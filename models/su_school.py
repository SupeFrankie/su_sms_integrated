# models/su_school.py

from odoo import models, fields

class SuSchool(models.Model):
    _name = 'su.school'
    _description = 'Strathmore University School'

    name = fields.Char(required=True)
    external_id = fields.Char(string='AMS School ID', required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'School ID must be unique')
    ]