# wizard/su_sms_compose.py


"""
SU SMS Compose Wizard.

Handles all 4 SMS types:
  manual  - comma/newline separated phone numbers
  adhoc   - CSV upload (firstname, lastname, phone_number, mobile_number)
  staff   - fetch from juba.strathmore.edu data service with HR filters
  student - fetch from juba.strathmore.edu data service with academic filters

Credit balance enforcement (AT balance checked before every send):
  balance <= 0          - ALL users blocked
  balance < 15,000 KES  - only group_su_sms_manager can send
  balance < 80 KES      - warning logged, send still allowed for managers

THE FIX: department_id must not exist as Many2one in this wizard
at all - not as related=, not as compute=. A Many2one field in a
TransientModel form view is serialised as a dict by Owl, and that dict
poisons all subsequent onchange calls.

Replace with department_name (Char), a plain string that is never
involved in the Selection cache validation path.
==========================================================================
"""

import base64
import csv
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.su_sms_integrated.tools.webservice import SuSmsWebService

_logger = logging.getLogger(__name__)


class SuSmsCompose(models.TransientModel):
    _name = 'su.sms.compose'
    _description = 'SU SMS Compose Wizard'

    # ------------------------------------------------------------------
    # Type + Message
    # ------------------------------------------------------------------
    sms_type = fields.Selection([
        ('manual',  'Manual (Direct Numbers)'),
        ('adhoc',   'Ad Hoc (CSV Upload)'),
        ('staff',   'Staff SMS'),
        ('student', 'Student SMS'),
    ], string='SMS Type', required=True, default='manual')

    body = fields.Text(string='Message Body', required=True)

    administrator_id = fields.Many2one(
        'su.sms.administrator',
        string='Send As (Department)',
        required=True,
        default=lambda self: self._default_admin(),
    )

    # department_name (Char) shows the same information safely because:
    #   • Char.convert_to_cache receives a string, never a dict
    #   • It cannot be confused with a Selection field's cache path
    #   • The view uses this field for display only (readonly)
    
    department_name = fields.Char(
        string='Department',
        compute='_compute_department_name',
        store=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Manual numbers
    # ------------------------------------------------------------------
    manual_numbers = fields.Text(
        string='Phone Numbers',
        help='Comma or newline separated. E.g. +254727374660, 0712345678',
    )

    # ------------------------------------------------------------------
    # Ad Hoc CSV
    # ------------------------------------------------------------------
    csv_file     = fields.Binary('CSV File')
    csv_filename = fields.Char('Filename')

    # ------------------------------------------------------------------
    # Staff filters
    # ------------------------------------------------------------------
    staff_department = fields.Char(
        'Department Filter',
        help='Leave blank to fetch all departments. Staff Admins are '
             'automatically scoped to their own department.',
    )
    staff_gender = fields.Selection([
        ('all', 'All Genders'),
        ('M',   'Male'),
        ('F',   'Female'),
    ], default='all', string='Gender')
    staff_category   = fields.Char('Category')
    staff_job_status = fields.Char('Job Status Type')

    # ------------------------------------------------------------------
    # Student filters
    # ------------------------------------------------------------------
    student_school           = fields.Char('School')
    student_program          = fields.Char('Program')
    student_course           = fields.Char('Course')
    student_year             = fields.Char('Year of Study')
    student_intake           = fields.Char('Intake')
    student_modular          = fields.Boolean(
        'Modular Programme',
        help='Use modular endpoint (enrolment period + module) instead of '
             'academic year',
    )
    student_enrolment_period = fields.Char('Enrolment Period')
    student_module           = fields.Char('Module')
    include_students         = fields.Boolean('Include Students', default=True)
    include_fathers          = fields.Boolean('Include Fathers')
    include_mothers          = fields.Boolean('Include Mothers')

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
    # Computed: department_name (Char - safe for onchange)
    # ------------------------------------------------------------------
    @api.depends('administrator_id')
    def _compute_department_name(self):
        for rec in self:
            dept = rec.administrator_id.department_id
            rec.department_name = dept.name if dept else ''

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    @api.depends('sms_type', 'manual_numbers', 'csv_file')
    def _compute_preview(self):
        for rec in self:
            numbers = []
            if rec.sms_type == 'manual':
                numbers = rec._parse_manual_numbers()
            elif rec.sms_type == 'adhoc':
                numbers = rec._parse_csv_numbers()

            rec.recipient_count = len(numbers)
            if numbers:
                rows = ''.join(
                    f'<tr><td>{i + 1}</td><td>{n[0]}</td><td>{n[1]}</td></tr>'
                    for i, n in enumerate(numbers[:50])
                )
                more = (
                    f'<tr><td colspan="3" class="text-muted">'
                    f'… and {len(numbers) - 50} more</td></tr>'
                    if len(numbers) > 50 else ''
                )
                rec.preview_html = (
                    '<table class="table table-sm table-bordered">'
                    '<thead><tr><th>#</th><th>Name</th><th>Number</th></tr></thead>'
                    f'<tbody>{rows}{more}</tbody></table>'
                )
            elif rec.sms_type in ('staff', 'student'):
                rec.preview_html = (
                    '<p class="text-info">'
                    '<i class="fa fa-info-circle"/> '
                    'Recipients will be fetched from the web service when you '
                    'click <strong>Send SMS</strong>.'
                    '</p>'
                )
            else:
                rec.preview_html = '<p class="text-muted">No recipients yet.</p>'

    # ------------------------------------------------------------------
    # Number parsers
    # ------------------------------------------------------------------
    def _parse_manual_numbers(self):
        if not self.manual_numbers:
            return []
        raw = self.manual_numbers.replace('\n', ',').replace(';', ',')
        return [('', n.strip()) for n in raw.split(',') if n.strip()]

    def _parse_csv_numbers(self):
        """
        Supports new template (firstname, lastname, phone_number, mobile_number)
        and legacy format (Name, Phone Number).
        phone_number is preferred; mobile_number used as fallback if blank.
        """
        if not self.csv_file:
            return []
        try:
            data   = base64.b64decode(self.csv_file)
            reader = csv.DictReader(
                io.StringIO(data.decode('utf-8', errors='replace'))
            )
            results = []
            for row in reader:
                firstname = (
                    row.get('firstname') or row.get('first_name') or ''
                ).strip()
                lastname = (
                    row.get('lastname') or row.get('last_name') or ''
                ).strip()
                if firstname or lastname:
                    name = f"{firstname} {lastname}".strip()
                else:
                    name = (row.get('Name') or row.get('name') or '').strip()

                phone = (
                    row.get('phone_number') or
                    row.get('Phone Number') or
                    row.get('Phone') or
                    row.get('phone') or ''
                ).strip()
                if not phone:
                    phone = (
                        row.get('mobile_number') or
                        row.get('Mobile Number') or
                        row.get('mobile') or ''
                    ).strip()

                if phone:
                    results.append((name, phone))
            return results
        except Exception as exc:
            _logger.warning("SU SMS CSV parse error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # CSV template download
    # ------------------------------------------------------------------
    def action_download_csv_template(self):
        return {
            'type':   'ir.actions.act_url',
            'url':    '/su_sms/adhoc_template.csv',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Internal helper: get actual department record (never in onchange)
    # ------------------------------------------------------------------
    def _get_department(self):
        """Use this inside action methods only - never in computed fields."""
        return self.administrator_id.department_id

    # ------------------------------------------------------------------
    # Role-based access check
    # ------------------------------------------------------------------
    def _check_sms_access(self):
        user       = self.env.user
        is_manager = user.has_group('su_sms_integrated.group_su_sms_manager')

        if self.sms_type == 'student' and not user.has_group(
            'su_sms_integrated.group_su_sms_faculty_admin'
        ):
            raise UserError(_("You do not have permission to send Student SMS."))

        if self.sms_type == 'staff' and not user.has_group(
            'su_sms_integrated.group_su_sms_staff_admin'
        ):
            raise UserError(_("You do not have permission to send Staff SMS."))

        if (self.sms_type == 'staff'
                and not is_manager
                and not user.has_group('su_sms_integrated.group_su_sms_admin')
                and self.administrator_id.department_id
                and self.staff_department):
            dept_short = self.administrator_id.department_id.short_name
            if self.staff_department != dept_short:
                raise UserError(_(
                    "Staff Administrators can only send SMS to their own "
                    "department (%s).",
                    dept_short,
                ))

    # ------------------------------------------------------------------
    # Credit balance enforcement
    # ------------------------------------------------------------------
    def _enforce_credit_balance(self):
        cfg = self.env['ir.config_parameter'].sudo()
        try:
            icts_threshold = float(
                cfg.get_param('su_sms.icts_threshold', '15000')
            )
            min_credit = float(
                cfg.get_param('su_sms.minimum_credit', '80')
            )
        except (ValueError, TypeError):
            icts_threshold, min_credit = 15000.0, 80.0

        try:
            balance_str = self.env.company._get_at_balance()
            parts       = str(balance_str).split()
            balance     = float(parts[-1]) if parts else 0.0
        except Exception as exc:
            _logger.warning(
                "SU SMS: could not verify AT balance before send: %s", exc
            )
            return  # Don't block if balance endpoint unreachable

        is_manager = self.env.user.has_group(
            'su_sms_integrated.group_su_sms_manager'
        )

        if balance <= 0:
            raise UserError(_(
                "The Africa's Talking credit balance is KES 0.00.\n"
                "SMS sending has been disabled until the account is topped up.\n"
                "Please contact ICT Services."
            ))

        if balance < icts_threshold and not is_manager:
            raise UserError(_(
                "The Africa's Talking balance (KES %.2f) is below the minimum "
                "operational threshold (KES %.2f).\n"
                "Only System Administrators can send SMS at this time.\n"
                "Please contact ICT Services to top up the account.",
                balance, icts_threshold,
            ))

        if balance < min_credit:
            _logger.warning(
                "SU SMS: AT balance KES %.2f is below the low-balance warning "
                "level (KES %.2f). Consider topping up.",
                balance, min_credit,
            )

    # ------------------------------------------------------------------
    # Staff department auto-scoping
    # ------------------------------------------------------------------
    def _resolve_staff_department_filter(self):
        user       = self.env.user
        is_manager = user.has_group('su_sms_integrated.group_su_sms_manager')
        is_admin   = user.has_group('su_sms_integrated.group_su_sms_admin')

        if not is_manager and not is_admin:
            dept = self.administrator_id.department_id
            return dept.short_name if dept else self.staff_department or None

        return self.staff_department or None

    # ------------------------------------------------------------------
    # Web service fetch
    # ------------------------------------------------------------------
    def _fetch_recipients_from_webservice(self):
        ws = SuSmsWebService(self.env)

        if self.sms_type == 'staff':
            return ws.get_staff(
                department=self._resolve_staff_department_filter(),
                gender=self.staff_gender,
                category=self.staff_category    or None,
                job_status=self.staff_job_status or None,
            )

        if self.sms_type == 'student':
            return ws.get_students(
                school=self.student_school                     or None,
                program=self.student_program                   or None,
                course=self.student_course                     or None,
                student_year=self.student_year                 or None,
                enrolment_period=self.student_enrolment_period or None,
                module=self.student_module                     or None,
                intake=self.student_intake                     or None,
                include_students=self.include_students,
                include_fathers=self.include_fathers,
                include_mothers=self.include_mothers,
                modular=self.student_modular,
            )

        raise UserError(
            _("Unknown SMS type '%s' for web service fetch.", self.sms_type)
        )

    # ------------------------------------------------------------------
    # Main send action
    # ------------------------------------------------------------------
    def action_send(self):
        self.ensure_one()
        self._check_sms_access()

        if not self.body or not self.body.strip():
            raise UserError(_("Message body cannot be empty."))
        if not self.administrator_id:
            raise UserError(_(
                "No SMS administrator profile found for your user. "
                "Please ask your system administrator to create one."
            ))

        self._enforce_credit_balance()

        if self.sms_type == 'manual':
            pairs = self._parse_manual_numbers()
        elif self.sms_type == 'adhoc':
            pairs = self._parse_csv_numbers()
        else:
            pairs = self._fetch_recipients_from_webservice()

        if not pairs:
            raise UserError(
                _("No valid phone numbers found. Please check your input.")
            )

        message = self.env['su.sms.message'].create({
            'body':             self.body,
            'sms_type':         self.sms_type,
            'administrator_id': self.administrator_id.id,
            'manual_numbers':   self.manual_numbers,
            'csv_file':         self.csv_file,
            'csv_filename':     self.csv_filename,
            'staff_department': self.staff_department,
            'staff_gender':     self.staff_gender,
            'staff_category':   self.staff_category,
            'staff_job_status': self.staff_job_status,
            'student_school':   self.student_school,
            'student_program':  self.student_program,
            'student_course':   self.student_course,
            'student_year':     self.student_year,
            'student_intake':   self.student_intake,
            'include_students': self.include_students,
            'include_fathers':  self.include_fathers,
            'include_mothers':  self.include_mothers,
        })

        self.env['su.sms.detail'].create([
            {
                'message_id':     message.id,
                'recipient_name': name,
                'phone_number':   number,
                'status':         'pending',
            }
            for name, number in pairs
        ])

        message.action_send()

        return {
            'type':      'ir.actions.act_window',
            'name':      _('SMS Campaign'),
            'res_model': 'su.sms.message',
            'res_id':    message.id,
            'view_mode': 'form',
            'target':    'current',
        }