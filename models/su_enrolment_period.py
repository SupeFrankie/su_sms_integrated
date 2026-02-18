# models/su_enrolment_period.py

from odoo import models, fields

class SuEnrolmentPeriod(models.Model):
    _name = 'su.enrolment.period'
    _description = 'Enrolment Period'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Enrolment Period ID must be unique')
    ]