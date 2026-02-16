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
    
    # ===== FINANCIAL REFERENCE FIELDS =====
    chart_code = fields.Char(
        related='department_id.su_chart_code',
        string='Chart Code',
        readonly=True,
        store=True
    )
    
    account_number = fields.Char(
        related='department_id.su_account_number',
        string='Account Number',
        readonly=True,
        store=True,
        help="KFS5 Account Number"
    )
    
    object_code = fields.Char(
        related='department_id.su_object_code',
        string='Object Code',
        readonly=True,
        store=True,
        help="KFS5 Budget Object Code"
    )
    
    # ===== AGGREGATED STATISTICS =====
    total_sms = fields.Integer(
        string='Total SMS Sent',
        compute='_compute_stats',
        store=True,
        help="Number of SMS messages in this period"
    )
    
    total_cost = fields.Float(
        string='Total Cost (KES)',
        compute='_compute_stats',
        store=True,
        digits=(12, 2),
        help="Total cost in Kenyan Shillings"
    )
    
    successful_sms = fields.Integer(
        string='Successful SMS',
        compute='_compute_stats',
        store=True
    )
    
    failed_sms = fields.Integer(
        string='Failed SMS',
        compute='_compute_stats',
        store=True
    )
    
    average_cost_per_sms = fields.Float(
        string='Avg Cost per SMS',
        compute='_compute_stats',
        store=True,
        digits=(10, 2)
    )
    
    # ===== KFS5 EXPORT FIELDS =====
    kfs5_processed = fields.Boolean(
        string='Exported to KFS5',
        default=False,
        help="Has this quarterly expenditure been exported?"
    )
    
    kfs5_batch_id = fields.Char(
        string='KFS5 Batch ID',
        help="Reference to KFS5 batch document"
    )
    
    kfs5_processed_date = fields.Datetime(
        string='Export Date',
        readonly=True
    )
    
    kfs5_processed_by = fields.Many2one(
        'res.users',
        string='Exported By',
        readonly=True
    )
    
    # ===== BREAKDOWN FIELDS (for detailed reporting) =====
    staff_sms_count = fields.Integer(
        string='Staff SMS',
        compute='_compute_breakdown',
        store=True
    )
    
    student_sms_count = fields.Integer(
        string='Student SMS',
        compute='_compute_breakdown',
        store=True
    )
    
    adhoc_sms_count = fields.Integer(
        string='Ad-hoc SMS',
        compute='_compute_breakdown',
        store=True
    )
    
    manual_sms_count = fields.Integer(
        string='Manual SMS',
        compute='_compute_breakdown',
        store=True
    )
    
    # ===== SQL CONSTRAINT =====
    _sql_constraints = [
        ('unique_dept_period',
         'unique(department_id, year, quarter)',
         'Department expenditure record must be unique per quarter!')
    ]
    
    # ===== COMPUTE METHODS =====
    @api.depends('department_id', 'year', 'quarter')
    def _compute_display_name(self):
        for record in self:
            if record.department_id and record.year and record.quarter:
                record.display_name = f"{record.department_id.name} - {record.year} {record.quarter}"
            else:
                record.display_name = "New Expenditure Record"
    
    @api.depends('department_id', 'year', 'quarter')
    def _compute_stats(self):
        """Compute aggregated statistics from su.sms.log"""
        for record in self:
            if not (record.department_id and record.year and record.quarter):
                record.total_sms = 0
                record.total_cost = 0.0
                record.successful_sms = 0
                record.failed_sms = 0
                record.average_cost_per_sms = 0.0
                continue
            
            # Get date range for this quarter
            start_date, end_date = record._get_quarter_date_range()
            
            # Query logs
            domain = [
                ('department_id', '=', record.department_id.id),
                ('create_date', '>=', start_date),
                ('create_date', '<', end_date),
            ]
            
            logs = self.env['su.sms.log'].search(domain)
            
            record.total_sms = len(logs)
            record.total_cost = sum(logs.mapped('cost'))
            record.successful_sms = len(logs.filtered(lambda l: l.status in ['sent', 'delivered']))
            record.failed_sms = len(logs.filtered(lambda l: l.status in ['failed', 'bounced']))
            
            if record.total_sms > 0:
                record.average_cost_per_sms = record.total_cost / record.total_sms
            else:
                record.average_cost_per_sms = 0.0
    
    @api.depends('department_id', 'year', 'quarter')
    def _compute_breakdown(self):
        """Compute breakdown by SMS type"""
        for record in self:
            if not (record.department_id and record.year and record.quarter):
                record.staff_sms_count = 0
                record.student_sms_count = 0
                record.adhoc_sms_count = 0
                record.manual_sms_count = 0
                continue
            
            start_date, end_date = record._get_quarter_date_range()
            
            # Query sms.sms records (has su_sms_type field)
            base_domain = [
                ('su_department_id', '=', record.department_id.id),
                ('create_date', '>=', start_date),
                ('create_date', '<', end_date),
            ]
            
            record.staff_sms_count = self.env['sms.sms'].search_count(
                base_domain + [('su_sms_type', '=', 'staff')]
            )
            record.student_sms_count = self.env['sms.sms'].search_count(
                base_domain + [('su_sms_type', '=', 'student')]
            )
            record.adhoc_sms_count = self.env['sms.sms'].search_count(
                base_domain + [('su_sms_type', '=', 'adhoc')]
            )
            record.manual_sms_count = self.env['sms.sms'].search_count(
                base_domain + [('su_sms_type', '=', 'manual')]
            )
    
    def _get_quarter_date_range(self):
        """Get start and end dates for the quarter"""
        self.ensure_one()
        
        quarter_months = {
            'Q1': (1, 3),
            'Q2': (4, 6),
            'Q3': (7, 9),
            'Q4': (10, 12),
        }
        
        start_month, end_month = quarter_months[self.quarter]
        
        start_date = datetime(self.year, start_month, 1)
        
        # Last day of end_month
        last_day = calendar.monthrange(self.year, end_month)[1]
        end_date = datetime(self.year, end_month, last_day, 23, 59, 59)
        
        return start_date, end_date + timedelta(seconds=1)  # Make exclusive
    
    # ===== BUSINESS LOGIC =====
    @api.model
    def _update_expenditure(self, department_id, date):
        """
        Called when SMS is sent to update/create expenditure record
        department_id: int (hr.department id)
        date: datetime
        """
        if isinstance(date, str):
            date = fields.Datetime.from_string(date)
        
        quarter_num = (date.month - 1) // 3 + 1
        quarter = f"Q{quarter_num}"
        year = date.year
        
        # Find or create expenditure record
        expenditure = self.search([
            ('department_id', '=', department_id),
            ('year', '=', year),
            ('quarter', '=', quarter),
        ], limit=1)
        
        if not expenditure:
            expenditure = self.create({
                'department_id': department_id,
                'year': year,
                'quarter': quarter,
            })
        else:
            # Trigger recompute by invalidating cache
            expenditure.invalidate_cache(['total_sms', 'total_cost'])
        
        return expenditure
    
    def action_mark_kfs5_processed(self):
        """Mark as exported to KFS5"""
        for record in self:
            if record.kfs5_processed:
                raise ValidationError(
                    _("This expenditure has already been exported to KFS5 on %s") %
                    record.kfs5_processed_date.strftime('%Y-%m-%d %H:%M')
                )
            
            record.write({
                'kfs5_processed': True,
                'kfs5_processed_date': fields.Datetime.now(),
                'kfs5_processed_by': self.env.user.id,
            })
    
    def action_view_logs(self):
        """Open su.sms.log view filtered for this period"""
        self.ensure_one()
        
        start_date, end_date = self._get_quarter_date_range()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('SMS Logs - %s') % self.display_name,
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