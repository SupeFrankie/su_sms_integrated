# tools/sms_api.py

"""
Africa's Talking SMS API class.
Mirrors sms_twilio/tools/sms_api.py (SmsApiTwilio) in architecture.

_send_sms_batch receives messages in the standard Odoo format:
[
    {
        'content': str,
        'numbers': [{'uuid': str, 'number': str}, ...]
    }, ...
]

Returns results in standard Odoo format:
[
    {
        'uuid': str,
        'state': str,           # 'sent' | failure_type
        'failure_type': str | False,
        'failure_reason': str | False,
        'credit': float,        # cost in KES
        'at_message_id': str | False,
    }, ...
]
"""
import logging

import requests

from odoo import _
from odoo.addons.sms.tools.sms_api import SmsApiBase

from odoo.addons.su_sms_integrated.tools.sms_at import (
    AT_STATUS_TO_ODOO_FAILURE,
    AT_SUCCESS_STATUSES,
    get_at_messaging_endpoint,
    normalize_phone_number,
    parse_at_cost,
)

_logger = logging.getLogger(__name__)

# Maximum recipients per single AT API call (AT supports bulk mode natively)
AT_BATCH_MAX = 500


class SmsApiAT(SmsApiBase):
    """Africa's Talking SMS provider - drop-in replacement for SmsApiTwilio."""

    PROVIDER_TO_SMS_FAILURE_TYPE = SmsApiBase.PROVIDER_TO_SMS_FAILURE_TYPE | {
        'at_authentication': 'at_authentication',
        'at_insufficient_balance': 'at_insufficient_balance',
        'at_invalid_sender': 'at_invalid_sender',
        'at_number_format': 'sms_number_format',
    }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_at_headers(self):
        company = (self.company or self.env.company).sudo()
        return {
            'apiKey': company.at_api_key or '',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }

    def _build_at_request(self, to_numbers, body):
        """Build the POST payload for the AT messaging API."""
        company = (self.company or self.env.company).sudo()
        payload = {
            'username': company.at_username or '',
            'to': ','.join(to_numbers),
            'message': body,
            'bulkSMSMode': '1',
        }
        sender_id = company.at_sender_id
        if sender_id:
            payload['from'] = sender_id
        return payload

    # ------------------------------------------------------------------
    # Core send - called by sms.sms._send_with_api
    # ------------------------------------------------------------------
    def _send_sms_batch(self, messages, delivery_reports_url=False):
        """
        Send a batch of SMS via Africa's Talking.

        :param messages: Odoo standard format - list of
            {'content': str, 'numbers': [{'uuid': str, 'number': str}]}
        :param delivery_reports_url: ignored (we use AT's own webhook via controller)
        :return: list of per-UUID result dicts
        """
        company = (self.company or self.env.company).sudo()
        endpoint = get_at_messaging_endpoint(company)
        headers = self._get_at_headers()

        results = []
        session = requests.Session()

        for message in messages:
            body = message.get('content') or ''
            number_infos = message.get('numbers') or []

            if not number_infos:
                continue

            # Normalise numbers and build uuid - normalised map
            uuid_to_normalized = {}
            for info in number_infos:
                raw = info.get('number', '')
                normalized = normalize_phone_number(raw)
                uuid_to_normalized[info['uuid']] = (raw, normalized)

            # AT allows up to AT_BATCH_MAX per call; split if needed
            chunks = [number_infos[i:i + AT_BATCH_MAX]
                      for i in range(0, len(number_infos), AT_BATCH_MAX)]

            for chunk in chunks:
                # Build number list for this chunk
                to_list = []
                for info in chunk:
                    _, normalized = uuid_to_normalized[info['uuid']]
                    if normalized:
                        to_list.append(normalized)

                if not to_list:
                    for info in chunk:
                        results.append(self._at_failure_result(
                            info['uuid'], 'sms_number_format',
                            _("Invalid or missing phone number"),
                        ))
                    continue

                payload = self._build_at_request(to_list, body)
                at_response = self._call_at_api(session, endpoint, headers, payload)

                if at_response is None:
                    # Network error - all fail with server error
                    for info in chunk:
                        results.append(self._at_failure_result(
                            info['uuid'], 'sms_server',
                            _("Could not reach Africa's Talking API"),
                        ))
                    continue

                # Parse AT response and match back to uuid by number
                results.extend(
                    self._parse_at_response(at_response, chunk, uuid_to_normalized)
                )

        return results

    def _call_at_api(self, session, endpoint, headers, payload):
        """Make HTTP call to AT. Returns parsed JSON or None on network error."""
        try:
            response = session.post(
                endpoint,
                data=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            _logger.warning("AT SMS API timeout")
        except requests.exceptions.ConnectionError as exc:
            _logger.warning("AT SMS API connection error: %s", exc)
        except requests.exceptions.HTTPError as exc:
            _logger.warning("AT SMS API HTTP error %s: %s", exc.response.status_code, exc)
            try:
                return exc.response.json()
            except Exception:
                pass
        except Exception as exc:
            _logger.warning("AT SMS API unexpected error: %s", exc)
        return None

    def _parse_at_response(self, at_data, chunk, uuid_to_normalized):
        """
        Parse AT response and match results back to Odoo UUIDs.

        AT response structure:
        {
            "SMSMessageData": {
                "Message": "Sent to 1/1 Total Cost: KES 0.8000",
                "Recipients": [
                    {
                        "statusCode": 101,
                        "number": "+254727374660",
                        "status": "Success",
                        "cost": "KES 0.8000",
                        "messageId": "ATXid_xxx"
                    }, ...
                ]
            }
        }
        """
        results = []
        sms_data = at_data.get('SMSMessageData', {})
        recipients = sms_data.get('Recipients', [])

        # Build a map from normalised number - AT result
        at_by_number = {}
        for rec in recipients:
            num = rec.get('number', '').strip()
            if num:
                at_by_number[num] = rec

        # Match back to UUIDs
        for info in chunk:
            uuid = info['uuid']
            _, normalized = uuid_to_normalized.get(uuid, (None, None))
            at_rec = at_by_number.get(normalized) if normalized else None

            if at_rec is None:
                # AT didn't return a result for this number - mark as server error
                results.append(self._at_failure_result(
                    uuid, 'sms_server',
                    _("Africa's Talking did not return a result for this number"),
                ))
                continue

            at_status = at_rec.get('status', '')
            cost = parse_at_cost(at_rec.get('cost'))
            at_message_id = at_rec.get('messageId')

            if at_status in AT_SUCCESS_STATUSES:
                results.append({
                    'uuid': uuid,
                    'state': 'sent',
                    'failure_type': False,
                    'failure_reason': False,
                    'credit': cost,
                    'at_message_id': at_message_id,
                })
            else:
                failure_type = AT_STATUS_TO_ODOO_FAILURE.get(at_status, 'sms_server')
                results.append({
                    'uuid': uuid,
                    'state': failure_type,
                    'failure_type': failure_type,
                    'failure_reason': at_status,
                    'credit': 0.0,
                    'at_message_id': at_message_id,
                })

        return results

    def _at_failure_result(self, uuid, failure_type, reason):
        return {
            'uuid': uuid,
            'state': failure_type,
            'failure_type': failure_type,
            'failure_reason': reason,
            'credit': 0.0,
            'at_message_id': False,
        }

    # ------------------------------------------------------------------
    # Error message display (mirrors sms_twilio pattern)
    # ------------------------------------------------------------------
    def _get_sms_api_error_messages(self):
        error_dict = super()._get_sms_api_error_messages()
        error_dict.update({
            'at_authentication': _("Africa's Talking authentication failed - check your API key."),
            'at_insufficient_balance': _("Insufficient Africa's Talking credit balance."),
            'at_invalid_sender': _("Invalid Sender ID - check configuration in Settings."),
            'at_number_format': _("Phone number rejected by Africa's Talking."),
            'sms_number_format': _("Invalid phone number format."),
            'sms_blacklist': _("This number is blacklisted."),
            'sms_server': _("Africa's Talking server error - please try again."),
            'sms_acc': _("Account not whitelisted (sandbox restriction)."),
        })
        return error_dict
