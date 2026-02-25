# models/sms_tracker.py

from odoo import fields, models

# Africa's Talking delivery status - Odoo failure type
AT_STATUS_TO_FAILURE_TYPE = {
    # AT status codes that indicate permanent failure
    'InvalidPhoneNumber': 'sms_number_format',
    'UserInBlacklist': 'sms_blacklist',
    'InsufficientBalance': 'at_insufficient_balance',
    'InvalidSenderId': 'at_invalid_sender',
    'NotNetworkSubscriber': 'sms_number_format',
    'UserAccountSuspended': 'at_authentication',
}


class SmsTracker(models.Model):
    _inherit = 'sms.tracker'

    at_message_id = fields.Char(
        string="AT Message ID",
        readonly=True,
        help="Africa's Talking message ID for delivery tracking",
    )

    def _action_update_from_at_status(self, at_status, error_message=None):
        """Update tracker from Africa's Talking delivery webhook."""
        failure_type = AT_STATUS_TO_FAILURE_TYPE.get(at_status)
        if at_status == 'Success':
            return self._action_update_from_sms_state('sent')
        return self.with_context(
            sms_known_failure_reason=error_message
        )._action_update_from_provider_error(failure_type or 'not_delivered')
