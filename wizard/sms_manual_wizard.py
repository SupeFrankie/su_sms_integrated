# wizard/sms_manual_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re


class SmsManualWizard(models.TransientModel):
    _name = 'sms.manual.wizard'
    _description = 'Manual SMS Wizard'
    
    phone_numbers = fields.Text(
        string='Phone Numbers',
        required=True,
        help='Enter comma-separated phone numbers'
    )
    template_id = fields.Many2one('su.sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    recipient_count = fields.Integer(compute='_compute_recipient_count')
    
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
        self.ensure_one()
        
        numbers = [n.strip() for n in self.phone_numbers.split(',') if n.strip()]
        
        if not numbers:
            raise UserError(_('Please enter at least one phone number'))
        
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        sms_records = self.env['sms.sms']
        for number in numbers:
            try:
                normalized = self._normalize_phone(number)
                sms_records |= self.env['sms.sms'].create({
                    'number': normalized,
                    'body': self.body,
                    'su_sms_type': 'manual',
                    'su_department_id': admin.department_id.id if admin else False,
                })
            except:
                continue
        
        if not sms_records:
            raise UserError(_('No valid phone numbers'))
        
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Sent'),
                'message': _(f'{len(sms_records)} SMS queued'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _normalize_phone(self, number):
        number = re.sub(r'[^\d+]', '', number)
        if number.startswith('0'):
            return '+254' + number[1:]
        elif not number.startswith('+'):
            return '+254' + number
        return number