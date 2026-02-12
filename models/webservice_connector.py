# models/webservice_connector.py
"""
Strathmore University Data Adapter
===================================

Connects to:
1. LDAP (Active Directory) for authentication and user lookup
2. Strathmore Juba dataservices for extended student/staff data.

"""
 

from odoo import models, api
from odoo.exceptions import UserError
import logging
import os

_logger = logging.getLogger(__name__)

try:
    from ldap3 import Server, Connection, ALL, SIMPLE
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    _logger.warning("ldap3 not installed")


class WebServiceAdapter(models.AbstractModel):
    _name = 'sms.webservice.adapter'
    _description = 'Strathmore LDAP & Dataservice Adapter'

    @api.model
    def _get_ldap_config(self):
        config = self.env['ir.config_parameter'].sudo()

        return {
            'host': config.get_param('su_sms.ldap_host'),
            'port': int(config.get_param('su_sms.ldap_port', 389)),
            'base_dn': config.get_param('su_sms.ldap_base_dn'),
            'staff_domain': config.get_param('su_sms.staff_domain'),
            'student_domain': config.get_param('su_sms.student_domain'),
            'ssl': config.get_param('su_sms.ldap_ssl') == 'True',
            'tls': config.get_param('su_sms.ldap_tls') == 'True',
            'password': os.getenv('LDAP_PASSWORD')
        }

    @api.model
    def ldap_authenticate_user(self, username, password):

        if not LDAP_AVAILABLE:
            return False, {'error': 'ldap3 library not installed'}

        config = self._get_ldap_config()

        if not config['host']:
            return False, {'error': 'LDAP host not configured in Settings'}

        domain = (
            config['student_domain']
            if str(username).isdigit()
            else config['staff_domain']
        )

        user_principal = f"{username}@{domain}"

        try:
            server = Server(
                config['host'],
                port=config['port'],
                use_ssl=config['ssl'],
                get_info=ALL
            )

            conn = Connection(
                server,
                user=user_principal,
                password=password,
                authentication=SIMPLE,
                auto_bind=True
            )

            conn.unbind()

            return True, {
                'username': username,
                'domain': domain,
                'message': 'Authentication successful'
            }

        except Exception as e:
            return False, {'error': str(e)}

    @api.model
    def test_ldap_connection(self):

        if not LDAP_AVAILABLE:
            return {'success': False, 'message': 'ldap3 not installed'}

        config = self._get_ldap_config()

        if not config['host']:
            return {'success': False, 'message': 'LDAP host not configured'}

        try:
            server = Server(
                config['host'],
                port=config['port'],
                use_ssl=config['ssl'],
                get_info=ALL
            )

            conn = Connection(
                server,
                user=config.get('staff_domain'),
                password=config.get('password'),
                authentication=SIMPLE,
                auto_bind=True
            )

            info = str(server.info)
            conn.unbind()

            return {
                'success': True,
                'server_info': info
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def action_test_ldap_ui(self):
        results = self.test_ldap_connection()

        if results['success']:
            raise UserError("LDAP connection successful.")
        else:
            raise UserError(f"LDAP connection failed:\n{results['message']}")
