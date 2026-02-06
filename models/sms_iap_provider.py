#sms_iap_provider.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError  # pyright: ignore[reportMissingImports]
import logging

_logger = logging.getLogger(__name__)


class IapAccount(models.Model):
    """
    This registers Africa's Talking as a provider in Odoo's system.
    Users will see it in Settings alongside Twilio.
    """
    _inherit = 'iap.account'

    provider = fields.Selection(
        selection=[('africas_talking', "Africa's Talking")],
        string="Provider",
        default='africas_talking',
        help="Select the SMS Provider"
    )


#class SmsApi(models.AbstractModel):
 #   """
  #  This is the BRIDGE - when Odoo wants to send SMS,
# it calls this and we route it through YOUR existing gateway.
 #   """
  #  _inherit = 'sms.api'

   # @api.model
    #def _send_sms_batch(self, messages):
     #   """
      #  Odoo calls this method when sending SMS.

       # Args:
        #    messages: List like [
         #       {
          #          'res_id': 123,  # ID of sms.sms record
           #         'number': '+254712345678',
            #        'content': 'Hello world'
             #   }
            #]

        #Returns:
         #   List of results for each message
        #"""
        # Check which provider is selected in Settings
        #account = self.env['iap.account'].get('sms')

        #if account.provider == 'africas_talking':
            # Use YOUR existing gateway system
         #   return self._send_via_su_gateway(messages)
        #else:
            # Use Odoo's default (Twilio, etc)
           # return super()._send_sms_batch(messages)

    def _send_via_su_gateway(self, messages):
        """
        Use YOUR existing sms.gateway.configuration to send.
        This preserves everything you've built!
        """
        # Get YOUR gateway (the one you already configured)
        gateway = self.env['sms.gateway.configuration'].search([
            ('is_default', '=', True)
        ], limit=1)

        if not gateway:
            raise UserError(_(
                'No SMS gateway configured!\n\n'
                'Configure in: SU SMS System → Configuration → Gateway Settings'
            ))

        _logger.info(f'Sending {len(messages)} SMS via SU Gateway: {gateway.name}')

        results = []

        for message in messages:
            try:
                # Use YOUR existing send_sms method!
                result = gateway.send_sms(
                    phone_number=message['number'],
                    message=message['content']
                )

                # Convert your result format to Odoo's format
                if result.get('success'):
                    results.append({
                        'res_id': message['res_id'],
                        'state': 'success',
                        'credit': result.get('cost', 0.0),
                    })
                else:
                    results.append({
                        'res_id': message['res_id'],
                        'state': 'error',
                        'credit': 0.0,
                    })

            except Exception as e:
                _logger.error(f'Error sending SMS: {str(e)}')
                results.append({
                    'res_id': message['res_id'],
                    'state': 'error',
                    'credit': 0.0,
                })

        return results