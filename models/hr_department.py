# models/hr_department.py


from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    short_name = fields.Char(string='Short Name')
    is_school = fields.Boolean(string='Is a School', default=False)

    administrator_id = fields.Many2one(
        'res.users',
        string='Primary SMS Admin'
    )

    # ===== KFS5 Billing Fields =====

    chart_code = fields.Char(
        string='Chart Code',
        default='SU',
        help="KFS5 Chart of Accounts Code"
    )

    account_number = fields.Char(
        string='Account Number',
        help="KFS5 Account Number for SMS billing"
    )

    object_code = fields.Char(
        string='Object Code',
        help="KFS5 Budget Object Code"
    )

    # ===== SMS Financial Tracking =====

    sms_credit_balance = fields.Float(
        string='Credit Balance',
        default=0.0,
        help="Prepaid SMS Balance"
    )

    sms_sent_this_month = fields.Integer(
        string='SMS Sent (Month)',
        compute='_compute_sms_stats',
        store=False
    )

    sms_cost_this_month = fields.Float(
        string='SMS Cost (Month)',
        compute='_compute_sms_stats',
        store=False,
        digits=(10, 2)
    )

    su_sms_administrator_ids = fields.One2many(
        'sms.administrator',
        'department_id',
        string='SMS Administrators'
    )

    @api.depends()
    def _compute_sms_stats(self):
        """
        Compute monthly SMS usage + cost.
        Safe even if su.sms.log is empty.
        """
        Log = self.env['su.sms.log']

        today = datetime.today()
        month_start = today.replace(day=1)

        for dept in self:
            logs = Log.search([
                ('department_id', '=', dept.id),
                ('create_date', '>=', month_start)
            ])

            dept.sms_sent_this_month = len(logs)
            dept.sms_cost_this_month = sum(logs.mapped('cost')) if logs else 0.0
