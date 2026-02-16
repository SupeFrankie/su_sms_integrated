# models/su_sms_log.py


"""
    SU SMS Log Model
    Replaces legacy sms.detail with proper Odoo model
    Logs every SMS send with full tracking and analytics
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SuSmsLog(models.Model):
    _name = 'su.sms.log'
    _description = 'SMS Send Log'
    _order = 'create_date desc'
    _rec_name = 'number'
    
    # ===== CORE FIELDS =====
    sms_id = fields.Many2one(
        'sms.sms',
        string='SMS Record',
        ondelete='cascade',
        index=True,
        help="Link to Odoo's core sms.sms record"
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        index=True,
        required=True,
        help="Department billed for this SMS"
    )
    
    sender_id = fields.Many2one(
        'sms.administrator',
        string='Sent By',
        help="Administrator who sent this SMS"
    )
    
    number = fields.Char(
        string='Phone Number',
        required=True,
        index=True,
        help="Recipient phone number"
    )
    
    message = fields.Text(
        string='Message Content',
        help="SMS message body"
    )
    
    message_length = fields.Integer(
        string='Message Length',
        compute='_compute_message_length',
        store=True,
        help="Character count of message"
    )
    
    sms_count = fields.Integer(
        string='SMS Parts',
        compute='_compute_sms_parts',
        store=True,
        help="Number of SMS parts (160 chars each)"
    )
    
    # ===== COST FIELDS =====
    cost = fields.Float(
        string='Cost (KES)',
        digits=(10, 2),
        help="Cost in Kenyan Shillings"
    )
    
    cost_per_sms = fields.Float(
        string='Cost Per SMS Part',
        compute='_compute_cost_per_sms',
        store=True,
        digits=(10, 2)
    )
    
    # ===== STATUS TRACKING =====
    status = fields.Selection([
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ], string='Status', default='queued', required=True, index=True)
    
    provider_message_id = fields.Char(
        string='Provider Message ID',
        help="Unique ID from SMS gateway (e.g., Africa's Talking)"
    )
    
    failure_reason = fields.Text(
        string='Failure Reason',
        help="Error message if send failed"
    )
    
    # ===== ANALYTICS & REPORTING FIELDS =====
    month = fields.Char(
        string='Month',
        compute='_compute_period',
        store=True,
        index=True,
        help="Format: YYYY-MM"
    )
    
    quarter = fields.Char(
        string='Quarter',
        compute='_compute_period',
        store=True,
        index=True,
        help="Format: YYYY-Q#"
    )
    
    year = fields.Integer(
        string='Year',
        compute='_compute_period',
        store=True,
        index=True
    )
    
    # ===== DELIVERY TRACKING (Optional - for webhook updates) =====
    delivered_date = fields.Datetime(
        string='Delivered At',
        help="Timestamp when message was delivered (from provider callback)"
    )
    
    # ===== COMPUTE METHODS =====
    @api.depends('message')
    def _compute_message_length(self):
        for log in self:
            log.message_length = len(log.message) if log.message else 0
    
    @api.depends('message_length')
    def _compute_sms_parts(self):
        """Calculate number of SMS parts based on message length"""
        for log in self:
            if not log.message_length:
                log.sms_count = 0
                continue
            
            # Standard SMS: 160 chars per part
            # Concatenated SMS: 153 chars per part (7 chars for headers)
            if log.message_length <= 160:
                log.sms_count = 1
            else:
                log.sms_count = -(-log.message_length // 153)  # Ceiling division
    
    @api.depends('cost', 'sms_count')
    def _compute_cost_per_sms(self):
        for log in self:
            if log.sms_count > 0:
                log.cost_per_sms = log.cost / log.sms_count
            else:
                log.cost_per_sms = 0.0
    
    @api.depends('create_date')
    def _compute_period(self):
        for log in self:
            if log.create_date:
                log.month = log.create_date.strftime('%Y-%m')
                log.year = log.create_date.year
                quarter_num = (log.create_date.month - 1) // 3 + 1
                log.quarter = f"{log.create_date.year}-Q{quarter_num}"
            else:
                log.month = False
                log.quarter = False
                log.year = False
    
    # ===== CONSTRAINTS =====
    @api.constrains('cost')
    def _check_cost(self):
        for log in self:
            if log.cost < 0:
                raise ValidationError(_("SMS cost cannot be negative"))
    
    # ===== ACTIONS =====
    def action_view_sms_record(self):
        """Open the related sms.sms record"""
        self.ensure_one()
        
        if not self.sms_id:
            raise ValidationError(_("No linked SMS record found"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('SMS Record'),
            'res_model': 'sms.sms',
            'res_id': self.sms_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_update_delivery_status(self, provider_message_id, status, delivered_date=None):
        """
        Update delivery status from provider webhook
        Called by webhook controller
        """
        log = self.search([('provider_message_id', '=', provider_message_id)], limit=1)
        
        if not log:
            return False
        
        values = {'status': status}
        if delivered_date:
            values['delivered_date'] = delivered_date
        
        log.write(values)
        
        # Also update the sms.sms record if it exists
        if log.sms_id:
            sms_state_map = {
                'delivered': 'sent',
                'failed': 'error',
                'bounced': 'error',
            }
            if status in sms_state_map:
                log.sms_id.write({'state': sms_state_map[status]})
        
        return True