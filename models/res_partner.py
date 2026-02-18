#models/res_partner.py

"""
Extend Odoo's Contact Model (res.partner)
==========================================

Adds SMS functionality to existing Odoo contacts.

This lets you:
- Send SMS directly from contact form
- Link SMS contacts to Odoo partners
- Track SMS history per partner
- Use Odoo contacts in SMS module
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sms_opt_in = fields.Boolean(
        string='SMS Opt-in',
        default=False
    )

    sms_blacklisted = fields.Boolean(
        compute='_compute_sms_blacklisted'
    )

    student_id = fields.Char(string='Student/Staff ID')

    contact_type = fields.Selection([
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('external', 'External')
    ])

    sms_count = fields.Integer(
        compute='_compute_sms_stats'
    )

    last_sms_date = fields.Datetime(
        compute='_compute_sms_stats'
    )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _get_mobile_number(self):
        self.ensure_one()
        return self.mobile or self.phone

    # ---------------------------------------------------------
    # Blacklist
    # ---------------------------------------------------------

    def _compute_sms_blacklisted(self):
        Blacklist = self.env['su.sms.blacklist']
        for partner in self:
            mobile = partner._get_mobile_number()
            partner.sms_blacklisted = bool(
                mobile and Blacklist.is_blacklisted(mobile)
            )

    # ---------------------------------------------------------
    # Stats (using core sms.sms)
    # ---------------------------------------------------------

    def _compute_sms_stats(self):
        Sms = self.env['sms.sms']
        for partner in self:
            mobile = partner._get_mobile_number()
            if not mobile:
                partner.sms_count = 0
                partner.last_sms_date = False
                continue

            records = Sms.search([
                ('number', '=', mobile),
                ('state', '=', 'sent')
            ], order='create_date desc')

            partner.sms_count = len(records)
            partner.last_sms_date = records[0].create_date if records else False

    # ---------------------------------------------------------
    # Send SMS (Core Odoo)
    # ---------------------------------------------------------

    def action_send_sms(self):
        self.ensure_one()

        mobile = self._get_mobile_number()
        if not mobile:
            raise UserError(_('No mobile number found.'))

        if self.sms_blacklisted:
            raise UserError(_('This contact is blacklisted.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send SMS'),
            'res_model': 'sms.sms',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_number': mobile,
                'default_partner_id': self.id,
            }
        }

    # ---------------------------------------------------------
    # History
    # ---------------------------------------------------------

    def action_view_sms_history(self):
        self.ensure_one()
        mobile = self._get_mobile_number()

        return {
            'name': _('SMS History'),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.sms',
            'view_mode': 'list,form',
            'domain': [('number', '=', mobile)],
        }

    # ---------------------------------------------------------
    # Blacklist action
    # ---------------------------------------------------------

    def action_add_to_blacklist(self):
        self.ensure_one()

        mobile = self._get_mobile_number()
        if not mobile:
            raise UserError(_('No mobile number found.'))

        if self.sms_blacklisted:
            raise UserError(_('Already blacklisted.'))

        self.env['su.sms.blacklist'].create({
            'phone_number': mobile,
            'reason': 'admin',
            'notes': _('Added from partner: %s') % self.name,
        })

        self.sms_opt_in = False

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Added to SMS blacklist.'),
                'type': 'warning',
            }
        }
