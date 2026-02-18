# models/sms_balance.py

from odoo import models, api, _
import requests
import logging

_logger = logging.getLogger(__name__)


class SMSBalance(models.Model):
    _name = 'sms.balance'
    _description = 'SMS Balance'

    @api.model
    def get_balance(self):
        company = self.env.company

        if company.sms_provider != 'africastalking':
            return {'error': "Africa's Talking not configured as provider"}

        return self._get_at_balance(company)

    def _get_at_balance(self, company):
        import requests

        if not company.at_username or not company.at_api_key:
            return {'error': 'Missing credentials'}

        url = "https://api.africastalking.com/version1/user"
        headers = {
            "apiKey": company.at_api_key,
            "Accept": "application/json",
        }
        data = {
            "username": company.at_username
        }

        response = requests.get(url, headers=headers, params=data)

        if response.status_code != 200:
            return {'error': response.text}

        return response.json()
