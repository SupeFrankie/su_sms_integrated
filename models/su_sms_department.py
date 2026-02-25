# models/su_sms_department.py

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SuSmsDepartment(models.Model):
    _name = 'su.sms.department'
    _description = 'SU SMS Billing Department'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Department Name',
        required=True,
    )
    short_name = fields.Char(
        string='Short Name',
        required=True,
        help='Department abbreviation e.g. ICTD',
    )
    # KFS5 billing codes
    chart_code = fields.Char(
        string='Chart Code',
        default='SU',
        required=True,
    )
    account_number = fields.Char(
        string='Account Number',
        required=True,
        help='KFS5 financial account for SMS billing',
    )
    object_code = fields.Char(
        string='Object Code',
        required=True,
        help='KFS5 budget object code',
    )
    active = fields.Boolean(default=True)

    # Optionally link to hr.department for display
    hr_department_id = fields.Many2one(
        'hr.department',
        string='HR Department',
        ondelete='set null',
        help='Optional link to Odoo HR department record',
    )

    administrator_ids = fields.One2many(
        'su.sms.administrator',
        'department_id',
        string='Administrators',
    )
    administrator_count = fields.Integer(
        compute='_compute_administrator_count',
        string='Administrators',
    )

    message_ids = fields.One2many(
        'su.sms.message',
        'department_id',
        string='SMS Messages',
    )
    message_count = fields.Integer(
        compute='_compute_message_count',
        string='SMS Sent',
    )

    # Expenditure (computed from su.sms.detail)
    total_cost = fields.Float(
        compute='_compute_total_cost',
        string='Total Cost (KES)',
        digits=(10, 4),
    )
    kfs5_processed = fields.Boolean(
        string='KFS5 Processed',
        help='Whether this period\'s charges have been pushed to KFS5',
    )
    kfs5_processed_date = fields.Datetime(
        string='KFS5 Processed Date',
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    def _compute_administrator_count(self):
        for dept in self:
            dept.administrator_count = len(dept.administrator_ids)

    def _compute_message_count(self):
        data = self.env['su.sms.message'].read_group(
            [('department_id', 'in', self.ids)],
            ['department_id'],
            ['department_id'],
        )
        dept_counts = {d['department_id'][0]: d['department_id_count'] for d in data}
        for dept in self:
            dept.message_count = dept_counts.get(dept.id, 0)

    def _compute_total_cost(self):
        data = self.env['su.sms.detail'].read_group(
            [('department_id', 'in', self.ids), ('status', '=', 'sent')],
            ['department_id', 'cost:sum'],
            ['department_id'],
        )
        cost_map = {d['department_id'][0]: d['cost'] for d in data}
        for dept in self:
            dept.total_cost = cost_map.get(dept.id, 0.0)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    _sql_constraints = [
        ('account_number_unique', 'unique(account_number)',
         'Account Number must be unique across departments.'),
    ]

    @api.constrains('short_name')
    def _check_short_name(self):
        for dept in self:
            if len(dept.short_name) > 20:
                raise ValidationError(_('Short name must be 20 characters or fewer.'))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_messages(self):
        return {
            'name': _('SMS Messages - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'su.sms.message',
            'view_mode': 'list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id},
        }

    def action_mark_kfs5_processed(self):
        self.write({
            'kfs5_processed': True,
            'kfs5_processed_date': fields.Datetime.now(),
        })
