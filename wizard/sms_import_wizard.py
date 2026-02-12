# wizard/sms_import_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import csv
import io
import re


class SmsImportWizard(models.TransientModel):
    _name = 'sms.import.wizard'
    _description = 'Import SMS Recipients'

    import_file = fields.Binary(string='Upload CSV File', attachment=False)
    file_name = fields.Char(string='File Name')
    
    line_ids = fields.One2many(
        'sms.import.line',
        'wizard_id',
        string='Imported Contacts'
    )
    
    template_id = fields.Many2one('sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    
    state = fields.Selection([
        ('upload', 'Upload'),
        ('preview', 'Preview'),
        ('compose', 'Compose')
    ], default='upload')
    
    valid_count = fields.Integer(compute='_compute_counts')
    invalid_count = fields.Integer(compute='_compute_counts')
    
    @api.depends('line_ids.is_valid')
    def _compute_counts(self):
        for wizard in self:
            wizard.valid_count = len(wizard.line_ids.filtered('is_valid'))
            wizard.invalid_count = len(wizard.line_ids.filtered(lambda l: not l.is_valid))
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.body = self.template_id.body
    
    def action_download_template(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['first_name', 'last_name', 'phone_number'])
        writer.writerow(['John', 'Doe', '+254712345678'])
        writer.writerow(['Jane', 'Smith', '0723456789'])
        writer.writerow(['Alice', 'Wanjiru', '734567890'])
        
        csv_content = output.getvalue()
        output.close()
        csv_base64 = base64.b64encode(csv_content.encode('utf-8'))
        
        attachment = self.env['ir.attachment'].create({
            'name': 'sms_import_template.csv',
            'type': 'binary',
            'datas': csv_base64,
            'mimetype': 'text/csv',
            'public': False,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
    
    def action_parse_csv(self):
        self.ensure_one()
        
        if not self.import_file:
            raise UserError(_('Please upload a CSV file'))
        
        self.line_ids.unlink()
        
        decoded_data = base64.b64decode(self.import_file)
        try:
            content = decoded_data.decode('utf-8')
        except UnicodeDecodeError:
            content = decoded_data.decode('latin-1')
        
        csv_file = io.StringIO(content)
        reader = csv.DictReader(csv_file)
        
        headers = [h.strip().lower() for h in reader.fieldnames] if reader.fieldnames else []
        
        required = ['first_name', 'last_name']
        phone_fields = ['phone_number', 'mobile_number']
        
        if not any(field in headers for field in phone_fields):
            raise UserError(_('CSV must contain phone_number or mobile_number column'))
        
        lines = []
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items()}
            
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            phone = row.get('phone_number') or row.get('mobile_number', '')
            phone = phone.strip()
            
            is_valid = bool(phone)
            error_message = ''
            
            if not phone:
                is_valid = False
                error_message = 'Missing phone number'
            else:
                try:
                    phone = self._normalize_phone(phone)
                except:
                    is_valid = False
                    error_message = 'Invalid phone format'
            
            lines.append((0, 0, {
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone,
                'is_valid': is_valid,
                'error_message': error_message
            }))
        
        self.line_ids = lines
        self.state = 'preview'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sms.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_proceed_to_compose(self):
        self.ensure_one()
        
        if self.invalid_count > 0:
            raise UserError(_('Please fix invalid entries before proceeding'))
        
        if self.valid_count == 0:
            raise UserError(_('No valid contacts to send to'))
        
        self.state = 'compose'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sms.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_send_sms(self):
        self.ensure_one()
        
        if not self.body:
            raise UserError(_('Please enter a message'))
        
        valid_lines = self.line_ids.filtered('is_valid')
        
        if not valid_lines:
            raise UserError(_('No valid contacts to send to'))
        
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        sms_records = self.env['sms.sms']
        for line in valid_lines:
            name = f"{line.first_name} {line.last_name}".strip() or 'Unknown'
            sms_records |= self.env['sms.sms'].create({
                'number': line.phone_number,
                'body': self.body,
                'su_sms_type': 'adhoc',
                'su_department_id': admin.department_id.id if admin else False,
            })
        
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Queued'),
                'message': _(f'{len(sms_records)} SMS messages queued'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _normalize_phone(self, number):
        if not number:
            raise ValueError('Empty number')
        number = re.sub(r'[^\d+]', '', number)
        if number.startswith('0'):
            number = '+254' + number[1:]
        elif not number.startswith('+'):
            number = '+254' + number
        if not re.match(r'^\+254\d{9}$', number):
            raise ValueError('Invalid format')
        return number