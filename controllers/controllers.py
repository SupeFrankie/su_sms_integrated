# controllers/controllers.py


import io
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SuSmsController(http.Controller):

    # ------------------------------------------------------------------
    # Africa's Talking delivery webhook
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/delivery/<string:sms_uuid>',
        type='jsonrpc',
        auth='public',
        csrf=False,
        methods=['POST'],
    )
    def at_delivery_report(self, sms_uuid, **kwargs):
        """
        Africa's Talking delivery report webhook.
        AT POSTs status updates here for each recipient.
        """
        at_status     = kwargs.get('status', '')
        at_message_id = kwargs.get('id', '')
        phone_number  = kwargs.get('phoneNumber', '')

        _logger.info(
            "AT delivery webhook: uuid=%s status=%s at_id=%s phone=%s",
            sms_uuid, at_status, at_message_id, phone_number,
        )

        tracker = request.env['sms.tracker'].sudo().search(
            [('sms_uuid', '=', sms_uuid)], limit=1
        )
        if tracker:
            tracker._action_update_from_at_status(at_status)

        detail = request.env['su.sms.detail'].sudo().search(
            [('sms_uuid', '=', sms_uuid)], limit=1
        )
        if detail:
            status_map = {
                'Delivered': 'delivered',
                'Success':   'sent',
                'Sent':      'sent',
                'Failed':    'failed',
                'Rejected':  'rejected',
            }
            detail.write({
                'status':        status_map.get(at_status, 'failed'),
                'at_message_id': at_message_id or detail.at_message_id,
            })

        return {'status': 'ok'}

    # ------------------------------------------------------------------
    # Balance endpoint (dashboard balance card + refresh button)
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/balance',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def get_at_balance(self, **kwargs):
        """
        Returns current Africa's Talking credit balance.
        Used by the dashboard balance card and its refresh button.

        Response:
            {'balance': 'KES 1234.50', 'error': False}   – success
            {'balance': None, 'error': 'message'}         – failure
        """
        try:
            company = request.env.company
            # _get_at_balance() is defined on res.company by su_sms_integrated
            if not hasattr(company, '_get_at_balance'):
                return {
                    'balance': None,
                    'error': "Balance check not configured. Please set up your Africa's Talking credentials.",
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
        type='jsonrpc',
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
            fields=['sms_type', 'state', 'recipient_count', 'success_count',
                    'total_cost', 'create_date', 'department_id'],
            order='create_date desc',
            limit=200,
        )

        dept_stats = []
        if is_manager:
            dept_stats = env['su.sms.department'].search_read(
                [],
                fields=['name', 'short_name', 'chart_code', 'account_number',
                        'object_code', 'total_cost', 'kfs5_processed'],
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
    # ADDED: serves the uploadable template so users can fill it in
    # ------------------------------------------------------------------
    @http.route(
        '/su_sms/adhoc_template.csv',
        type='http',
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
            mobile_number   - mobile / alternative number (fallback)

        The wizard parser prefers phone_number; if blank, falls back
        to mobile_number.
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