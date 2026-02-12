# models/su_academic_year.py

from odoo import models, fields

class SuAcademicYear(models.Model):
    _name = 'su.academic.year'
    _description = 'Academic Year'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Academic Year ID must be unique')
    ]
