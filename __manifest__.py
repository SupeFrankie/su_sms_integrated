{
    'name': 'Strathmore University - SMS System',
    'version': '2.0.0',  # Major version bump for refactoring
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
        'sms',           # Odoo core SMS
        'mass_mailing',  # For mailing.list if needed
        'iap',           # In-App Purchase for SMS
    ],
    
    'data': [
        # Security
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/sms_template_data.xml',
        'data/iap_provider_data.xml',
        
        # Wizards
        'wizard/sms_staff_wizard_views.xml',
        'wizard/sms_student_wizard_views.xml',
        'wizard/sms_manual_wizard_views.xml',
        'wizard/sms_import_wizard_views.xml',  # Ad Hoc
        
        # Views
        'views/sms_department_views.xml',
        'views/sms_administrator_views.xml',
        'views/sms_department_expenditure_views.xml',
        'views/iap_config_views.xml',
        'views/res_users_views.xml',
        'views/hr_department_views.xml',
        'views/sms_dashboard_views.xml',
        
        # Menus (REFACTORED)
        'views/menu_views.xml',
    ],
    
    'external_dependencies': {
        'python': ['requests'],
    },
    
    'installable': True,
    'application': True,
    'auto_install': False,
}