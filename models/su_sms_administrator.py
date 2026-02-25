# models/su_sms_administrator.py

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SuSmsAdministrator(models.Model):
    _name = 'su.sms.administrator'
    _description = 'SU SMS Administrator'
    _rec_name = 'display_name'
    _order = 'name'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    department_id = fields.Many2one(
        'su.sms.department',
        string='Department',
        required=True,
        ondelete='restrict',
        index=True,
    )
    role = fields.Selection([
        ('system_admin', 'System Administrator'),
        ('faculty_admin', 'Faculty Administrator'),
        ('staff_admin', 'Staff Administrator'),
        ('admin', 'Administrator'),
        ('basic_user', 'Basic User'),
    ], string='Role', required=True, default='basic_user')

    active = fields.Boolean(default=True)
    phone = fields.Char(string='Phone', help='Receives a copy of sent SMS')

    # Delegated from user
    name = fields.Char(related='user_id.name', string='Name', store=True)
    email = fields.Char(related='user_id.email', string='Email', store=True)
    login = fields.Char(related='user_id.login', string='Username', store=True)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('name', 'department_id.short_name')
    def _compute_display_name(self):
        for rec in self:
            dept = rec.department_id.short_name or ''
            rec.display_name = f"{rec.name} ({dept})" if dept else rec.name or ''

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    _sql_constraints = [
        ('user_unique', 'unique(user_id)',
         'A user can only have one SMS Administrator record.'),
    ]

    @api.constrains('role')
    def _check_role_groups(self):
        """Sync Odoo security groups to match the assigned role."""
        role_group_map = {
            'system_admin': 'su_sms_integrated.group_su_sms_manager',
            'faculty_admin': 'su_sms_integrated.group_su_sms_faculty_admin',
            'staff_admin': 'su_sms_integrated.group_su_sms_staff_admin',
            'admin': 'su_sms_integrated.group_su_sms_admin',
            'basic_user': 'su_sms_integrated.group_su_sms_user',
        }
        for rec in self:
            # Remove from all SU SMS groups first
            all_group_xmlids = list(role_group_map.values())
            all_groups = self.env['res.groups'].browse()
            for xmlid in all_group_xmlids:
                try:
                    g = self.env.ref(xmlid)
                    all_groups |= g
                except Exception:
                    pass
            if all_groups:
                rec.user_id.write({'groups_id': [(3, g.id) for g in all_groups]})
            # Add to appropriate group
            group_xmlid = role_group_map.get(rec.role)
            if group_xmlid:
                try:
                    group = self.env.ref(group_xmlid)
                    rec.user_id.write({'groups_id': [(4, group.id)]})
                except Exception:
                    pass
