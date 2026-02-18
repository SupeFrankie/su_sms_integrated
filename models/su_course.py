# models/su_course.py

from odoo import models, fields

class SuCourse(models.Model):
    _name = 'su.course'
    _description = 'SU Course'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    program_id = fields.Many2one('su.program', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)', 'Course ID must be unique')
    ]