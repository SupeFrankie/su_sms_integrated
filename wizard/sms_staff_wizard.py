# wizard/sms_staff_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import os


class SmsStaffWizard(models.TransientModel):
    _name = 'sms.staff.wizard'
    _description = 'Staff SMS Wizard'
    
    department_ids = fields.Many2many('hr.department', string='Departments')
    gender = fields.Selection([
        ('all', 'All'),
        ('M', 'Male'),
        ('F', 'Female')
    ], default='all', required=True)
    category_id = fields.Many2one('hr.employee.category', string='Category')
    job_status = fields.Selection([
        ('all', 'All'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], default='active', required=True)
    
    template_id = fields.Many2one('su.sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    recipient_count = fields.Integer(compute='_compute_recipients')
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.body = self.template_id.body
    
    @api.depends('department_ids', 'gender', 'category_id', 'job_status')
    def _compute_recipients(self):
        for wizard in self:
            try:
                staff = wizard._fetch_staff_list()
                wizard.recipient_count = len(staff)
            except:
                wizard.recipient_count = 0
    
    def action_send_sms(self):
        self.ensure_one()
        
        staff_list = self._fetch_staff_list()
        
        if not staff_list:
            raise UserError(_('No staff members match filters'))
        
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        if not admin or not admin.department_id:
            raise UserError(_('Your account is not linked to a department'))
        
        sms_records = self.env['sms.sms']
        for staff in staff_list:
            if staff.get('mobile'):
                sms_records |= self.env['sms.sms'].create({
                    'number': self._normalize_phone(staff['mobile']),
                    'body': self.body,
                    'su_sms_type': 'staff',
                    'su_department_id': admin.department_id.id,
                })
        
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Queued'),
                'message': _(f'{len(sms_records)} SMS queued'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _fetch_staff_list(self):
        base_url = os.getenv('STAFF_DATASERVICE_URL', 'http://localhost')
        params = {}
        
        if self.department_ids:
            params['department'] = ','.join(self.department_ids.mapped('name'))
        if self.gender != 'all':
            params['gender'] = self.gender
        if self.category_id:
            params['category'] = self.category_id.name
        if self.job_status != 'all':
            params['status'] = self.job_status
        
        try:
            url = f'{base_url}/staff/getStaffBy'
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('staff', [])
        except:
            return []
    
    def _normalize_phone(self, number):
        if not number:
            return False
        number = number.replace(' ', '').replace('-', '')
        if number.startswith('0'):
            return '+254' + number[1:]
        elif not number.startswith('+'):
            return '+254' + number
        return number