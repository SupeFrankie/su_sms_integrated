# models/su_sms_department_expenditure.py


"""
    SU SMS Department Expenditure Model
    Replaces SQL view with pure Odoo model for maintainability
    Aggregates SMS costs by department and quarter for KFS5 export
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import calendar


class SuSmsDepartmentExpenditure(models.Model):
    _name = 'su.sms.department.expenditure'
    _description = 'Department SMS Expenditure (Quarterly)'
    _order = 'year desc, quarter desc, department_id'
    _rec_name = 'display_name'
    
    # ===== CORE FIELDS =====
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    year = fields.Integer(
        string='Year',
        required=True,
        index=True
    )
    
    quarter = fields.Selection([
        ('Q1', 'Q1 (Jan-Mar)'),
        ('Q2', 'Q2 (Apr-Jun)'),
        ('Q3', 'Q3 (Jul-Sep)'),
        ('Q4', 'Q4 (Oct-Dec)'),
    ], string='Quarter', required=True, index=True)
    
    display_name = fields.Char(
        string='Period',
        compute='_compute_display_name',
        store=True
    )
    
    # ===== FINANCIAL REFERENCE FIELDS (Updated Related Fields) =====
    chart_code = fields.Char(
        string='Chart Code',
        related='department_id.chart_code',  # FIXED: was su_chart_code
        readonly=True,
        store=True
    )
    
    account_number = fields.Char(
        string='Account Number',
        related='department_id.account_number', # FIXED: was su_account_number
        readonly=True,
        store=True
    )
    
    object_code = fields.Char(
        string='Object Code',
        related='department_id.object_code', # FIXED: was su_object_code
        readonly=True,
        store=True
    )
    
    # ===== AGGREGATED STATISTICS =====
    total_sms = fields.Integer(string='Total SMS', default=0)
    successful_sms = fields.Integer(string='Successful', default=0)
    failed_sms = fields.Integer(string='Failed', default=0)
    total_cost = fields.Float(string='Total Cost (KES)', default=0.0, digits=(10, 2))
    
    # ===== KFS5 EXPORT STATUS =====
    kfs5_processed = fields.Boolean(string='Exported to KFS5', default=False, index=True)
    kfs5_batch_id = fields.Char(string='KFS5 Batch ID', readonly=True)
    kfs5_processed_date = fields.Datetime(string='Export Date', readonly=True)
    kfs5_processed_by = fields.Many2one('res.users', string='Exported By', readonly=True)

    @api.depends('department_id', 'year', 'quarter')
    def _compute_display_name(self):
        for rec in self:
            if rec.department_id and rec.year and rec.quarter:
                rec.display_name = f"{rec.department_id.name} - {rec.year} {rec.quarter}"
            else:
                rec.display_name = "New Expenditure Record"

    def action_view_logs(self):
        self.ensure_one()
        
        # Calculate start/end date for the quarter
        q_map = {'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10}
        start_month = q_map.get(self.quarter, 1)
        start_date = datetime(self.year, start_month, 1)
        
        # End date is 3 months later
        if start_month + 3 > 12:
            end_date = datetime(self.year + 1, 1, 1)
        else:
            end_date = datetime(self.year, start_month + 3, 1)
            
        return {
            'name': _('SMS Logs (%s %s)') % (self.year, self.quarter),
            'type': 'ir.actions.act_window',
            'res_model': 'su.sms.log',
            'view_mode': 'list,form',
            'domain': [
                ('department_id', '=', self.department_id.id),
                ('create_date', '>=', start_date),
                ('create_date', '<', end_date),
            ],
            'context': {'create': False},
        }
    
    def action_export_to_kfs5(self):
        """
        Generate KFS5 export file
        This is a placeholder - actual implementation depends on KFS5 integration
        """
        self.ensure_one()
        
        if not self.account_number or not self.object_code:
            raise ValidationError(
                _("Department %s is missing KFS5 account configuration") %
                self.department_id.name
            )
        
        # TODO: Implement actual KFS5 export logic
        # For now, just mark as processed
        batch_id = f"SMS-{self.year}-{self.quarter}-{self.id}"
        
        self.write({
            'kfs5_processed': True,
            'kfs5_batch_id': batch_id,
            'kfs5_processed_date': fields.Datetime.now(),
            'kfs5_processed_by': self.env.user.id,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Expenditure exported to KFS5. Batch ID: %s') % batch_id,
                'type': 'success',
                'sticky': False,
            }
        }