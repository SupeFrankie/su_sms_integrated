# wizard/sms_staff_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests


class SmsStaffWizard(models.TransientModel):
    _name = 'sms.staff.wizard'
    _description = 'Staff SMS Wizard'
    
    # Filters (matches PHP system Section 4)
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help='Leave empty to send to all departments (System Admin only)'
    )
    gender = fields.Selection([
        ('all', 'All'),
        ('M', 'Male'),
        ('F', 'Female')
    ], string='Gender', default='all', required=True)
    
    category_id = fields.Many2one(
        'hr.employee.category',
        string='Category',
        help='Staff category (optional filter)'
    )
    
    job_status = fields.Selection([
        ('all', 'All'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Job Status', default='active', required=True)
    
    # Message
    template_id = fields.Many2one('sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    
    # Preview
    recipient_count = fields.Integer(
        string='Recipients',
        compute='_compute_recipients',
        store=False
    )
    
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
    
    def action_preview_recipients(self):
        """Show list of recipients before sending"""
        staff = self._fetch_staff_list()
        
        return {
            'name': _('Recipients Preview'),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.staff.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'preview_mode': True,
                'staff_list': staff
            }
        }
    
    def action_send_sms(self):
        """Send SMS to filtered staff"""
        self.ensure_one()
        
        # Check balance first
        balance = self.env['sms.balance'].get_balance()
        if balance.get('restricted'):
            raise UserError(_(balance.get('message')))
        
        # Fetch staff from web service
        staff_list = self._fetch_staff_list()
        
        if not staff_list:
            raise UserError(_('No staff members match your filters'))
        
        # Get current user's department for billing
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        if not admin or not admin.department_id:
            raise UserError(_(
                'Your user account is not linked to a department. '
                'Please contact the System Administrator.'
            ))
        
        # Create sms.sms records
        sms_records = self.env['sms.sms']
        for staff in staff_list:
            if staff.get('mobile'):
                sms_records |= self.env['sms.sms'].create({
                    'number': self._normalize_phone(staff['mobile']),
                    'body': self.body,
                    'partner_id': staff.get('partner_id'),  # Link to res.partner if exists
                    'su_sms_type': 'staff',
                    'su_department_id': admin.department_id.id,
                })
        
        # Queue for sending
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Queued'),
                'message': _(f'{len(sms_records)} SMS messages queued for sending'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _fetch_staff_list(self):
        """Call external web service to get staff"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'su_sms.webservice_base_url',
            'https://dataservice.strathmore.edu'
        )
        
        # Build query parameters
        params = {}
        
        if self.department_ids:
            params['department'] = ','.join(self.department_ids.mapped('name'))
        
        if self.gender != 'all':
            params['gender'] = self.gender
        
        if self.category_id:
            params['category'] = self.category_id.name
        
        if self.job_status != 'all':
            params['status'] = self.job_status
        
        # Call web service
        try:
            url = f'{base_url}/staff/getStaffBy'
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Transform to expected format
            staff_list = []
            for staff in data.get('staff', []):
                staff_list.append({
                    'name': f"{staff.get('first_name')} {staff.get('last_name')}",
                    'mobile': staff.get('mobile'),
                    'email': staff.get('email'),
                    'department': staff.get('department'),
                    'partner_id': self._get_or_create_partner(staff)
                })
            
            return staff_list
            
        except requests.exceptions.RequestException as e:
            raise UserError(_(f'Failed to fetch staff data: {e}'))
    
    def _get_or_create_partner(self, staff_data):
        """Link staff to res.partner if exists, create if needed"""
        partner = self.env['res.partner'].search([
            ('email', '=', staff_data.get('email'))
        ], limit=1)
        
        if not partner:
            partner = self.env['res.partner'].create({
                'name': f"{staff_data.get('first_name')} {staff_data.get('last_name')}",
                'email': staff_data.get('email'),
                'mobile': staff_data.get('mobile'),
                'is_company': False,
            })
        
        return partner.id
    
    def _normalize_phone(self, number):
        """Normalize phone number to +254 format"""
        if not number:
            return False
        
        # Remove spaces and dashes
        number = number.replace(' ', '').replace('-', '')
        
        # If starts with 0, replace with +254
        if number.startswith('0'):
            number = '+254' + number[1:]
        elif not number.startswith('+'):
            number = '+254' + number
        
        return number