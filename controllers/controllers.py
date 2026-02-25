# controllers/controllers.py

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SuSmsController(http.Controller):

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

        AT POSTs delivery status updates here. We update the sms.tracker
        and su.sms.detail records.

        AT posts these fields:
          id          - AT message ID
          status      - Delivered / Failed / Rejected / Sent
          phoneNumber - recipient number
          networkCode - network identifier
        """
        at_status = kwargs.get('status', '')
        at_message_id = kwargs.get('id', '')
        phone_number = kwargs.get('phoneNumber', '')

        _logger.info(
            "AT delivery webhook: uuid=%s status=%s at_id=%s phone=%s",
            sms_uuid, at_status, at_message_id, phone_number,
        )

        # Update sms.tracker via uuid
        tracker = request.env['sms.tracker'].sudo().search(
            [('sms_uuid', '=', sms_uuid)], limit=1
        )
        if tracker:
            tracker._action_update_from_at_status(at_status)

        # Update su.sms.detail if linked
        detail = request.env['su.sms.detail'].sudo().search(
            [('sms_uuid', '=', sms_uuid)], limit=1
        )
        if detail:
            status_map = {
                'Delivered': 'delivered',
                'Success': 'sent',
                'Sent': 'sent',
                'Failed': 'failed',
                'Rejected': 'rejected',
            }
            detail.write({
                'status': status_map.get(at_status, 'failed'),
                'at_message_id': at_message_id or detail.at_message_id,
            })

        return {'status': 'ok'}

    @http.route(
        '/su_sms/balance',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def get_at_balance(self, **kwargs):
        """JSON endpoint for dashboard to fetch current AT credit balance."""
        try:
            balance = request.env.company._get_at_balance()
            return {'balance': balance, 'error': False}
        except Exception as exc:
            return {'balance': None, 'error': str(exc)}

    @http.route(
        '/su_sms/dashboard_stats',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
    )
    def get_dashboard_stats(self, **kwargs):
        """JSON endpoint for OWL dashboard widget."""
        env = request.env
        is_manager = env.user.has_group('su_sms_integrated.group_su_sms_manager')

        # SMS stats
        domain_base = [] if is_manager else [
            ('administrator_id.user_id', '=', env.uid)
        ]
        messages = env['su.sms.message'].search_read(
            domain_base,
            fields=['sms_type', 'state', 'recipient_count', 'success_count', 'total_cost',
                    'create_date', 'department_id'],
            order='create_date desc',
            limit=200,
        )

        # Department expenditure (manager only)
        dept_stats = []
        if is_manager:
            depts = env['su.sms.department'].search_read(
                [],
                fields=['name', 'short_name', 'chart_code', 'account_number',
                        'object_code', 'total_cost', 'kfs5_processed'],
            )
            dept_stats = depts

        # Totals
        total_sent = sum(m['success_count'] for m in messages)
        total_cost = sum(m['total_cost'] for m in messages)

        return {
            'messages': messages,
            'dept_stats': dept_stats,
            'total_sent': total_sent,
            'total_cost': total_cost,
            'is_manager': is_manager,
        }