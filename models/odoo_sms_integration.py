# odoo_sms_integration.py

from odoo import models, fields, api, _


class SmsSms(models.Model):
    """
    Extend Odoo's native SMS model to add your custom fields.
    Now any SMS sent from Odoo will have department tracking!
    """
    _inherit = 'sms.sms'
    
    # Link to YOUR campaign (if sent via your module)
    su_campaign_id = fields.Many2one(
        'sms.campaign',
        string='SU Campaign',
        help='Link to Strathmore SMS campaign if sent via SU module'
    )
    
    # Track department for billing
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_department',
        store=True,
        help='Department for billing purposes'
    )
    
    # Track cost in KES
    cost_kes = fields.Float(
        string='Cost (KES)',
        help='SMS cost from Africa\'s Talking'
    )
    
    @api.depends('su_campaign_id', 'create_uid')
    def _compute_department(self):
        """Auto-determine department from campaign or user"""
        for sms in self:
            if sms.su_campaign_id and sms.su_campaign_id.department_id:
                sms.department_id = sms.su_campaign_id.department_id
            elif sms.create_uid and sms.create_uid.department_id:
                sms.department_id = sms.create_uid.department_id
            else:
                sms.department_id = False
    
    def _postprocess_iap_sent_sms(self, iap_results, failure_reason=None, delete_all=False):
        """
        This runs AFTER SMS is sent via IAP.
        We capture the cost and update our records.
        """
        res = super()._postprocess_iap_sent_sms(iap_results, failure_reason, delete_all)
        
        for sms in self:
            # Find result for this SMS
            result = next((r for r in iap_results if r.get('res_id') == sms.id), None)
            
            if result and result.get('state') == 'success':
                # Capture cost from Africa's Talking
                sms.cost_kes = result.get('credit', 0.0)
                
                _logger.info(f'SMS {sms.id} sent, cost: {sms.cost_kes} KES')
        
        return res