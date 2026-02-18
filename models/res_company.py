# models/res_company.py


"""
Company Configuration for Africa's Talking
===========================================

IN PARITY with sms_twilio/models/res_company.py

Key Points:
- Adds 'africastalking' to sms_provider selection
- Stores AT credentials (username, api_key, sender_id)
- Returns SmsApiAfricasTalking from _get_sms_api_class()
- Validates credentials with _assert_at_credentials()
"""

from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.su_sms_integrated.tools.sms_api import SmsApiAfricasTalking


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # ===== SMS PROVIDER SELECTION =====
    # Odoo 19: sms_provider does not exist on res.company in the base sms
    # module, so we define it here as a full field (not selection_add).
    # If another SMS provider module is also installed that defines this
    # field, change back to selection_add and add ondelete.
    sms_provider = fields.Selection(
        selection=[
            ('africastalking', "Africa's Talking"),
        ],
        string="SMS Provider",
        default='africastalking',
    )
    
    # ===== AFRICA'S TALKING CREDENTIALS =====
    # Pattern: Store per-company, restrict to system group
    # Like sms_twilio: sms_twilio_account_sid, sms_twilio_auth_token
    at_username = fields.Char(
        string="AT Username",
        groups='base.group_system',
        help="Africa's Talking username.\n"
             "Use 'sandbox' for testing or your app name for production.\n"
             "Find in: Dashboard > Overview"
    )
    
    at_api_key = fields.Char(
        string="AT API Key",
        groups='base.group_system',
        help="Africa's Talking API Key.\n"
             "Find in: Dashboard > Settings > API Key\n"
             "Keep this secret!"
    )
    
    at_sender_id = fields.Char(
        string="AT Sender ID",
        groups='base.group_system',
        help="Optional sender ID (Alphanumeric name shown to recipients).\n"
             "Must be registered with Africa's Talking.\n"
             "Leave empty to use default (AFRICASTKNG).\n"
             "To register: Contact AT support with your brand name."
    )
    
    # ===== API CLASS ROUTING =====
    def _get_sms_api_class(self):
        """
        Return SMS API class for this company.
        
        EXACT pattern from sms_twilio/models/res_company.py
        
        Called by Odoo's SMS engine to get the right API implementation.
        """
        self.ensure_one()
        if self.sms_provider == 'africastalking':
            return SmsApiAfricasTalking
        return super()._get_sms_api_class()
    
    # ===== CREDENTIAL VALIDATION =====
    def _assert_at_credentials(self):
        """
        Validate Africa's Talking credentials.
        
        Pattern from sms_twilio: _assert_twilio_sid()
        
        Raises:
            UserError: If credentials invalid or missing
        """
        self.ensure_one()
        
        if not self.at_username:
            raise UserError(_(
                "Africa's Talking username not configured for company '%s'.\n\n"
                "Go to: Settings > Companies > %s\n"
                "Set the AT Username field."
            ) % (self.name, self.name))
        
        if not self.at_api_key:
            raise UserError(_(
                "Africa's Talking API Key not configured for company '%s'.\n\n"
                "Go to: Settings > Companies > %s\n"
                "Set the AT API Key field."
            ) % (self.name, self.name))
        
        # Validate username format (AT-specific)
        # Sandbox usernames are exactly 'sandbox'
        # Production usernames are alphanumeric
        if self.at_username not in ('sandbox', 'SANDBOX'):
            if not self.at_username.replace('_', '').replace('-', '').isalnum():
                raise UserError(_(
                    "Invalid Africa's Talking username: '%s'\n\n"
                    "Username must be alphanumeric (can include _ and -)."
                ) % self.at_username)
    
    # ===== MANAGEMENT ACTION =====
    def action_test_at_connection(self):
        """
        Test AT connection and fetch account balance.
        
        Pattern: Similar to sms_twilio wizard but simplified.
        
        Returns:
            dict: Notification action
        """
        self.ensure_one()
        self._assert_at_credentials()
        
        try:
            import africastalking
            
            # Initialize SDK
            africastalking.initialize(
                username=self.at_username,
                api_key=self.at_api_key
            )
            
            # Fetch account info
            app = africastalking.Application
            data = app.fetch_application_data()
            
            balance = data.get('UserData', {}).get('balance', 'Unknown')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _(
                        "Successfully connected to Africa's Talking!\n\n"
                        "Account: %s\n"
                        "Balance: %s"
                    ) % (self.at_username, balance),
                    'type': 'success',
                    'sticky': True,
                }
            }
        
        except ImportError:
            raise UserError(_(
                "Africa's Talking SDK not installed.\n\n"
                "System administrators must run:\n"
                "pip install africastalking\n\n"
                "Then restart Odoo."
            ))
        
        except Exception as e:
            raise UserError(_(
                "Connection test failed:\n%s\n\n"
                "Please verify your credentials:\n"
                "- Username: %s\n"
                "- API Key: %s"
            ) % (str(e), self.at_username, '(hidden)'))
    
    def action_view_at_dashboard(self):
        """
        Open Africa's Talking dashboard in new tab.
        
        Returns:
            dict: URL action
        """
        self.ensure_one()
        
        # Determine dashboard URL based on username
        if self.at_username in ('sandbox', 'SANDBOX'):
            url = 'https://account.africastalking.com/apps/sandbox'
        else:
            url = 'https://account.africastalking.com/apps'
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }