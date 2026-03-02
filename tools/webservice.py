# tools/webservice.py


"""
Strathmore University Data Web Service client.

Base URLs (stored in ir.config_parameter):
  su_sms.student_dataservice_url  ->  https://juba.strathmore.edu/dataservice/students/
  su_sms.staff_dataservice_url    ->  https://juba.strathmore.edu/dataservice/staff/getStaffByUsername/

From the student base we construct:
  {base}getStudentsAcademic?school=X&program=Y&...
  {base}getStudentsModular?school=X&program=Y&...

From the staff URL we derive the staff base:
  https://juba.strathmore.edu/dataservice/staff/
  -> {base}getAllStaff
  -> {base}getStaffBy?department=X&gender=Y&...

The service returns JSON arrays.  Field name normalisation handles both camelCase
and underscore_case variants seen in Strathmore web services.

RESPONSE SHAPE (expected from juba.strathmore.edu):
  Students:
    [
      { "name": "John Doe",   "phone": "0727...", "fatherPhone": "0712...", "motherPhone": "0733..." },
      ...
    ]
  Staff:
    [
      { "firstName": "Jane", "lastName": "Doe", "mobileNumber": "0727...", "department": "ICTD" },
      ...
    ]

If the shape differs, adjust _parse_student_record / _parse_staff_record below.
"""

import logging
import urllib.parse

import requests
from requests.exceptions import RequestException

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Field name candidates to try in order (student phone fields)
_STUDENT_PHONE_FIELDS    = ('phone', 'mobilePhone', 'phoneNumber', 'mobile', 'phone_number')
_STUDENT_FNAME_FIELDS    = ('name', 'fullName', 'full_name', 'studentName')
_FATHER_PHONE_FIELDS     = ('fatherPhone', 'father_phone', 'fatherMobile', 'parentFatherPhone')
_MOTHER_PHONE_FIELDS     = ('motherPhone', 'mother_phone', 'motherMobile', 'parentMotherPhone')

# Staff phone fields
_STAFF_PHONE_FIELDS      = ('mobileNumber', 'mobile', 'phone', 'phoneNumber', 'mobile_number')
_STAFF_FNAME_FIELDS      = ('firstName', 'first_name', 'givenName')
_STAFF_LNAME_FIELDS      = ('lastName', 'last_name', 'surname', 'familyName')
_STAFF_FULLNAME_FIELDS   = ('name', 'fullName', 'full_name', 'staffName')
_STAFF_DEPT_FIELDS       = ('department', 'departmentName', 'dept', 'departmentCode')


def _first(record, *field_candidates):
    """Return the first non-empty value found among field_candidates in record dict."""
    for f in field_candidates:
        v = record.get(f)
        if v:
            return str(v).strip()
    return ''


def _parse_student_record(rec, include_student, include_father, include_mother):
    """
    Yield (name, phone) tuples from a single student JSON record.
    Respects the include_student/father/mother checkboxes.
    """
    results = []
    student_name = _first(rec, *_STUDENT_FNAME_FIELDS) or 'Student'

    if include_student:
        phone = _first(rec, *_STUDENT_PHONE_FIELDS)
        if phone:
            results.append((student_name, phone))

    if include_father:
        phone = _first(rec, *_FATHER_PHONE_FIELDS)
        if phone:
            results.append((f"Father of {student_name}", phone))

    if include_mother:
        phone = _first(rec, *_MOTHER_PHONE_FIELDS)
        if phone:
            results.append((f"Mother of {student_name}", phone))

    return results


def _parse_staff_record(rec):
    """Return (name, phone) from a single staff JSON record, or None if no phone."""
    phone = _first(rec, *_STAFF_PHONE_FIELDS)
    if not phone:
        return None
    # Build name from parts or full name field
    name = _first(rec, *_STAFF_FULLNAME_FIELDS)
    if not name:
        first = _first(rec, *_STAFF_FNAME_FIELDS)
        last  = _first(rec, *_STAFF_LNAME_FIELDS)
        name  = f"{first} {last}".strip() or 'Staff'
    return (name, phone)


def _staff_base_url(staff_dataservice_url):
    """
    Derive staff base from the getStaffByUsername URL.
    'https://juba.strathmore.edu/dataservice/staff/getStaffByUsername/'
    -> 'https://juba.strathmore.edu/dataservice/staff/'
    """
    url = staff_dataservice_url.rstrip('/')
    # Remove the last path component
    parts = url.rsplit('/', 1)
    return parts[0] + '/' if len(parts) == 2 else url + '/'


class SuSmsWebService:
    """
    Thin client around the Strathmore juba data service.

    Usage (from wizard):
        ws = SuSmsWebService(env)
        pairs = ws.get_students(school='SBS', program='BBS', ...)
        pairs = ws.get_staff(department='ICTD', gender='M')
    """

    def __init__(self, env):
        self.env    = env
        self._cfg   = env['ir.config_parameter'].sudo()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    @property
    def student_base(self):
        url = self._cfg.get_param(
            'su_sms.student_dataservice_url',
            default='https://juba.strathmore.edu/dataservice/students/',
        )
        return url.rstrip('/') + '/'

    @property
    def staff_base(self):
        url = self._cfg.get_param(
            'su_sms.staff_dataservice_url',
            default='https://juba.strathmore.edu/dataservice/staff/getStaffByUsername/',
        )
        return _staff_base_url(url)

    @property
    def timeout(self):
        try:
            return int(self._cfg.get_param('su_sms.webservice_timeout', default='15'))
        except (ValueError, TypeError):
            return 15

    @property
    def use_mock(self):
        return self._cfg.get_param('su_sms.webservice_use_mock', default='false').lower() == 'true'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_students(self, school=None, program=None, course=None,
                     academic_year=None, student_year=None,
                     enrolment_period=None, module=None, intake=None,
                     include_students=True, include_fathers=False, include_mothers=False,
                     modular=False):
        """
        Fetch student recipient list.

        Returns list of (name, phone) tuples.
        Calls getStudentsModular when modular=True, getStudentsAcademic otherwise.
        """
        if self.use_mock:
            return self._mock_students(include_students, include_fathers, include_mothers)

        endpoint = self.student_base + ('getStudentsModular' if modular else 'getStudentsAcademic')

        params = {}
        if school:          params['school']          = school
        if program:         params['program']         = program
        if course:          params['course']          = course
        if intake:          params['intake']          = intake
        if academic_year:   params['academicYear']    = academic_year
        if student_year:    params['studentYear']     = student_year
        if enrolment_period:params['enrolmentPeriod'] = enrolment_period
        if module:          params['module']          = module

        records = self._get_json(endpoint, params)
        if records is None:
            raise UserError(_(
                "Could not retrieve student data from the web service.\n"
                "Please check your network connection or contact ICT Services."
            ))

        results = []
        for rec in records:
            results.extend(_parse_student_record(
                rec, include_students, include_fathers, include_mothers
            ))

        if not results:
            raise UserError(_(
                "No students found matching the selected filters.\n"
                "Please broaden your selection and try again."
            ))

        _logger.info("SU WS: fetched %d student recipients from %s", len(results), endpoint)
        return results

    def get_staff(self, department=None, gender=None, category=None, job_status=None):
        """
        Fetch staff recipient list.

        Returns list of (name, phone) tuples.
        Uses getStaffBy with params if any filter set, else getAllStaff.
        """
        if self.use_mock:
            return self._mock_staff()

        params = {}
        if department:  params['department']   = department
        if gender and gender != 'all':
            params['gender'] = gender
        if category:    params['category']     = category
        if job_status:  params['jobStatusType']= job_status

        endpoint = self.staff_base + ('getStaffBy' if params else 'getAllStaff')

        records = self._get_json(endpoint, params)
        if records is None:
            raise UserError(_(
                "Could not retrieve staff data from the web service.\n"
                "Please check your network connection or contact ICT Services."
            ))

        results = []
        for rec in records:
            pair = _parse_staff_record(rec)
            if pair:
                results.append(pair)

        if not results:
            raise UserError(_(
                "No staff members found matching the selected filters.\n"
                "Please broaden your selection and try again."
            ))

        _logger.info("SU WS: fetched %d staff recipients from %s", len(results), endpoint)
        return results

    def lookup_staff_by_username(self, username):
        """
        Look up a single staff member by CAS/LDAP username.
        Returns a dict with name/phone keys or None if not found.
        Used when adding a new SMS administrator.
        """
        if self.use_mock:
            return {'name': f'Mock User ({username})', 'phone': '+254700000000', 'email': f'{username}@strathmore.edu'}

        endpoint = self._cfg.get_param(
            'su_sms.staff_dataservice_url',
            default='https://juba.strathmore.edu/dataservice/staff/getStaffByUsername/',
        ).rstrip('/') + '/' + urllib.parse.quote(username)

        try:
            resp = requests.get(endpoint, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # The endpoint may return a single object or a list
            rec = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
            if not rec:
                return None
            name = _first(rec, *_STAFF_FULLNAME_FIELDS)
            if not name:
                first = _first(rec, *_STAFF_FNAME_FIELDS)
                last  = _first(rec, *_STAFF_LNAME_FIELDS)
                name  = f"{first} {last}".strip()
            return {
                'name':  name,
                'phone': _first(rec, *_STAFF_PHONE_FIELDS),
                'email': rec.get('email', rec.get('emailAddress', '')),
            }
        except RequestException as exc:
            _logger.warning("SU WS: lookup_staff_by_username failed for %s: %s", username, exc)
            return None

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------
    def _get_json(self, endpoint, params=None):
        """
        GET request returning parsed JSON list/dict, or None on network error.
        Logs but does not raise network-level exceptions.
        """
        try:
            _logger.debug("SU WS GET %s params=%s", endpoint, params)
            resp = requests.get(endpoint, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            # Normalise: endpoint may wrap array in e.g. {"data": [...]} or {"students": [...]}
            if isinstance(data, list):
                return data
            for key in ('data', 'students', 'staff', 'results', 'records'):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Single-item dict - wrap in list
            if isinstance(data, dict):
                return [data]
            return data
        except requests.exceptions.HTTPError as exc:
            _logger.error("SU WS HTTP error %s for %s: %s", exc.response.status_code, endpoint, exc)
        except requests.exceptions.Timeout:
            _logger.error("SU WS timeout reaching %s", endpoint)
        except requests.exceptions.ConnectionError as exc:
            _logger.error("SU WS connection error for %s: %s", endpoint, exc)
        except Exception as exc:
            _logger.error("SU WS unexpected error for %s: %s", endpoint, exc)
        return None

    # ------------------------------------------------------------------
    # Mock data (used when su_sms.webservice_use_mock = true)
    # ------------------------------------------------------------------
    def _mock_students(self, include_students, include_fathers, include_mothers):
        _logger.warning("SU WS: using MOCK student data - disable su_sms.webservice_use_mock in production")
        rows = [
            {'name': 'Alice Kamau',  'phone': '+254711000001', 'fatherPhone': '+254722000001', 'motherPhone': '+254733000001'},
            {'name': 'Bob Mwangi',   'phone': '+254711000002', 'fatherPhone': '+254722000002', 'motherPhone': '+254733000002'},
            {'name': 'Carol Odhiambo','phone': '+254711000003','fatherPhone': '+254722000003', 'motherPhone': '+254733000003'},
        ]
        results = []
        for rec in rows:
            results.extend(_parse_student_record(rec, include_students, include_fathers, include_mothers))
        return results

    def _mock_staff(self):
        _logger.warning("SU WS: using MOCK staff data - disable su_sms.webservice_use_mock in production")
        return [
            ('David Njoroge',  '+254711100001'),
            ('Eve Akinyi',     '+254711100002'),
            ('Frank Omondi',   '+254711100003'),
        ]