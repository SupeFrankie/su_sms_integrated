# models/sms_balance.py


from odoo import models, api, _
import requests
import logging

_logger = logging.getLogger(__name__)


class SmsBalance(models.TransientModel):
    _name = 'su.sms.balance'
    _description = 'SMS Balance Monitor'
    
    @api.model
    def get_balance(self):
        account = self.env['iap.account'].get('sms')
        
        if not account:
            return {'error': 'No SMS account configured'}
        
        if account.provider == 'africas_talking':
            return self._get_at_balance(account)
        
        return {
            'balance': account.account_token or 0,
            'currency': 'Credits',
            'provider': 'Odoo IAP',
            'warning': False,
            'restricted': False
        }
    
    def _get_at_balance(self, account):
        if account.at_environment == 'sandbox':
            url = 'https://api.sandbox.africastalking.com/version1/user'
        else:
            url = 'https://api.africastalking.com/version1/user'
        
        headers = {
            'apiKey': account.at_api_key,
            'Accept': 'application/json'
        }
        
        params = {'username': account.at_username}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            user_data = data.get('UserData', {})
            balance_str = user_data.get('balance', 'KES 0')
            balance = float(balance_str.replace('KES ', '').replace(',', ''))
            
            MINIMUM_CREDIT_BALANCE = 80
            ICTS_THRESHOLD = 15000
            
            is_system_admin = self.env.user.has_group(
                'su_sms_integrated.group_sms_system_admin'
            )
            
            return {
                'balance': balance,
                'currency': 'KES',
                'provider': 'Africa\'s Talking',
                'warning': balance < MINIMUM_CREDIT_BALANCE,
                'restricted': balance < ICTS_THRESHOLD and not is_system_admin,
                'message': self._get_balance_message(balance, is_system_admin)
            }
        except Exception as e:
            _logger.error(f'Failed to fetch AT balance: {e}')
            return {
                'error': str(e),
                'provider': 'Africa\'s Talking'
            }
    
    def _get_balance_message(self, balance, is_admin):
        if balance <= 0:
            return 'No credits available'
        elif balance < 80:
            return f'Low balance (KES {balance:.2f})'
        elif balance < 15000 and not is_admin:
            return f'Balance: KES {balance:.2f}. Only System Administrators can send SMS'
        else:
            return f'Balance: KES {balance:.2f}'