{
    'name': 'Strathmore University - SMS System',
    'version': '2.0.0',
    'category': 'Marketing/SMS',
    'summary': 'University SMS System with Africa\'s Talking Integration',
    'author': 'Francis Martine Nyabuto Agata',
    'license': 'LGPL-3',
    
    'depends': [
        'base',
        'mail',
        'contacts',
        'web',
        'hr',
        'sms',
        'iap',
        'marketing_automation',
        'sms_marketing',
        'auth_ldap',
    ],
    
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        
        'data/sms_template_data.xml',
        'data/iap_provider_data.xml',
        
        'wizard/sms_staff_wizard_views.xml',
        'wizard/sms_student_wizard_views.xml',
        'wizard/sms_manual_wizard_views.xml',
        'wizard/sms_import_wizard_views.xml',
        
        'views/sms_department_views.xml',
        'views/sms_administrator_views.xml',
        'views/sms_department_expenditure_views.xml',
        'views/iap_config_views.xml',
        'views/res_users_views.xml',
        'views/hr_department_views.xml',
        'views/sms_dashboard_views.xml',
        'views/sms_gateway_views.xml',
        'views/sms_blacklist_views.xml',
        'views/sms_template_views.xml',
        'views/opt_out_templates.xml',
        'views/menu_views.xml',
    ],
    
    'external_dependencies': {
        'python': ['requests', 'ldap3'],
    },
    
    'installable': True,
    'application': True,
    'auto_install': False,
}