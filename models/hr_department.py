# models/hr_department.py


from odoo import models, fields, api

class HrDepartment(models.Model):
    _inherit = 'hr.department'
    
    # ===== KFS5 Billing Fields =====
    su_chart_code = fields.Char(
        string='Chart Code',
        default='SU',
        help="KFS5 Chart of Accounts Code"
    )
    
    su_account_number = fields.Char(
        string='Account Number',
        help="KFS5 Account Number for SMS billing"
    )
    
    su_object_code = fields.Char(
        string='Object Code',
        help="KFS5 Budget Object Code"
    )
    
    # ===== SMS Statistics =====
    su_sms_count = fields.Integer(
        string='SMS Sent',
        compute='_compute_sms_stats',
        help="Total SMS sent by this department"
    )
    
    su_sms_cost = fields.Float(
        string='SMS Cost (KES)',
        compute='_compute_sms_stats',
        help="Total SMS cost for this department"
    )
    
    su_sms_administrator_ids = fields.One2many(
        'sms.administrator',
        'department_id',
        string='SMS Administrators'
    )
    
    @api.depends('su_sms_administrator_ids')
    def _compute_sms_stats(self):
        for dept in self:
            logs = self.env['su.sms.log'].search([
                ('department_id', '=', dept.id)
            ])
            dept.su_sms_count = len(logs)
            dept.su_sms_cost = sum(logs.mapped('cost'))