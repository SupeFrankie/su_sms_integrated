# wizard/su_sms_compose.py

import base64
import csv
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SuSmsCompose(models.TransientModel):
    _name = 'su.sms.compose'
    _description = 'SU SMS Compose Wizard'

    # ------------------------------------------------------------------
    # Step 1: Type + Message
    # ------------------------------------------------------------------
    sms_type = fields.Selection([
        ('manual', 'Manual (Direct Numbers)'),
        ('adhoc', 'Ad Hoc (CSV Upload)'),
        ('staff', 'Staff SMS'),
        ('student', 'Student SMS'),
    ], string='SMS Type', required=True, default='manual')

    body = fields.Text(string='Message Body', required=True)

    administrator_id = fields.Many2one(
        'su.sms.administrator',
        string='Send As (Department)',
        required=True,
        default=lambda self: self._default_admin(),
    )
    department_id = fields.Many2one(
        'su.sms.department',
        related='administrator_id.department_id',
        string='Department',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Manual numbers
    # ------------------------------------------------------------------
    manual_numbers = fields.Text(
        string='Phone Numbers',
        help='Comma or newline separated phone numbers. E.g. +254727374660, 0712345678',
    )

    # ------------------------------------------------------------------
    # Ad Hoc CSV
    # ------------------------------------------------------------------
    csv_file = fields.Binary('CSV File')
    csv_filename = fields.Char('Filename')

    # ------------------------------------------------------------------
    # Staff filters
    # ------------------------------------------------------------------
    staff_department = fields.Char('Department')
    staff_gender = fields.Selection([
        ('all', 'All Genders'),
        ('M', 'Male'),
        ('F', 'Female'),
    ], default='all', string='Gender')
    staff_category = fields.Char('Category')
    staff_job_status = fields.Char('Job Status')

    # ------------------------------------------------------------------
    # Student filters
    # ------------------------------------------------------------------
    student_school = fields.Char('School')
    student_program = fields.Char('Program')
    student_course = fields.Char('Course')
    student_year = fields.Char('Year of Study')
    student_intake = fields.Char('Intake')
    include_students = fields.Boolean('Include Students', default=True)
    include_fathers = fields.Boolean('Include Fathers')
    include_mothers = fields.Boolean('Include Mothers')

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    preview_html = fields.Html(
        string='Recipients Preview',
        compute='_compute_preview',
        sanitize=False,
    )
    recipient_count = fields.Integer(
        compute='_compute_preview',
        string='Recipient Count',
    )

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def _default_admin(self):
        admin = self.env['su.sms.administrator'].search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ], limit=1)
        return admin.id if admin else False

    # ------------------------------------------------------------------
    # Preview compute
    # ------------------------------------------------------------------
    @api.depends('sms_type', 'manual_numbers', 'csv_file')
    def _compute_preview(self):
        for rec in self:
            numbers = rec._get_numbers_list()
            rec.recipient_count = len(numbers)
            if numbers:
                rows = ''.join(
                    f'<tr><td>{i + 1}</td><td>{n[0]}</td><td>{n[1]}</td></tr>'
                    for i, n in enumerate(numbers[:50])
                )
                more = f'<tr><td colspan="3">... and {len(numbers) - 50} more</td></tr>' if len(numbers) > 50 else ''
                rec.preview_html = (
                    f'<table class="table table-sm table-bordered">'
                    f'<thead><tr><th>#</th><th>Name</th><th>Number</th></tr></thead>'
                    f'<tbody>{rows}{more}</tbody></table>'
                )
            else:
                rec.preview_html = '<p class="text-muted">No recipients yet.</p>'

    def _get_numbers_list(self):
        """Return list of (name, number) tuples based on current sms_type."""
        if self.sms_type == 'manual':
            return self._parse_manual_numbers()
        elif self.sms_type == 'adhoc':
            return self._parse_csv_numbers()
        elif self.sms_type in ('staff', 'student'):
            # For webservice-based types, we can't preview without actual WS call
            # Return empty - the message will be built when sending
            return []
        return []

    def _parse_manual_numbers(self):
        if not self.manual_numbers:
            return []
        raw = self.manual_numbers.replace('\n', ',').replace(';', ',')
        return [('', n.strip()) for n in raw.split(',') if n.strip()]

    def _parse_csv_numbers(self):
        if not self.csv_file:
            return []
        try:
            data = base64.b64decode(self.csv_file)
            reader = csv.DictReader(io.StringIO(data.decode('utf-8', errors='replace')))
            results = []
            for row in reader:
                phone = (row.get('Phone Number') or row.get('phone_number')
                         or row.get('Phone') or row.get('phone') or '').strip()
                name = (row.get('Name') or row.get('name') or '').strip()
                if phone:
                    results.append((name, phone))
            return results
        except Exception as exc:
            _logger.warning("CSV parse error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Role-based access check
    # ------------------------------------------------------------------
    def _check_access(self):
        """Verify the user is allowed to send this SMS type."""
        user = self.env.user
        if user.has_group('su_sms_integrated.group_su_sms_manager'):
            return  # full access
        if self.sms_type == 'student' and not user.has_group(
            'su_sms_integrated.group_su_sms_faculty_admin'
        ):
            raise UserError(_("You do not have permission to send Student SMS."))
        if self.sms_type == 'staff' and not user.has_group(
            'su_sms_integrated.group_su_sms_staff_admin'
        ):
            raise UserError(_("You do not have permission to send Staff SMS."))

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------
    def action_send(self):
        self.ensure_one()
        self._check_access()

        if not self.body or not self.body.strip():
            raise UserError(_("Message body cannot be empty."))
        if not self.administrator_id:
            raise UserError(_("No SMS administrator profile found for your user. "
                               "Please ask your system administrator to set one up."))

        # Gather recipients
        if self.sms_type == 'manual':
            pairs = self._parse_manual_numbers()
        elif self.sms_type == 'adhoc':
            pairs = self._parse_csv_numbers()
        else:
            # staff / student - must be populated by webservice
            # For now raise; the real integration calls an external WS
            pairs = self._fetch_recipients_from_webservice()

        if not pairs:
            raise UserError(_("No valid phone numbers found. Please check your input."))

        # Create su.sms.message campaign record
        message = self.env['su.sms.message'].create({
            'body': self.body,
            'sms_type': self.sms_type,
            'administrator_id': self.administrator_id.id,
            'manual_numbers': self.manual_numbers,
            'csv_file': self.csv_file,
            'csv_filename': self.csv_filename,
            # Staff filters
            'staff_department': self.staff_department,
            'staff_gender': self.staff_gender,
            'staff_category': self.staff_category,
            'staff_job_status': self.staff_job_status,
            # Student filters
            'student_school': self.student_school,
            'student_program': self.student_program,
            'student_course': self.student_course,
            'student_year': self.student_year,
            'student_intake': self.student_intake,
            'include_students': self.include_students,
            'include_fathers': self.include_fathers,
            'include_mothers': self.include_mothers,
        })

        # Create detail lines
        detail_vals = [
            {
                'message_id': message.id,
                'recipient_name': name,
                'phone_number': number,
                'status': 'pending',
            }
            for name, number in pairs
        ]
        self.env['su.sms.detail'].create(detail_vals)

        # Trigger send
        message.action_send()

        return {
            'type': 'ir.actions.act_window',
            'name': _('SMS Campaign'),
            'res_model': 'su.sms.message',
            'res_id': message.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _fetch_recipients_from_webservice(self):
        """
        Placeholder for external web service integration.
        Returns list of (name, phone) tuples.

        Implement this to call your SU Data Web Service:
        - Staff: GET {WEBSERVICE_BASE_URL}/staff/getStaffBy?dept=...&gender=...
        - Student: GET {WEBSERVICE_BASE_URL}/student/getStudentsAcademic?school=...
        """
        _logger.info(
            "SU SMS: webservice fetch for type=%s dept=%s school=%s",
            self.sms_type, self.staff_department, self.student_school,
        )
        # TODO: implement real web service call
        # Example stub:
        # import requests
        # base_url = self.env['ir.config_parameter'].sudo().get_param('su_sms.webservice_base_url')
        # if self.sms_type == 'staff':
        #     response = requests.get(f'{base_url}/staff/getAllStaff', timeout=30)
        #     data = response.json()
        #     return [(r.get('name'), r.get('phone')) for r in data if r.get('phone')]
        raise UserError(_(
            "Web service integration is not yet configured.\n"
            "Please contact your system administrator to set up the "
            "SU Data Web Service connection (su_sms.webservice_base_url)."
        ))
