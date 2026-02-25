# models/res_company.py

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.su_sms_integrated.tools.sms_api import SmsApiAT

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ------------------------------------------------------------------
    # Provider selection (mirrors sms_twilio approach)
    # ------------------------------------------------------------------
    sms_provider = fields.Selection(
        string='SMS Provider',
        selection=[
            ('iap', 'Send via Odoo (IAP)'),
            ('africas_talking', "Send via Africa's Talking"),
        ],
        default='iap',
    )

    # ------------------------------------------------------------------
    # Africa's Talking credentials (system-only)
    # ------------------------------------------------------------------
    at_username = fields.Char(
        string="AT Username",
        groups='base.group_system',
        help="Africa's Talking account username (use 'sandbox' for testing)",
    )
    at_api_key = fields.Char(
        string="AT API Key",
        groups='base.group_system',
    )
    at_sender_id = fields.Char(
        string="AT Sender ID",
        default='STRATHU',
        groups='base.group_system',
        help="Alphanumeric Sender ID registered on Africa's Talking (max 11 chars)",
    )
    at_environment = fields.Selection(
        string='AT Environment',
        selection=[('production', 'Production'), ('sandbox', 'Sandbox')],
        default='production',
        groups='base.group_system',
    )

    # ------------------------------------------------------------------
    # LDAP config (soft - shown when auth_ldap installed)
    # ------------------------------------------------------------------
    su_ldap_enabled = fields.Boolean(
        string='Enable LDAP Login',
        default=False,
        help="If auth_ldap is installed and configured, users will authenticate via LDAP/AD.",
    )

    # ------------------------------------------------------------------
    # Provider routing (mirrors sms_twilio._get_sms_api_class)
    # ------------------------------------------------------------------
    def _get_sms_api_class(self):
        self.ensure_one()
        if self.sms_provider == 'africas_talking':
            return SmsApiAT
        return super()._get_sms_api_class()

    # ------------------------------------------------------------------
    # AT helpers
    # ------------------------------------------------------------------
    def _assert_at_credentials(self):
        """Raise if credentials are not configured."""
        self.ensure_one()
        if not self.at_username or not self.at_api_key:
            raise UserError(_(
                "Africa's Talking credentials are not configured.\n"
                "Please set the AT Username and API Key in Settings - Technical - SMS."
            ))

    def _get_at_balance(self):
        """Fetch AT account balance. Returns a string like 'KES 1234.50' or raises."""
        self.ensure_one()
        self._assert_at_credentials()
        base_url = (
            'https://sandbox.africastalking.com'
            if self.at_environment == 'sandbox'
            else 'https://api.africastalking.com'
        )
        try:
            response = requests.get(
                f'{base_url}/version1/user',
                params={'username': self.sudo().at_username},
                headers={
                    'apiKey': self.sudo().at_api_key,
                    'Accept': 'application/json',
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data.get('UserData', {}).get('balance', 'Unknown')
        except requests.exceptions.RequestException as exc:
            _logger.warning("AT balance check failed: %s", exc)
            raise UserError(_("Could not reach Africa's Talking API: %s", str(exc)))

    def _action_open_su_sms_account_manage(self):
        return {
            'name': _("Manage Africa's Talking SMS"),
            'res_model': 'su.sms.account.manage',
            'res_id': False,
            'context': self.env.context,
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }
