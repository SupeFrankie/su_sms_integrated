# tools/sms_api.py

import re
import requests
from odoo import _
from odoo.exceptions import UserError
from odoo.addons.sms.tools.sms_api import SmsApiBase


class SmsApiAfricasTalking(SmsApiBase):
    """
    Africa's Talking implementation of Odoo's SMS provider API.

    Responsibilities:
      - Send message batches via the AT REST API.
      - Return Odoo-compatible result dicts.
      - Store provider_message_id in the result so the engine
        can persist it via _handle_call_result_hook.

    NOT responsible for:
      - sms.sms state management (engine does that).
      - sms.tracker updates (webhook controller does that).
    """

    API_URL = "https://api.africastalking.com/version1/messaging"

    # AT send-time status → Odoo failure type
    AT_STATUS_TO_FAILURE = {
        'InvalidPhoneNumber': 'wrong_number_format',
        'UserInBlacklist': 'sms_blacklist',
        'InsufficientBalance': 'sms_credit',
        'AuthenticationFailed': 'sms_server',
    }

    def _normalize_number(self, number):
        """
        Normalize Kenyan numbers to E.164 format.
        Assumes Kenya default (+254).

        Examples:
            0712345678      → +254712345678
            254712345678    → +254712345678
            +254712345678   → +254712345678
        """
        if not number:
            return number

        number = re.sub(r'\s+|-', '', number)

        if number.startswith('+'):
            return number

        if number.startswith('0') and len(number) == 10:
            return '+254' + number[1:]

        if number.startswith('254') and len(number) == 12:
            return '+' + number

        return number

    # -----------------------------------------------------------------
    # Core send method – called by Odoo SMS engine via _split_by_api
    # -----------------------------------------------------------------

    def _send_sms_batch(self, messages):
        """
        Send a batch of messages through Africa's Talking.

        Args:
            messages: list of (uuid, {'number': str, 'content': str})

        Returns:
            dict keyed by uuid:
            {
                uuid: {
                    'state': 'sent' | 'server_error' | ...,
                    'credit': float,
                    'provider_message_id': str,
                }
            }
        """
        if not messages:
            return {}

        company = self._get_company_from_messages(messages)
        self._assert_at_credentials(company)

        headers = {
            'apiKey': company.at_api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }

        numbers = ','.join(
            self._normalize_number(m['number'])
            for _, m in messages
        )
        content = messages[0][1]['content']

        payload = {
            'username': company.at_username,
            'to': numbers,
            'message': content,
        }

        if company.at_sender_id:
            payload['from'] = company.at_sender_id

        try:
            response = requests.post(
                self.API_URL, headers=headers, data=payload, timeout=15
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return {
                uuid: {'state': 'server_error', 'credit': 0}
                for uuid, _ in messages
            }

        return self._parse_at_response(data, messages)

    # -----------------------------------------------------------------
    # Response parser
    # -----------------------------------------------------------------

    def _parse_at_response(self, data, messages):
        """
        Convert AT API response into Odoo-compatible result dict.
        AT returns one recipient entry per number, in order.
        """
        results = {}
        recipients = data.get('SMSMessageData', {}).get('Recipients', [])

        for (uuid, _), recipient in zip(messages, recipients):
            status = recipient.get('status', '')
            message_id = recipient.get('messageId')
            cost = recipient.get('cost', '0')

            if status == 'Success':
                results[uuid] = {
                    'state': 'sent',
                    'credit': self._parse_credit(cost),
                    'provider_message_id': message_id,
                }
            else:
                failure_type = self.AT_STATUS_TO_FAILURE.get(
                    status, 'server_error'
                )
                results[uuid] = {
                    'state': failure_type,
                    'credit': 0,
                }

        return results

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _assert_at_credentials(self, company):
        """Raise UserError early if AT credentials are not configured."""
        if not company.at_username:
            raise UserError(
                _("Africa's Talking username is missing for company '%s'.")
                % company.name
            )
        if not company.at_api_key:
            raise UserError(
                _("Africa's Talking API key is missing for company '%s'.")
                % company.name
            )

    def _parse_credit(self, cost_string):
        """
        AT returns cost as 'KES 0.8000'.  Extract the numeric portion.
        Falls back to 1.0 on any parse error.
        """
        try:
            return float(cost_string.split()[-1])
        except Exception:
            return 1.0

    def _get_company_from_messages(self, messages):
        """
        Resolve the res.company record from the first message's UUID.
        SmsApiBase subclasses receive self.env from the engine.
        """
        uuid = messages[0][0]
        sms = self.env['sms.sms'].sudo().search(
            [('uuid', '=', uuid)], limit=1
        )
        if not sms:
            return self.env.company
        return sms.company_id or self.env.company