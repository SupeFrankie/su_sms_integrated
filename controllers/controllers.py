# controllers/controllers.py


"""
Africa's Talking delivery-status webhook controller.

Pattern: mirrors sms_twilio/controllers/controllers.py exactly.

Endpoint:  POST /sms_africastalking/status/<uuid>
Security:  HMAC-SHA256 signature validation via X-AT-Signature header.
"""

import hmac
import logging
import re

from odoo.addons.su_sms_integrated.tools.sms_africastalking import (
    generate_at_callback_signature,
    get_at_error_code_mapping,
)
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

# AT delivery status -> Odoo sms.tracker state
# Only error states are listed separately so the controller can branch.
_AT_ERROR_STATES = {'Rejected', 'Failed'}

_AT_TO_SMS_STATE = {
    'Success':   'sent',
    'Sent':      'sent',
    'Delivered': 'sent',
    'Submitted': 'sent',
    'Buffered':  'outgoing',
    'Queued':    'outgoing',
    'Rejected':  'error',
    'Failed':    'error',
}

_UUID_RE = re.compile(r'^[0-9a-f]{32}$')


class SmsAfricasTalkingController(Controller):
    """Webhook controller for Africa's Talking delivery reports."""

    @route(
        '/sms_africastalking/status/<string:uuid>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def update_sms_status(
        self,
        uuid,
        status=None,
        errorCode=None,
        errorMessage=None,
        **kwargs,
    ):
        """
        Receive AT delivery report and update sms.tracker.

        AT POST params:
          id            AT message ID (ATXid_…)
          status        Delivery status
          phoneNumber   Recipient number
          errorCode     AT error code if failed
          errorMessage  Human-readable error
        """
        # Validate UUID 
        if not _UUID_RE.match(uuid or ''):
            _logger.warning("AT webhook: invalid uuid=%r", uuid)
            raise request.not_found()

        # Validate status 
        if status not in _AT_TO_SMS_STATE:
            _logger.warning(
                "AT webhook: unknown status=%r for uuid=%s", status, uuid
            )
            raise request.not_found()

        # Validate signature 
        if not self._validate_at_signature(uuid):
            _logger.warning(
                "AT webhook: signature mismatch for uuid=%s", uuid
            )
            raise request.not_found()

        # Find tracker 
        tracker_sudo = request.env['sms.tracker'].sudo().search(
            [('sms_uuid', '=', uuid)]
        )
        if not tracker_sudo:
            _logger.warning(
                "AT webhook: no sms.tracker for uuid=%s", uuid
            )
            return 'OK'  # Return OK so AT does not retry indefinitely.

        # Update tracker state 
        if status in _AT_ERROR_STATES:
            tracker_sudo._action_update_from_at_error(
                status, errorCode, errorMessage
            )
        else:
            tracker_sudo._action_update_from_sms_state(
                _AT_TO_SMS_STATE[status]
            )

        # Mark SMS for deletion (exact twilio pattern) 
        request.env['sms.sms'].sudo().search([
            ('uuid', '=', uuid),
            ('to_delete', '=', False),
        ]).write({'to_delete': True})

        return 'OK'

    # ------------------------------------------------------------------

    def _validate_at_signature(self, uuid):
        """
        Compare the X-AT-Signature header against our computed HMAC.

        Returns True if signatures match, False otherwise.
        If the company has no api_key configured, validation is skipped
        (returns True) so the webhook is still functional during initial setup.
        """
        sms = request.env['sms.sms'].sudo().search(
            [('uuid', '=', uuid)], limit=1
        )
        if not sms:
            return False

        company = (sms.company_id or request.env.company).sudo()

        if not company.at_api_key:
            _logger.debug(
                "AT webhook: no api_key on company %s, skipping signature check",
                company.name,
            )
            return True

        computed = generate_at_callback_signature(
            company,
            uuid,
            request.httprequest.form.to_dict(),
        )
        received = request.httprequest.headers.get('X-AT-Signature', '')

        return hmac.compare_digest(computed, received)