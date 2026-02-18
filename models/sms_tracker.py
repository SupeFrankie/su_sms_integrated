# models/sms_tracker.py



"""
Extend sms.tracker with Africa's Talking-specific fields and error handling.

Pattern: mirrors sms_twilio/models/sms_tracker.py
"""

from odoo import models, fields


# AT error code -> Odoo failure type
# Pattern from sms_twilio: TWILIO_CODE_TO_FAILURE_TYPE
AT_CODE_TO_FAILURE_TYPE = {
    '401': 'sms_credit',             # Invalid credentials
    '402': 'wrong_number_format',    # Invalid number
    '403': 'sms_server',             # Invalid sender ID
    '404': 'sms_credit',             # Insufficient balance
    '405': 'sms_blacklist',          # User blacklisted
    '406': 'not_allowed',            # Risk hold
    '407': 'not_delivered',          # Rate limit
    '409': 'wrong_number_format',    # Rejected number
    '500': 'sms_server',             # Internal server error
    '503': 'not_delivered',          # Service unavailable
}


class SmsTracker(models.Model):
    _inherit = 'sms.tracker'

    # ------------------------------------------------------------------
    # Africa's Talking persistent message identifier
    # Pattern from twilio: sms_twilio_sid
    # ------------------------------------------------------------------
    at_message_id = fields.Char(
        string="AT Message ID",
        readonly=True,
        help="Africa's Talking message identifier (ATXid_…). "
             "Persists after sms.sms deletion for audit purposes.",
    )

    # ------------------------------------------------------------------
    # Webhook error update
    # Pattern from twilio: _action_update_from_twilio_error()
    # ------------------------------------------------------------------

    def _action_update_from_at_error(self, at_status, error_code, error_message):
        """
        Update this tracker record from an AT delivery-failure webhook.

        Args:
            at_status:     str – AT delivery status ('Rejected', 'Failed', …)
            error_code:    str | None – AT numeric error code ('402', …)
            error_message: str | None – Human-readable error description

        Returns:
            bool – result of _action_update_from_provider_error()
        """
        failure_type = AT_CODE_TO_FAILURE_TYPE.get(error_code)

        # Fallback when code is unknown but status signals a hard failure
        if not failure_type:
            failure_type = 'not_delivered' if at_status == 'Failed' else None

        return self.with_context(
            sms_known_failure_reason=error_message or at_status
        )._action_update_from_provider_error(failure_type)

    # ------------------------------------------------------------------
    # Convenience action
    # ------------------------------------------------------------------

    def action_open_at_reports(self):
        """Open Africa's Talking sent-messages report page in a new tab."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://account.africastalking.com/messaging/bulk/sent',
            'target': 'new',
        }