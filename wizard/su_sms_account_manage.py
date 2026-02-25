# wizard/su_sms_account_manage.py

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.su_sms_integrated.tools.sms_at import normalize_phone_number

_logger = logging.getLogger(__name__)


class SuSmsAccountManage(models.TransientModel):
    _name = 'su.sms.account.manage'
    _description = "Africa's Talking SMS Connection Wizard"

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    sms_provider = fields.Selection(
        related='company_id.sms_provider',
        readonly=False,
    )
    at_username = fields.Char(
        related='company_id.at_username',
        readonly=False,
    )
    at_api_key = fields.Char(
        related='company_id.at_api_key',
        readonly=False,
    )
    at_sender_id = fields.Char(
        related='company_id.at_sender_id',
        readonly=False,
    )
    at_environment = fields.Selection(
        related='company_id.at_environment',
        readonly=False,
    )
    test_number = fields.Char("Test Number", help="Number to send a test SMS to, e.g. +254727374660")

    def action_check_balance(self):
        """Fetch current Africa's Talking balance and show a notification."""
        try:
            balance = self.company_id._get_at_balance()
            return self._display_notification(
                'success',
                _("Africa's Talking balance: %s", balance),
            )
        except UserError as exc:
            return self._display_notification('danger', str(exc))

    def action_send_test(self):
        """Send a test SMS to the configured test number."""
        if not self.test_number:
            raise UserError(_("Please enter a test phone number."))
        normalized = normalize_phone_number(self.test_number)
        composer = self.env['sms.composer'].create({
            'body': _("Test SMS from Strathmore University Odoo (Africa's Talking)"),
            'composition_mode': 'numbers',
            'numbers': normalized,
        })
        sms_records = composer._action_send_sms()
        sms = sms_records[0] if sms_records else None
        has_error = bool(sms and sms.failure_type)
        if not has_error:
            msg = _("Test SMS sent successfully to %s.", normalized)
        else:
            sms_api = self.company_id._get_sms_api_class()(self.env)
            error_msgs = sms_api._get_sms_api_error_messages()
            msg = _("Error: %s", error_msgs.get(sms.failure_type, sms.failure_type))
        return self._display_notification('danger' if has_error else 'success', msg)

    def action_save(self):
        return {'type': 'ir.actions.act_window_close'}

    def _display_notification(self, notif_type, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Africa's Talking SMS"),
                'message': message,
                'type': notif_type,
                'sticky': False,
            },
        }
