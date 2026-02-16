# models/sms_gateway_provider.py
"""
    SMS Gateway Provider Abstraction Layer
    Provides a clean interface for multiple SMS providers
    Currently implements Africa's Talking
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class SmsGatewayProvider(models.AbstractModel):
    """
    Abstract base model for SMS gateway providers
    All concrete providers must inherit this and implement required methods
    """
    _name = 'sms.gateway.provider'
    _description = 'SMS Gateway Provider Interface'
    
    @api.model
    def _get_active_provider(self):
        """
        Get the currently active SMS provider instance
        Returns: Provider model instance (e.g., sms.gateway.africastalking)
        """
        config = self.env['sms.gateway.configuration'].search([
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            raise UserError(_(
                "No active SMS gateway configured.\n"
                "Please go to Settings > SMS Configuration to set up your provider."
            ))
        
        # Return concrete implementation based on provider type
        provider_map = {
            'africastalking': 'sms.gateway.africastalking',
            # Add more providers here as needed
            # 'twilio': 'sms.gateway.twilio',
            # 'nexmo': 'sms.gateway.nexmo',
        }
        
        provider_model = provider_map.get(config.provider_type)
        
        if not provider_model:
            raise UserError(_(
                "Unsupported SMS provider: %s\n"
                "Supported providers: %s"
            ) % (config.provider_type, ', '.join(provider_map.keys())))
        
        return self.env[provider_model]
    
    def send_sms(self, number, message):
        """
        Send SMS to a single recipient
        
        Args:
            number (str): Phone number (international format recommended)
            message (str): Message content
            
        Returns:
            dict: {
                'success': bool,
                'cost': float,
                'message_id': str,
                'number': str,
                'error_message': str (if success=False)
            }
        """
        raise NotImplementedError(_("send_sms must be implemented by concrete provider"))
    
    def send_bulk_sms(self, recipients, message):
        """
        Send SMS to multiple recipients
        
        Args:
            recipients (list): List of phone numbers
            message (str): Message content
            
        Returns:
            list: List of result dicts (same format as send_sms)
        """
        # Default implementation: loop through send_sms
        results = []
        for number in recipients:
            result = self.send_sms(number, message)
            results.append(result)
        return results
    
    def get_balance(self):
        """
        Get account balance from provider
        
        Returns:
            float: Account balance in local currency (KES for Africa's Talking)
        """
        raise NotImplementedError(_("get_balance must be implemented by concrete provider"))


class SmsGatewayAfricasTalking(models.AbstractModel):
    """
    Africa's Talking SMS Provider Implementation
    Requires: pip install africastalking
    """
    _name = 'sms.gateway.africastalking'
    _inherit = 'sms.gateway.provider'
    _description = "Africa's Talking SMS Provider"
    
    def _get_config(self):
        """Get active Africa's Talking configuration"""
        config = self.env['sms.gateway.configuration'].search([
            ('provider_type', '=', 'africastalking'),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            raise UserError(_(
                "No active Africa's Talking configuration found.\n"
                "Please configure Africa's Talking in Settings > SMS Configuration."
            ))
        
        if not config.at_username or not config.at_api_key:
            raise UserError(_(
                "Africa's Talking configuration incomplete.\n"
                "Please provide Username and API Key in Settings."
            ))
        
        return config
    
    def _initialize_client(self):
        """Initialize Africa's Talking client"""
        config = self._get_config()
        
        try:
            import africastalking
            
            africastalking.initialize(
                username=config.at_username,
                api_key=config.at_api_key
            )
            
            return africastalking.SMS
            
        except ImportError:
            raise UserError(_(
                "Africa's Talking library not installed.\n"
                "Please install: pip install africastalking"
            ))
        except Exception as e:
            _logger.error(f"Failed to initialize Africa's Talking: {str(e)}")
            raise UserError(_(
                "Failed to initialize Africa's Talking:\n%s"
            ) % str(e))
    
    def send_sms(self, number, message):
        """Send SMS via Africa's Talking"""
        config = self._get_config()
        sms_service = self._initialize_client()
        
        try:
            # Format phone number (AT expects format: +254...)
            if not number.startswith('+'):
                # Assume Kenyan number if no country code
                number = '+254' + number.lstrip('0')
            
            # Send SMS
            response = sms_service.send(
                message=message,
                recipients=[number],
                sender_id=config.at_sender_id or None,
                enqueue=False  # Synchronous send
            )
            
            # Parse response
            if response['SMSMessageData']['Recipients']:
                recipient = response['SMSMessageData']['Recipients'][0]
                
                success = recipient['status'] == 'Success'
                
                # Parse cost (format: "KES 0.80")
                cost_str = recipient.get('cost', '0')
                cost = 0.0
                if cost_str and 'KES' in cost_str:
                    cost = float(cost_str.replace('KES', '').strip())
                
                return {
                    'success': success,
                    'cost': cost,
                    'message_id': recipient.get('messageId'),
                    'number': recipient['number'],
                    'error_message': recipient.get('status') if not success else None
                }
            else:
                return {
                    'success': False,
                    'cost': 0.0,
                    'message_id': None,
                    'number': number,
                    'error_message': 'No recipients in response'
                }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Africa's Talking send failed for {number}: {error_msg}")
            
            return {
                'success': False,
                'cost': 0.0,
                'message_id': None,
                'number': number,
                'error_message': error_msg
            }
    
    def send_bulk_sms(self, recipients, message):
        """
        Send bulk SMS via Africa's Talking
        More efficient than looping send_sms as it uses single API call
        """
        config = self._get_config()
        sms_service = self._initialize_client()
        
        try:
            # Format all phone numbers
            formatted_numbers = []
            for number in recipients:
                if not number.startswith('+'):
                    number = '+254' + number.lstrip('0')
                formatted_numbers.append(number)
            
            # Send bulk SMS
            response = sms_service.send(
                message=message,
                recipients=formatted_numbers,
                sender_id=config.at_sender_id or None,
                enqueue=False
            )
            
            # Parse results
            results = []
            if response['SMSMessageData']['Recipients']:
                for recipient in response['SMSMessageData']['Recipients']:
                    success = recipient['status'] == 'Success'
                    
                    cost_str = recipient.get('cost', '0')
                    cost = 0.0
                    if cost_str and 'KES' in cost_str:
                        cost = float(cost_str.replace('KES', '').strip())
                    
                    results.append({
                        'success': success,
                        'cost': cost,
                        'message_id': recipient.get('messageId'),
                        'number': recipient['number'],
                        'error_message': recipient.get('status') if not success else None
                    })
            
            return results
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Africa's Talking bulk send failed: {error_msg}")
            
            # Return failure for all recipients
            return [{
                'success': False,
                'cost': 0.0,
                'message_id': None,
                'number': num,
                'error_message': error_msg
            } for num in recipients]
    
    def get_balance(self):
        """Get account balance from Africa's Talking"""
        try:
            import africastalking
            
            config = self._get_config()
            
            africastalking.initialize(
                username=config.at_username,
                api_key=config.at_api_key
            )
            
            application = africastalking.Application
            user_data = application.fetch_application_data()
            
            balance_str = user_data.get('UserData', {}).get('balance', '0')
            
            # Parse balance (format: "KES 123.45")
            if 'KES' in balance_str:
                balance = float(balance_str.replace('KES', '').strip())
            else:
                balance = float(balance_str)
            
            return balance
            
        except Exception as e:
            _logger.error(f"Failed to fetch Africa's Talking balance: {str(e)}")
            return 0.0
    
    def check_delivery_status(self, message_id):
        """
        Check delivery status of a message
        Note: Africa's Talking primarily uses webhooks for delivery reports
        """
        # Africa's Talking doesn't have a direct status check API
        # Status updates come via webhooks
        _logger.warning(
            "Africa's Talking delivery status must be obtained via webhooks. "
            "Message ID: %s" % message_id
        )
        return None