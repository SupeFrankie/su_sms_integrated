# models/su_program.py

from odoo import models, fields

class SuProgram(models.Model):
    _name = 'su.program'
    _description = 'Strathmore Program'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    school_id = fields.Many2one('su.school', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Program ID must be unique')
    ]
