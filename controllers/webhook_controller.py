# controllers/webhook_controller.py

from odoo import http
from odoo.http import request
import logging
import re

_logger = logging.getLogger(__name__)


class SmsWebhookController(http.Controller):

    @http.route(
        '/sms/webhook/delivery/<string:uuid>',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def sms_delivery_webhook(self, uuid, **kwargs):
        """
        Delivery confirmation endpoint from Africa's Talking.

        Update sms.tracker
        Keeps aligned with Odoo's native SMS engine.
        """

        try:
            _logger.info(f"Delivery webhook received for UUID {uuid}: {kwargs}")

            #  Basic UUID check 
            if not re.match(r'^[0-9a-f]{32}$', uuid):
                _logger.warning(f"Invalid UUID format: {uuid}")
                return "Invalid UUID"

            status = kwargs.get('status')
            error_code = kwargs.get('errorCode')
            error_message = kwargs.get('errorMessage')

            if not status:
                return "Missing status"

            # Find tracker record 
            tracker = request.env['sms.tracker'].sudo().search([
                ('sms_uuid', '=', uuid)
            ], limit=1)

            if not tracker:
                _logger.warning(f"No tracker found for UUID: {uuid}")
                return "OK"  # still return OK so AT doesn't retry forever

            # Map Africa's Talking status to Odoo state 
            status_map = {
                'Success': 'sent',
                'Sent': 'sent',
                'Delivered': 'sent',
                'Submitted': 'pending',
                'Queued': 'outgoing',
                'Failed': 'error',
                'Rejected': 'error',
            }

            new_state = status_map.get(status, 'error')

            if new_state == 'error':
                # Let Odoo handle proper failure logic
                tracker.with_context(
                    sms_known_failure_reason=error_message
                )._action_update_from_provider_error('unknown')

            else:
                tracker._action_update_from_sms_state(new_state)

            return "OK"

        except Exception as e:
            _logger.error(f"Delivery webhook error: {str(e)}")
            return "Error"
