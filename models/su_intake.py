# models/su_intake.py

from odoo import models, fields

class SuIntake(models.Model):
    _name = 'su.intake'
    _description = 'Student Intake'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    year = fields.Integer()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Intake ID must be unique')
    ]