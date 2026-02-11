# models/iap_africas_talking.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class IapAccount(models.Model):
    """Extend IAP Account to support Africa's Talking"""
    _inherit = 'iap.account'
    
    provider = fields.Selection(
        selection_add=[('africas_talking', "Africa's Talking")],
        ondelete={'africas_talking': 'cascade'}
    )
    
    # Africa's Talking specific fields
    at_username = fields.Char(
        string='AT Username',
        help='Africa\'s Talking account username'
    )
    at_api_key = fields.Char(
        string='AT API Key',
        help='Africa\'s Talking API key (keep secret)'
    )
    at_sender_id = fields.Char(
        string='Sender ID',
        default='STRATHU',
        help='Sender name (max 11 chars, alphanumeric)'
    )
    at_environment = fields.Selection([
        ('sandbox', 'Sandbox'),
        ('production', 'Production')
    ], string='Environment', default='production')
    
    @api.constrains('at_sender_id')
    def _check_sender_id(self):
        for account in self:
            if account.provider == 'africas_talking' and account.at_sender_id:
                if len(account.at_sender_id) > 11:
                    raise UserError(_('Sender ID cannot exceed 11 characters'))


class SmsApi(models.AbstractModel):
    """Override SMS API to route through Africa's Talking when configured"""
    _inherit = 'sms.api'
    
    @api.model
    def _send_sms(self, numbers, message):
        """Route SMS based on configured provider"""
        account = self.env['iap.account'].get('sms')
        
        # Check if Africa's Talking is configured
        if account and account.provider == 'africas_talking':
            # Security check: Only System Admins can use AT
            if not self.env.user.has_group('su_sms_integrated.group_sms_system_admin'):
                raise UserError(_(
                    'Only System Administrators can send SMS via Africa\'s Talking. '
                    'Please contact your administrator.'
                ))
            
            return self._send_sms_africas_talking(numbers, message, account)
        
        # Default to Odoo IAP
        return super()._send_sms(numbers, message)
    
    def _send_sms_africas_talking(self, numbers, message, account):
        """Send SMS via Africa's Talking API"""
        if account.at_environment == 'sandbox':
            url = 'https://api.sandbox.africastalking.com/version1/messaging'
        else:
            url = 'https://api.africastalking.com/version1/messaging'
        
        headers = {
            'apiKey': account.at_api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        # Format numbers (ensure +254 format for Kenya)
        formatted_numbers = []
        for num in numbers:
            if not num.startswith('+'):
                # Assume Kenya if no country code
                num = '+254' + num.lstrip('0')
            formatted_numbers.append(num)
        
        data = {
            'username': account.at_username,
            'to': ','.join(formatted_numbers),
            'message': message,
            'from': account.at_sender_id or 'STRATHU'
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            _logger.info(f'Africa\'s Talking response: {result}')
            
            return self._parse_at_response(result, formatted_numbers)
            
        except requests.exceptions.Timeout:
            _logger.error('Africa\'s Talking API timeout')
            raise UserError(_('SMS Gateway timeout. Please try again.'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Africa\'s Talking API error: {e}')
            raise UserError(_('SMS sending failed: %s') % str(e))
    
    def _parse_at_response(self, result, numbers):
        """Convert Africa's Talking response to Odoo format"""
        responses = []
        recipients = result.get('SMSMessageData', {}).get('Recipients', [])
        
        for i, recipient in enumerate(recipients):
            # Parse cost (format: "KES 0.8000")
            cost_str = recipient.get('cost', 'KES 0')
            cost = float(cost_str.replace('KES ', '').replace(',', ''))
            
            state = 'sent' if recipient.get('status') == 'Success' else 'error'
            
            responses.append({
                'res_id': False,  # Will be set by Odoo
                'state': state,
                'credit': cost,  # Cost in KES
                'failure_reason': recipient.get('status') if state == 'error' else None
            })
        
        # If fewer responses than numbers, fill with errors
        while len(responses) < len(numbers):
            responses.append({
                'res_id': False,
                'state': 'error',
                'credit': 0.0,
                'failure_reason': 'No response from gateway'
            })
        
        return responses