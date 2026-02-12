# wizard/sms_import_line.py

from odoo import models, fields

class SmsImportLine(models.TransientModel):
    _name = 'sms.import.line'
    _description = 'SMS Import Line'
    
    wizard_id = fields.Many2one('sms.import.wizard', required=True, ondelete='cascade')
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    phone_number = fields.Char(string='Phone Number', required=True)
    is_valid = fields.Boolean(default=True)
    error_message = fields.Char()