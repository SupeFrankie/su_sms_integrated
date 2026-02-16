# models/res_config_settings.py


from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # ===== Africa's Talking Settings =====
    at_username = fields.Char(
        string='AT Username',
        config_parameter='su_sms.at_username'
    )
    
    at_api_key = fields.Char(
        string='AT API Key',
        config_parameter='su_sms.at_api_key'
    )
    
    at_sender_id = fields.Char(
        string='AT Sender ID',
        config_parameter='su_sms.at_sender_id',
        help="Optional custom sender ID"
    )
    
    # ===== LDAP Settings =====
    ldap_server = fields.Char(
        string='LDAP Server',
        config_parameter='su_sms.ldap_server'
    )
    
    ldap_port = fields.Integer(
        string='LDAP Port',
        default=389,
        config_parameter='su_sms.ldap_port'
    )
    
    ldap_bind_dn = fields.Char(
        string='Bind DN',
        config_parameter='su_sms.ldap_bind_dn'
    )
    
    ldap_bind_password = fields.Char(
        string='Bind Password',
        config_parameter='su_sms.ldap_bind_password'
    )
    
    ldap_staff_base_dn = fields.Char(
        string='Staff Base DN',
        config_parameter='su_sms.ldap_staff_base_dn'
    )
    
    ldap_student_base_dn = fields.Char(
        string='Student Base DN',
        config_parameter='su_sms.ldap_student_base_dn'
    )