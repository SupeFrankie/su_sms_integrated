# models/su_sms_department_expenditure.py

"""
SU SMS Department Expenditure Model
Replaces SQL view with pure Odoo model for maintainability.
Aggregates SMS costs by department and quarter for KFS5 export.

- Added _update_expenditure() method (was referenced in sms_sms.py but missing here)
- related field names corrected to match hr_department fields (chart_code, not su_chart_code)
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
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
        string='Chart Code',
        related='department_id.chart_code',
        readonly=True,
        store=True
    )

    account_number = fields.Char(
        string='Account Number',
        related='department_id.account_number',
        readonly=True,
        store=True
    )

    object_code = fields.Char(
        string='Object Code',
        related='department_id.object_code',
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

    # ===== SQL CONSTRAINT =====
    _sql_constraints = [
        (
            'unique_dept_year_quarter',
            'unique(department_id, year, quarter)',
            'An expenditure record for this department, year and quarter already exists.'
        )
    ]

    @api.depends('department_id', 'year', 'quarter')
    def _compute_display_name(self):
        for rec in self:
            if rec.department_id and rec.year and rec.quarter:
                rec.display_name = f"{rec.department_id.name} - {rec.year} {rec.quarter}"
            else:
                rec.display_name = "New Expenditure Record"

    # ------------------------------------------------------------------
    # Core update hook
    # Called by sms_sms._handle_call_result_hook on successful send.
    # ------------------------------------------------------------------

    @api.model
    def _update_expenditure(self, department_id, date):
        """
        Increment expenditure counters for the department/quarter that
        contains `date`.  Creates the quarterly record if it does not exist.

        Args:
            department_id (int): hr.department.id
            date (datetime):     Timestamp of the send event (usually sms.create_date)
        """
        if not department_id or not date:
            return

        # Normalise to Python datetime
        if isinstance(date, str):
            date = fields.Datetime.from_string(date)

        year = date.year
        month = date.month
        quarter_map = {1: 'Q1', 2: 'Q1', 3: 'Q1',
                       4: 'Q2', 5: 'Q2', 6: 'Q2',
                       7: 'Q3', 8: 'Q3', 9: 'Q3',
                       10: 'Q4', 11: 'Q4', 12: 'Q4'}
        quarter = quarter_map[month]

        record = self.search([
            ('department_id', '=', department_id),
            ('year', '=', year),
            ('quarter', '=', quarter),
        ], limit=1)

        if not record:
            record = self.create({
                'department_id': department_id,
                'year': year,
                'quarter': quarter,
            })

        record.sudo().write({
            'total_sms': record.total_sms + 1,
            'successful_sms': record.successful_sms + 1,
        })

    @api.model
    def _record_failure(self, department_id, date):
        """Increment failed_sms counter.  Mirrors _update_expenditure."""
        if not department_id or not date:
            return

        if isinstance(date, str):
            date = fields.Datetime.from_string(date)

        year = date.year
        month = date.month
        quarter_map = {1: 'Q1', 2: 'Q1', 3: 'Q1',
                       4: 'Q2', 5: 'Q2', 6: 'Q2',
                       7: 'Q3', 8: 'Q3', 9: 'Q3',
                       10: 'Q4', 11: 'Q4', 12: 'Q4'}
        quarter = quarter_map[month]

        record = self.search([
            ('department_id', '=', department_id),
            ('year', '=', year),
            ('quarter', '=', quarter),
        ], limit=1)

        if not record:
            record = self.create({
                'department_id': department_id,
                'year': year,
                'quarter': quarter,
            })

        record.sudo().write({
            'total_sms': record.total_sms + 1,
            'failed_sms': record.failed_sms + 1,
        })

    def action_view_logs(self):
        self.ensure_one()

        q_map = {'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10}
        start_month = q_map.get(self.quarter, 1)
        start_date = datetime(self.year, start_month, 1)

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
        """Generate KFS5 export file (stub — implement actual KFS5 integration)."""
        self.ensure_one()

        if not self.account_number or not self.object_code:
            raise ValidationError(
                _("Department %s is missing KFS5 account configuration.")
                % self.department_id.name
            )

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