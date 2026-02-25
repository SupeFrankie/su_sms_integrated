# models/res_config_settings.py

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sms_provider = fields.Selection(
        related='company_id.sms_provider',
        required=True,
        readonly=False,
    )
    at_environment = fields.Selection(
        related='company_id.at_environment',
        readonly=False,
    )
    su_ldap_enabled = fields.Boolean(
        related='company_id.su_ldap_enabled',
        readonly=False,
    )

    def action_open_su_sms_account_manage(self):
        return self.company_id._action_open_su_sms_account_manage()
