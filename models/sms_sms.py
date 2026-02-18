# models/sms_sms.py


import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class SmsSms(models.Model):
    """
    Extend core sms.sms with SU-specific fields and post-send hook.

    Rules:
      - Do NOT override _send().  Let Odoo engine handle it.
      - Do NOT manage state directly here.
      - Use _handle_call_result_hook only for side-effects (logging,
        expenditure update).  Super must always be called first.
    """

    _inherit = 'sms.sms'

    # ------------------------------------------------------------------
    # SU-specific fields
    # ------------------------------------------------------------------

    su_department_id = fields.Many2one(
        'hr.department',
        string='SU Department',
        help='Department responsible for this SMS cost.',
    )

    su_sms_type = fields.Selection([
        ('staff',   'Staff'),
        ('student', 'Student'),
        ('adhoc',   'Ad-hoc'),
        ('manual',  'Manual'),
    ], string='SMS Type', help='Classification used for expenditure breakdown.')

    # ------------------------------------------------------------------
    # Post-send hook
    # ------------------------------------------------------------------

    def _handle_call_result_hook(self, sms_record, result):
        """
        Called by the Odoo SMS engine after provider response is processed.

        Signature (Odoo 16/17/18/19):
            _handle_call_result_hook(self, sms_record, result)
            where self is the sms.sms recordset being processed
            and sms_record is the individual sms.sms record.

        We use it to:
          1. Create su.sms.log entry (once per send).
          2. Update su.sms.department.expenditure if send succeeded.
        """
        super()._handle_call_result_hook(sms_record, result)

        # Guard: only act on records that belong to this module's provider
        # (engine calls hook for all providers, not just africastalking)
        if not sms_record.su_department_id:
            return

        # Avoid duplicate log entries (idempotent)
        existing = self.env['su.sms.log'].sudo().search(
            [('sms_id', '=', sms_record.id)], limit=1
        )
        if not existing:
            self._create_su_sms_log(sms_record, result)

        if result.get('state') == 'sent':
            self.env['su.sms.department.expenditure']._update_expenditure(
                department_id=sms_record.su_department_id.id,
                date=sms_record.create_date,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_su_sms_log(self, sms_record, result):
        """
        Create a single su.sms.log entry from a send result.

        Field mapping:
          sms.sms              → su.sms.log
          ─────────────────────────────────
          id                   → sms_id
          number               → number       (not 'phone_number')
          body                 → message
          su_department_id.id  → department_id
          result['credit']     → cost         (not 'credit')
          result['state']      → status       (not 'state')
          result['provider_message_id'] → provider_message_id
        """
        cost = result.get('credit', 0.0) or 0.0
        state = result.get('state', 'queued')

        # Map engine state values to su.sms.log status selection
        status_map = {
            'sent':         'sent',
            'server_error': 'failed',
            'sms_credit':   'failed',
            'sms_blacklist':'failed',
            'not_allowed':  'failed',
            'not_delivered':'failed',
            'wrong_number_format': 'failed',
        }
        log_status = status_map.get(state, 'queued')

        try:
            self.env['su.sms.log'].create({
                'sms_id':              sms_record.id,
                'number':              sms_record.number,
                'message':             sms_record.body,
                'department_id':       sms_record.su_department_id.id,
                'cost':                cost,
                'status':              log_status,
                'provider_message_id': result.get('provider_message_id'),
            })
        except Exception:
            _logger.exception(
                'su_sms_integrated: failed to create su.sms.log '
                'for sms.sms id=%s', sms_record.id
            )