# models/su_sms_detail.py


from odoo import fields, models


class SuSmsDetail(models.Model):
    _name = 'su.sms.detail'
    _description = 'SU SMS Recipient Detail'
    _order = 'id'

    message_id = fields.Many2one(
        'su.sms.message',
        string='Campaign',
        required=True,
        ondelete='cascade',
        index=True,
    )
    # Denormalized for easy filtering/reporting
    department_id = fields.Many2one(
        'su.sms.department',
        related='message_id.department_id',
        store=True,
        string='Department',
        index=True,
    )

    recipient_name = fields.Char('Recipient Name')
    phone_number = fields.Char('Phone Number', required=True)

    # Africa's Talking response fields
    at_message_id = fields.Char('AT Message ID', readonly=True)
    cost = fields.Float('Cost (KES)', digits=(10, 4), readonly=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ], default='draft', string='Status', index=True)

    failure_reason = fields.Char('Failure Reason', readonly=True)

    # UUID links back to sms.sms for result matching
    sms_uuid = fields.Char('SMS UUID', index=True, copy=False)
