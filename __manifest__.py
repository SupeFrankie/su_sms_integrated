{
    'name': 'SU SMS - Africa\'s Talking',
    'version': '19.0.1.0',
    'summary': 'Strathmore University SMS via Africa\'s Talking - mass, staff, student, ad-hoc, manual',
    'category': 'Hidden/Tools',
    'description': """
Replaces Odoo's IAP SMS transport with Africa's Talking for Strathmore University.

Features
========
* All SMS types: Ad Hoc (CSV), Staff, Student, Manual
* Mass-send with per-recipient status tracking
* Department separation with billing codes (chart_code / account_number / object_code)
* Role-based access (System Admin, Faculty Admin, Staff Admin, Basic User)
* LDAP authentication support (requires auth_ldap)
* Dashboard with AT credit balance + department expenditure (sysadmin)
* Full integration with sms_marketing (sms.sms / sms.composer pipeline)
""",
    'author': 'Strathmore University ICT',
    'depends': [
        'sms',          # Odoo SMS base (sms.sms, sms.composer, sms_api pipeline)
        'mail',
        'hr',           # hr.department (soft reference for display)
        'phone_validation',
    ],
    'data': [
        # Security - load FIRST
        'security/su_sms_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/su_sms_data.xml',
        # Wizards
        'wizard/su_sms_account_manage_views.xml',
        'wizard/su_sms_compose_views.xml',
        # Views
        'views/res_config_settings_views.xml',
        'views/su_sms_department_views.xml',
        'views/su_sms_administrator_views.xml',
        'views/su_sms_message_views.xml',
        'views/su_sms_dashboard_views.xml',
        'views/su_sms_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'su_sms_integrated/static/src/css/su_sms.css',
            'su_sms_integrated/static/src/xml/su_sms_dashboard.xml',
            'su_sms_integrated/static/src/js/su_sms_dashboard.js',
        ],
    },
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,  # Not standalone; extends sms module
    'license': 'LGPL-3',
}
