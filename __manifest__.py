{
    'name': 'Strathmore University - SMS System',
    'version': '2.0.0',
    'category': 'Marketing/SMS',
    'summary': "University SMS System with Africa's Talking Integration",
    'author': 'Francis Martine Nyabuto Agata',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'web',
        'hr',
        'sms',
    ],

    'data': [
        # Security (must be first) 
        'security/security_groups.xml',
        'security/ir.model.access.csv',

        # Seed data 
        'data/sms_template_data.xml',

        # Wizards 
        'wizard/sms_staff_wizard_views.xml',
        'wizard/sms_student_wizard_views.xml',
        'wizard/sms_manual_wizard_views.xml',

        # Views 
        'views/res_config_settings_views.xml',
        'views/sms_administrator_views.xml',
        'views/sms_department_expenditure_views.xml',
        'views/res_users_views.xml',
        'views/hr_department_views.xml',
        'views/su_sms_log_views.xml',
        'views/sms_blacklist_views.xml',
        'views/sms_template_views.xml',
        # 'views/opt_out_templates.xml', (commented out for now like it's controller)
        'views/menu_views.xml',
    ],

    #'assets': {
    #    'web.assets_backend': [
    #        'su_sms_integrated/static/src/css/sms_dashboard.css',
    #        'su_sms_integrated/static/src/xml/sms_live_widget.xml',
    #        'su_sms_integrated/static/src/xml/sms_systray_balance.xml',
    #        'su_sms_integrated/static/src/js/sms_live_widget.js',
    #        'su_sms_integrated/static/src/js/sms_systray_balance.js',
    #    ],
    #},

    'external_dependencies': {
        'python': ['requests'],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}