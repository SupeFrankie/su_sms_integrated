# models/odoo_sms_integration.py

from odoo import models, fields, api

class SmsSms(models.Model):
    _inherit = 'sms.sms'
    
    su_sms_type = fields.Selection([
        ('staff', 'Staff SMS'),
        ('student', 'Student SMS'),
        ('adhoc', 'Ad Hoc SMS'),
        ('manual', 'Manual SMS'),
    ], string='SU Type', index=True)
    
    su_department_id = fields.Many2one(
        'sms.department',
        string='Department',
        compute='_compute_su_department',
        store=True,
        index=True
    )
    
    cost_kes = fields.Float(string='Cost (KES)')
    kfs5_processed = fields.Boolean(default=False)
    kfs5_processed_date = fields.Datetime(readonly=True)
    
    @api.depends('create_uid')
    def _compute_su_department(self):
        for sms in self:
            admin = self.env['sms.administrator'].search([
                ('user_id', '=', sms.create_uid.id)
            ], limit=1)
            sms.su_department_id = admin.department_id if admin else False
    
    def _postprocess_iap_sent_sms(self, iap_results, failure_reason=None, delete_all=False):
        res = super()._postprocess_iap_sent_sms(iap_results, failure_reason, delete_all)
        for sms in self:
            result = next((r for r in iap_results if r.get('res_id') == sms.id), None)
            if result:
                sms.cost_kes = result.get('credit', 0.0)
        return res