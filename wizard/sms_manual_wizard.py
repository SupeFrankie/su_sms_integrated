# wizard/sms_manual_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SmsManualWizard(models.TransientModel):
    _name = 'sms.manual.wizard'
    _description = 'Manual SMS Wizard'
    
    phone_numbers = fields.Text(
        string='Phone Numbers',
        required=True,
        help='Enter comma-separated phone numbers (e.g., 0712345678, 0723456789)'
    )
    
    template_id = fields.Many2one('sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    
    recipient_count = fields.Integer(
        string='Recipients',
        compute='_compute_recipient_count'
    )
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.body = self.template_id.body
    
    @api.depends('phone_numbers')
    def _compute_recipient_count(self):
        for wizard in self:
            if wizard.phone_numbers:
                numbers = [n.strip() for n in wizard.phone_numbers.split(',') if n.strip()]
                wizard.recipient_count = len(numbers)
            else:
                wizard.recipient_count = 0
    
    def action_send_sms(self):
        """Send SMS to manually entered numbers"""
        self.ensure_one()
        
        # Parse numbers
        numbers = [n.strip() for n in self.phone_numbers.split(',') if n.strip()]
        
        if not numbers:
            raise UserError(_('Please enter at least one phone number'))
        
        # Get billing department
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        # Create sms.sms records
        sms_records = self.env['sms.sms']
        for number in numbers:
            normalized = self._normalize_phone(number)
            if normalized:
                sms_records |= self.env['sms.sms'].create({
                    'number': normalized,
                    'body': self.body,
                    'su_sms_type': 'manual',
                    'su_department_id': admin.department_id.id if admin else False,
                })
        
        if not sms_records:
            raise UserError(_('No valid phone numbers found'))
        
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Sent'),
                'message': _(f'{len(sms_records)} SMS messages queued'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _normalize_phone(self, number):
        """Normalize to +254 format"""
        if not number:
            return False
        number = number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if number.startswith('0'):
            return '+254' + number[1:]
        elif not number.startswith('+'):
            return '+254' + number
        return number