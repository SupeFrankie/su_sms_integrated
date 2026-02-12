# models/iap_africas_talking.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class IapAccount(models.Model):
    _inherit = 'iap.account'
    
    # FIX: Defined as a NEW field because 'provider' does not exist in Odoo 19 iap.account
    provider = fields.Selection(
        selection=[('africas_talking', "Africa's Talking")],
        string="Provider",
        default='africas_talking',
        required=True,
        help="Select the SMS Provider"
    )
    
    at_username = fields.Char(string='AT Username')
    at_api_key = fields.Char(string='AT API Key')
    at_sender_id = fields.Char(string='Sender ID', default='STRATHU')
    at_environment = fields.Selection([
        ('sandbox', 'Sandbox'),
        ('production', 'Production')
    ], default='production')
    
    @api.constrains('at_sender_id')
    def _check_sender_id(self):
        for account in self:
            if account.provider == 'africas_talking' and account.at_sender_id:
                if len(account.at_sender_id) > 11:
                    raise UserError(_('Sender ID cannot exceed 11 characters'))


# NOTE: We keep this minimal to prevent crashes if Odoo changes sms.api signature
class SmsApi(models.AbstractModel):
    _inherit = 'sms.api'
    
    @api.model
    def _send_sms(self, numbers, message):
        """
        Override to intercept SMS sending if needed. 
        For now, we rely on the Gateway configuration instead of this low-level hook 
        to avoid conflicts with Odoo's native IAP flow.
        """
        return super(SmsApi, self)._send_sms(numbers, message)