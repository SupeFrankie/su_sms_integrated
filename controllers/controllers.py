# controllers/controllers.py


"""
Internal JSON-RPC routes for the SU SMS module.

NOTE: The Africa's Talking delivery webhook has been intentionally moved to
      portal.py because AT sends HTTP POST with form-encoded data — NOT a
      JSON-RPC payload. Using type='jsonrpc' on that route caused kwargs to
      arrive empty and silently dropped all delivery status updates.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SuSmsController(http.Controller):

    # ------------------------------------------------------------------
    # Balance endpoint  (dashboard card + refresh button)
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/balance',
        type='jsonrpc',       # internal authenticated call from OWL dashboard
        auth='user',
        methods=['POST'],
    )
    def get_at_balance(self, **kwargs):
        """
        Returns current Africa's Talking credit balance.
        Used by the dashboard balance card and its refresh button.

        Response:
            {'balance': 'KES 1234.50', 'error': False}   - success
            {'balance': None, 'error': 'message'}         - failure
        """
        try:
            company = request.env.company
            if not hasattr(company, '_get_at_balance'):
                return {
                    'balance': None,
                    'error': (
                        "Balance check not configured. "
                        "Please set up your Africa's Talking credentials."
                    ),
                }
            balance = company._get_at_balance()
            return {'balance': balance, 'error': False}
        except Exception as exc:
            _logger.warning("SU SMS balance check failed: %s", exc)
            return {'balance': None, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Dashboard stats
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/dashboard_stats',
        type='jsonrpc',       # internal authenticated call from OWL dashboard
        auth='user',
        methods=['POST'],
    )
    def get_dashboard_stats(self, **kwargs):
        """JSON endpoint for the OWL dashboard widget."""
        env        = request.env
        is_manager = env.user.has_group('su_sms_integrated.group_su_sms_manager')

        domain_base = [] if is_manager else [
            ('administrator_id.user_id', '=', env.uid)
        ]
        messages = env['su.sms.message'].search_read(
            domain_base,
            fields=[
                'sms_type', 'state', 'recipient_count', 'success_count',
                'total_cost', 'create_date', 'department_id',
            ],
            order='create_date desc',
            limit=200,
        )

        dept_stats = []
        if is_manager:
            dept_stats = env['su.sms.department'].search_read(
                [],
                fields=[
                    'name', 'short_name', 'chart_code', 'account_number',
                    'object_code', 'total_cost', 'kfs5_processed',
                ],
            )

        return {
            'messages':   messages,
            'dept_stats': dept_stats,
            'total_sent': sum(m['success_count'] for m in messages),
            'total_cost': sum(m['total_cost']    for m in messages),
            'is_manager': is_manager,
        }

    # ------------------------------------------------------------------
    # Ad Hoc CSV template download
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/adhoc_template.csv',
        type='http',          # file download - must stay type='http'
        auth='user',
        methods=['GET'],
    )
    def download_adhoc_template(self, **kwargs):
        """
        Serves a pre-filled CSV template for Ad Hoc SMS uploads.

        Columns:
            firstname       - recipient first name
            lastname        - recipient last name
            phone_number    - primary phone  (used for sending)
            mobile_number   - mobile / alternative number (fallback if primary blank)
        """
        csv_content = (
            'firstname,lastname,phone_number,mobile_number\n'
            'John,Doe,0712345678,0726133144\n'
            'Jane,Smith,+254733456789,\n'
        )
        csv_bytes = csv_content.encode('utf-8')
        headers = [
            ('Content-Type',        'text/csv; charset=utf-8'),
            ('Content-Disposition', 'attachment; filename="adhoc_sms_template.csv"'),
            ('Content-Length',      str(len(csv_bytes))),
        ]
        return request.make_response(csv_content, headers=headers)