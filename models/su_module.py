# models/su_module.py

from odoo import models, fields

class SuModule(models.Model):
    _name = 'su.module'
    _description = 'Student Module'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Module ID must be unique')
    ]
