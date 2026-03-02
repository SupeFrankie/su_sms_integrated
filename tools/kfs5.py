# tools/kfs5.py


"""
KFS5 (Kuali Financial System) billing integration.

Purpose: Submit per-department SMS charges to KFS5 at month-end so that
each department is billed for their SMS usage automatically.

Configuration (set via Settings > Technical > Parameters > System Parameters):
  su_sms.kfs5_api_url    - KFS5 REST/SOAP endpoint URL
  su_sms.kfs5_username   - API username (basic auth)
  su_sms.kfs5_password   - API password / token
  su_sms.kfs5_chart_code - Default chart code (usually "SU")

HOW TO CONNECT YOUR KFS5 INSTANCE
-------------------------------------------------------------------------------
1. Obtain the KFS5 REST endpoint URL from your Finance team.
   Typically: https://<kfs5-host>/kfs/remoting/rest/financialTransaction/...

2. Set the four parameters above in:
   Settings > Technical > Parameters > System Parameters

3. Verify connectivity via Settings -> Africa's Talking SMS -> Test KFS5.

4. The cron job fires automatically on the 1st of each month at 02:00.
   To trigger manually: Settings > Technical > Scheduled Actions
   -> "SU SMS: Monthly KFS5 Billing Submission"

PAYLOAD STRUCTURE (adjust _build_payload to match your KFS5 API contract)
--------------------------------------------------------------------------------
{
  "documentType": "JV",
  "description":  "SMS charges ICTD 2025-01",
  "sourceLines": [
    {
      "chartCode":     "SU",
      "accountNumber": "2202800",
      "objectCode":    "2700",
      "amount":        1234.50,
      "description":   "Bulk SMS 2025-01",
      "referenceId":   "SU_SMS_ICTD_2025-01"
    }
  ]
}
------------------------------------------------------------------------------
"""

import logging
from datetime import date, datetime, timezone

import requests
from requests.exceptions import RequestException

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SuSmsKfs5Client:
    """
    Thin HTTP client for submitting SMS billing charges to KFS5.

    Two modes:
      Interactive (button/wizard) - raise_on_config_error=True  -> raises UserError
      Cron                        - raise_on_config_error=False -> logs, never raises
    """

    def __init__(self, env, raise_on_config_error=False):
        self.env                    = env
        self._cfg                   = env['ir.config_parameter'].sudo()
        self._raise_on_config_error = raise_on_config_error

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    @property
    def api_url(self):
        return self._cfg.get_param('su_sms.kfs5_api_url', default='').strip()

    @property
    def username(self):
        return self._cfg.get_param('su_sms.kfs5_username', default='').strip()

    @property
    def password(self):
        return self._cfg.get_param('su_sms.kfs5_password', default='').strip()

    @property
    def chart_code(self):
        return self._cfg.get_param('su_sms.kfs5_chart_code', default='SU').strip()

    def _check_configured(self):
        """
        Returns True if configured.
        In interactive mode raises UserError.
        In cron mode logs a warning and returns False (cron keeps running).
        """
        missing = [
            p for p, v in [
                ('su_sms.kfs5_api_url',  self.api_url),
                ('su_sms.kfs5_username', self.username),
                ('su_sms.kfs5_password', self.password),
            ] if not v
        ]
        if not missing:
            return True

        msg = (
            "KFS5 not configured - missing system parameters: %s. "
            "Set them in Settings > Technical > Parameters > System Parameters."
            % ", ".join(missing)
        )
        if self._raise_on_config_error:
            raise UserError(_(msg))
        _logger.warning("SU SMS KFS5: %s - skipping run.", msg)
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def test_connection(self):
        """Ping KFS5 to verify credentials. Raises UserError on failure."""
        if not self._check_configured():
            raise UserError(_("KFS5 is not configured. See system parameters."))
        try:
            resp = requests.get(
                self.api_url,
                auth=(self.username, self.password),
                timeout=10,
            )
            resp.raise_for_status()
            _logger.info("KFS5 connection test OK (HTTP %s)", resp.status_code)
            return True
        except RequestException as exc:
            raise UserError(_("KFS5 connection test failed: %s", str(exc)))

    def submit_department_charges(self, department_ids=None, period_label=None):
        """
        Submit SMS billing charges to KFS5.

        :param department_ids: list of su.sms.department IDs, or None = all active
        :param period_label:   "YYYY-MM" string; defaults to current month
        :returns: list of (dept_name, success: bool, message: str)
        """
        if not self._check_configured():
            return []

        if not period_label:
            today = date.today()
            period_label = f"{today.year}-{today.month:02d}"

        departments = (
            self.env['su.sms.department'].browse(department_ids)
            if department_ids
            else self.env['su.sms.department'].search([('active', '=', True)])
        )

        if not departments:
            _logger.info("KFS5: no active departments found.")
            return []

        results = [self._process_department(d, period_label) for d in departments]

        submitted = sum(1 for n, ok, m in results if ok and 'Skipped' not in m)
        skipped   = sum(1 for n, ok, m in results if 'Skipped' in m)
        failed    = sum(1 for n, ok, m in results if not ok)
        _logger.info(
            "KFS5 run complete (period=%s): %d submitted, %d skipped, %d failed",
            period_label, submitted, skipped, failed,
        )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _process_department(self, dept, period_label):
        """Process one department. Returns (name, success, message)."""
        try:
            details = self.env['su.sms.detail'].search([
                ('department_id',              '=', dept.id),
                ('status',                     '=', 'sent'),
                ('message_id.kfs5_processed',  '=', False),
            ])
            total_cost = sum(details.mapped('cost'))

            if total_cost <= 0:
                _logger.info("KFS5: %s - no unprocessed cost, skipping.", dept.name)
                return (dept.name, True, 'Skipped (no unprocessed cost)')

            payload = self._build_payload(dept, total_cost, period_label)
            ok, response_text = self._post_to_kfs5(payload)

            if ok:
                # FIX: original code used fields.Datetime.now() but 'fields' was
                # never imported in this file. Using Python datetime directly.
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                details.mapped('message_id').write({
                    'kfs5_processed':      True,
                    'kfs5_processed_date': now,
                })
                dept.write({
                    'kfs5_processed':      True,
                    'kfs5_processed_date': now,
                })
                _logger.info(
                    "KFS5: ✓ %s - KES %.4f submitted for %s",
                    dept.name, total_cost, period_label,
                )
                return (dept.name, True, f"OK - KES {total_cost:.2f} submitted")

            _logger.error("KFS5: ✗ %s - %s", dept.name, response_text)
            return (dept.name, False, response_text)

        except Exception:  # noqa: BLE001
            _logger.exception("KFS5: unexpected error for %s", dept.name)
            return (dept.name, False, "Unexpected error - see server logs")

    def _build_payload(self, dept, amount, period_label):
        """
        ---------------------------------------------------------------
        │  CUSTOMISE this method to match your KFS5 API contract.     │
        │  The structure below is a Journal Voucher (JV) default.     │
        ---------------------------------------------------------------
        """
        return {
            "documentType": "JV",
            "description":  f"SMS charges {dept.short_name} {period_label}",
            "sourceLines": [
                {
                    "chartCode":     dept.chart_code or self.chart_code,
                    "accountNumber": dept.account_number,
                    "objectCode":    dept.object_code,
                    "amount":        round(amount, 2),
                    "description":   f"Bulk SMS {period_label}",
                    "referenceId":   f"SU_SMS_{dept.short_name}_{period_label}",
                }
            ],
        }

    def _post_to_kfs5(self, payload):
        """POST payload. Returns (success: bool, response_text: str)."""
        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                auth=(self.username, self.password),
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            if resp.ok:
                return True, resp.text
            return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
        except RequestException as exc:
            return False, str(exc)