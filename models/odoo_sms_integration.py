# models/odoo_sms_integration.py

"""
    Strathmore University SMS Integration
    Extends Odoo's core sms.sms model with:
    - Department billing tracking
    - Africa's Talking provider integration
    - Cost computation and logging
    - KFS5 export preparation
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SmsSms(models.Model):
    _inherit = 'sms.sms'
    
    # ===== SU CUSTOM FIELDS =====
    su_sms_type = fields.Selection([
        ('staff', 'Staff SMS'),
        ('student', 'Student SMS'),
        ('adhoc', 'Ad Hoc SMS'),
        ('manual', 'Manual SMS'),
    ], string='SU SMS Type', index=True, help="Type of SMS for reporting purposes")
    
    su_department_id = fields.Many2one(
        'hr.department',
        string='Billing Department',
        compute='_compute_su_department',
        store=True,
        index=True,
        help="Department to be charged for this SMS"
    )
    
    su_sender_id = fields.Many2one(
        'sms.administrator',
        string='Sent By',
        compute='_compute_su_sender',
        store=True,
        help="Administrator who initiated this SMS"
    )
    
    su_cost = fields.Float(
        string='Cost (KES)',
        digits=(10, 2),
        help="Cost in Kenyan Shillings as returned by provider"
    )
    
    su_recipient_count = fields.Integer(
        string='Number of Recipients',
        default=1,
        help="Count of recipients for this SMS"
    )
    
    su_provider_message_id = fields.Char(
        string='Provider Message ID',
        help="Unique message ID from SMS gateway"
    )
    
    # ===== KFS5 INTEGRATION FIELDS =====
    kfs5_processed = fields.Boolean(
        string='Exported to KFS5',
        default=False,
        help="Has this SMS been exported to KFS5 for billing?"
    )
    
    kfs5_processed_date = fields.Datetime(
        string='KFS5 Export Date',
        readonly=True
    )
    
    kfs5_batch_id = fields.Char(
        string='KFS5 Batch Reference',
        readonly=True,
        help="KFS5 batch document number"
    )
    
    # ===== COMPUTE METHODS =====
    @api.depends('create_uid')
    def _compute_su_department(self):
        """Compute billing department from sender's administrator record"""
        for sms in self:
            if not sms.create_uid:
                sms.su_department_id = False
                continue
                
            admin = self.env['sms.administrator'].search([
                ('user_id', '=', sms.create_uid.id)
            ], limit=1)
            
            sms.su_department_id = admin.department_id if admin else False
    
    @api.depends('create_uid')
    def _compute_su_sender(self):
        """Compute sender administrator record"""
        for sms in self:
            if not sms.create_uid:
                sms.su_sender_id = False
                continue
                
            admin = self.env['sms.administrator'].search([
                ('user_id', '=', sms.create_uid.id)
            ], limit=1)
            
            sms.su_sender_id = admin if admin else False
    
    # ===== OVERRIDE SEND METHOD =====
    def _send(self, unlink_failed=False, unlink_sent=True, raise_exception=False):
        """
        Override Odoo's _send method to:
        1. Route through our provider abstraction layer
        2. Log each send to su.sms.log
        3. Compute and store cost
        4. Update department expenditure aggregation
        
        Falls back to super() if no custom provider configured
        """
        # Check if we have an active SU SMS provider configured
        try:
            provider = self.env['sms.gateway.provider']._get_active_provider()
            use_custom_provider = bool(provider)
        except Exception as e:
            _logger.warning(f"No custom SMS provider configured: {e}. Using Odoo default.")
            use_custom_provider = False
        
        if not use_custom_provider:
            # Fall back to Odoo's standard SMS sending
            return super()._send(unlink_failed, unlink_sent, raise_exception)
        
        # Custom send logic
        results = []
        for sms in self:
            try:
                # Validate phone number format
                if not sms.number:
                    sms.write({
                        'state': 'error',
                        'failure_reason': 'No phone number provided'
                    })
                    continue
                
                # Send via custom provider
                result = provider.send_sms(
                    number=sms.number,
                    message=sms.body
                )
                
                # Update SMS record based on result
                sms_values = {
                    'su_cost': result.get('cost', 0.0),
                    'su_provider_message_id': result.get('message_id'),
                }
                
                if result.get('success'):
                    sms_values.update({
                        'state': 'sent',
                        'failure_reason': False,
                    })
                else:
                    sms_values.update({
                        'state': 'error',
                        'failure_reason': result.get('error_message', 'Unknown error'),
                    })
                
                sms.write(sms_values)
                
                # Create log entry
                self.env['su.sms.log'].create({
                    'sms_id': sms.id,
                    'department_id': sms.su_department_id.id if sms.su_department_id else False,
                    'sender_id': sms.su_sender_id.id if sms.su_sender_id else False,
                    'number': sms.number,
                    'message': sms.body,
                    'cost': sms.su_cost,
                    'status': sms.state,
                    'provider_message_id': sms.su_provider_message_id,
                    'failure_reason': sms.failure_reason,
                })
                
                # Update department expenditure (triggers aggregation)
                if sms.su_department_id and sms.state == 'sent':
                    self.env['su.sms.department.expenditure']._update_expenditure(
                        sms.su_department_id.id,
                        sms.create_date or fields.Datetime.now()
                    )
                
                results.append(result)
                
            except Exception as e:
                error_msg = f"SMS send failed: {str(e)}"
                _logger.error(f"{error_msg} (SMS ID: {sms.id})")
                
                sms.write({
                    'state': 'error',
                    'failure_reason': error_msg
                })
                
                if raise_exception:
                    raise
        
        # Handle cleanup based on state
        if unlink_sent:
            self.filtered(lambda s: s.state == 'sent').unlink()
        if unlink_failed:
            self.filtered(lambda s: s.state in ['error', 'canceled']).unlink()
        
        return results
    
    # ===== BATCH OPERATIONS =====
    def mark_kfs5_processed(self, batch_id):
        """Mark SMS records as processed for KFS5 export"""
        self.ensure_one()
        
        if self.kfs5_processed:
            _logger.warning(f"SMS {self.id} already processed in batch {self.kfs5_batch_id}")
            return False
        
        self.write({
            'kfs5_processed': True,
            'kfs5_processed_date': fields.Datetime.now(),
            'kfs5_batch_id': batch_id,
        })
        
        return True
    
    def action_view_log(self):
        """Open su.sms.log view for this SMS"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'SMS Logs',
            'res_model': 'su.sms.log',
            'view_mode': 'list,form',
            'domain': [('sms_id', '=', self.id)],
            'context': {'create': False},
        }