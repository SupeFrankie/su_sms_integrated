# models/su_sms_message.py

import base64
import csv
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SuSmsMessage(models.Model):
    _name = 'su.sms.message'
    _description = 'SU SMS Message Campaign'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # ------------------------------------------------------------------
    # Core fields
    # ------------------------------------------------------------------
    body = fields.Text(string='Message', required=True)
    sms_type = fields.Selection([
        ('adhoc', 'Ad Hoc (CSV Upload)'),
        ('student', 'Student SMS'),
        ('staff', 'Staff SMS'),
        ('manual', 'Manual (Direct Numbers)'),
    ], string='SMS Type', required=True, default='manual')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('done', 'Done'),
        ('partial', 'Partially Sent'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    administrator_id = fields.Many2one(
        'su.sms.administrator',
        string='Sent By',
        required=True,
        index=True,
        default=lambda self: self._default_administrator(),
    )
    department_id = fields.Many2one(
        'su.sms.department',
        related='administrator_id.department_id',
        store=True,
        string='Department',
        index=True,
    )
    detail_ids = fields.One2many(
        'su.sms.detail',
        'message_id',
        string='Recipients',
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    display_name = fields.Char(compute='_compute_display_name', store=True)
    recipient_count = fields.Integer(compute='_compute_stats', store=True)
    success_count = fields.Integer(compute='_compute_stats', store=True)
    failed_count = fields.Integer(compute='_compute_stats', store=True)
    total_cost = fields.Float(
        compute='_compute_stats', store=True, digits=(10, 4),
        string='Total Cost (KES)',
    )

    # ------------------------------------------------------------------
    # Filtering fields (for wizard - student/staff)
    # ------------------------------------------------------------------
    # Student filters
    student_school = fields.Char('School')
    student_program = fields.Char('Program')
    student_course = fields.Char('Course')
    student_year = fields.Char('Year of Study')
    student_intake = fields.Char('Intake')
    include_students = fields.Boolean('Include Students', default=True)
    include_fathers = fields.Boolean('Include Fathers')
    include_mothers = fields.Boolean('Include Mothers')

    # Staff filters
    staff_department = fields.Char('Staff Department')
    staff_gender = fields.Selection([
        ('all', 'All'), ('M', 'Male'), ('F', 'Female')
    ], default='all', string='Gender')
    staff_category = fields.Char('Category')
    staff_job_status = fields.Char('Job Status Type')

    # Manual / Ad Hoc
    manual_numbers = fields.Text(
        'Numbers',
        help='Comma-separated phone numbers (Manual mode)',
    )
    csv_file = fields.Binary('CSV File', help='CSV with Name,Phone Number columns')
    csv_filename = fields.Char('CSV Filename')

    # ------------------------------------------------------------------
    # KFS5 billing
    # ------------------------------------------------------------------
    kfs5_processed = fields.Boolean('KFS5 Processed')
    kfs5_processed_date = fields.Datetime('KFS5 Processed Date')

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def _default_administrator(self):
        admin = self.env['su.sms.administrator'].search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)
        return admin.id if admin else False

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('create_date', 'sms_type', 'administrator_id.name')
    def _compute_display_name(self):
        type_labels = dict(self._fields['sms_type'].selection)
        for rec in self:
            date_str = rec.create_date.strftime('%Y-%m-%d') if rec.create_date else 'Draft'
            type_label = type_labels.get(rec.sms_type, rec.sms_type)
            sender = rec.administrator_id.name or ''
            rec.display_name = f"{type_label} - {sender} - {date_str}"

    @api.depends('detail_ids.status', 'detail_ids.cost')
    def _compute_stats(self):
        for rec in self:
            details = rec.detail_ids
            rec.recipient_count = len(details)
            rec.success_count = len(details.filtered(lambda d: d.status == 'sent'))
            rec.failed_count = len(details.filtered(lambda d: d.status == 'failed'))
            rec.total_cost = sum(details.filtered(lambda d: d.status == 'sent').mapped('cost'))

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------
    def action_send(self):
        """Build sms.sms records from detail_ids and trigger send."""
        self.ensure_one()
        if self.state not in ('draft', 'failed'):
            raise UserError(_('Only draft or failed messages can be sent.'))
        if not self.detail_ids:
            raise UserError(_('No recipients. Please add recipients before sending.'))

        self.write({'state': 'sending'})

        # Build sms.sms outgoing records linked to this campaign
        sms_vals = []
        for detail in self.detail_ids.filtered(lambda d: d.status in ('pending', 'failed', 'draft')):
            if not detail.phone_number:
                continue
            sms_vals.append({
                'number': detail.phone_number,
                'body': self.body,
                'su_message_id': self.id,
                'record_company_id': self.env.company.id,
            })

        if not sms_vals:
            self.write({'state': 'failed'})
            raise UserError(_('No valid phone numbers found.'))

        sms_records = self.env['sms.sms'].create(sms_vals)

        # Update detail with uuid for result tracking
        sms_by_number = {s.number: s for s in sms_records}
        for detail in self.detail_ids:
            sms = sms_by_number.get(detail.phone_number)
            if sms:
                detail.sms_uuid = sms.uuid

        # Trigger send
        sms_records.send(unlink_failed=False, unlink_sent=True, raise_exception=False)
        self.write({'state': 'done'})
        return True

    def action_populate_from_csv(self):
        """Parse CSV and populate detail_ids."""
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_('Please upload a CSV file first.'))
        try:
            data = base64.b64decode(self.csv_file)
            reader = csv.DictReader(io.StringIO(data.decode('utf-8', errors='replace')))
        except Exception as exc:
            raise UserError(_('Could not parse CSV: %s', str(exc)))

        # Detect number column
        number_keys = ['Phone Number', 'phone_number', 'Phone', 'phone', 'Number', 'number']
        name_keys = ['Name', 'name', 'Full Name', 'full_name']

        vals_list = []
        for row in reader:
            phone = None
            for k in number_keys:
                if k in row and row[k]:
                    phone = row[k].strip()
                    break
            name = ''
            for k in name_keys:
                if k in row and row[k]:
                    name = row[k].strip()
                    break
            if phone:
                vals_list.append({
                    'message_id': self.id,
                    'recipient_name': name,
                    'phone_number': phone,
                    'status': 'pending',
                })

        if not vals_list:
            raise UserError(_('No valid phone numbers found in CSV. Expected columns: Name, Phone Number'))

        # Remove old pending details, keep sent/failed
        self.detail_ids.filtered(lambda d: d.status == 'pending').unlink()
        self.env['su.sms.detail'].create(vals_list)
        return True

    def action_populate_from_manual(self):
        """Parse comma-separated numbers."""
        self.ensure_one()
        if not self.manual_numbers:
            raise UserError(_('Please enter at least one phone number.'))
        numbers = [n.strip() for n in self.manual_numbers.replace('\n', ',').split(',') if n.strip()]
        if not numbers:
            raise UserError(_('No valid numbers found.'))
        self.detail_ids.filtered(lambda d: d.status == 'pending').unlink()
        vals_list = [
            {'message_id': self.id, 'phone_number': n, 'status': 'pending'}
            for n in numbers
        ]
        self.env['su.sms.detail'].create(vals_list)
        return True

    def _update_department_expenditure(self, detail):
        """Called from sms_sms._handle_call_result_hook on success."""
        # This is intentionally lightweight - detail already has cost from AT response
        _logger.info(
            'SU SMS expenditure: dept=%s cost=%s for message=%s',
            self.department_id.name, detail.cost, self.id,
        )

    def action_mark_kfs5(self):
        self.write({'kfs5_processed': True, 'kfs5_processed_date': fields.Datetime.now()})

    def action_view_recipients(self):
        return {
            'name': _('Recipients'),
            'type': 'ir.actions.act_window',
            'res_model': 'su.sms.detail',
            'view_mode': 'list',
            'domain': [('message_id', '=', self.id)],
        }
