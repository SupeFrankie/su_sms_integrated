# wizard/sms_student_wizard.py


from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import os


class SmsStudentWizard(models.TransientModel):
    _name = 'sms.student.wizard'
    _description = 'Student SMS Wizard'
    
    school_id = fields.Many2one('su.school', string='School')
    program_id = fields.Many2one('su.program', string='Program')
    course_id = fields.Many2one('su.course', string='Course')
    academic_year_id = fields.Many2one('su.academic.year', string='Academic Year')
    student_year = fields.Selection([
        ('1', 'Year 1'),
        ('2', 'Year 2'),
        ('3', 'Year 3'),
        ('4', 'Year 4'),
        ('5', 'Year 5')
    ], string='Student Year')
    intake_id = fields.Many2one('su.intake', string='Intake')
    enrolment_period_id = fields.Many2one('su.enrolment.period', string='Enrolment Period')
    module_id = fields.Many2one('su.module', string='Module')
    
    send_to_students = fields.Boolean(string='Students', default=True)
    send_to_fathers = fields.Boolean(string='Fathers', default=False)
    send_to_mothers = fields.Boolean(string='Mothers', default=False)
    
    template_id = fields.Many2one('sms.template', string='Template')
    body = fields.Text(string='Message', required=True)
    recipient_count = fields.Integer(compute='_compute_recipients')
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.body = self.template_id.body
    
    @api.depends('school_id', 'send_to_students', 'send_to_fathers', 'send_to_mothers')
    def _compute_recipients(self):
        for wizard in self:
            try:
                students = wizard._fetch_students()
                count = 0
                if wizard.send_to_students:
                    count += len(students)
                if wizard.send_to_fathers:
                    count += len([s for s in students if s.get('father_mobile')])
                if wizard.send_to_mothers:
                    count += len([s for s in students if s.get('mother_mobile')])
                wizard.recipient_count = count
            except:
                wizard.recipient_count = 0
    
    def action_send_sms(self):
        self.ensure_one()
        
        if not (self.send_to_students or self.send_to_fathers or self.send_to_mothers):
            raise UserError(_('Select at least one recipient group'))
        
        students = self._fetch_students()
        
        if not students:
            raise UserError(_('No students match filters'))
        
        recipients = []
        
        if self.send_to_students:
            for student in students:
                if student.get('mobile'):
                    recipients.append({
                        'name': student['name'],
                        'mobile': student['mobile'],
                        'type': 'student'
                    })
        
        if self.send_to_fathers:
            for student in students:
                if student.get('father_mobile'):
                    recipients.append({
                        'name': student.get('father_name', 'Parent'),
                        'mobile': student['father_mobile'],
                        'type': 'parent_father'
                    })
        
        if self.send_to_mothers:
            for student in students:
                if student.get('mother_mobile'):
                    recipients.append({
                        'name': student.get('mother_name', 'Parent'),
                        'mobile': student['mother_mobile'],
                        'type': 'parent_mother'
                    })
        
        admin = self.env['sms.administrator'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        sms_records = self.env['sms.sms']
        for recipient in recipients:
            sms_records |= self.env['sms.sms'].create({
                'number': self._normalize_phone(recipient['mobile']),
                'body': self.body,
                'su_sms_type': 'student',
                'su_department_id': admin.department_id.id if admin else False,
            })
        
        sms_records.send()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SMS Queued'),
                'message': _(f'{len(recipients)} SMS queued'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
    def _fetch_students(self):
        base_url = os.getenv('STUDENT_DATASERVICE_URL', 'http://localhost')
        params = {}
        
        if self.school_id:
            params['school_id'] = self.school_id.external_id
        if self.program_id:
            params['program_id'] = self.program_id.external_id
        if self.course_id:
            params['course_id'] = self.course_id.external_id
        if self.academic_year_id:
            params['academic_year_id'] = self.academic_year_id.external_id
        if self.student_year:
            params['student_year'] = self.student_year
        if self.intake_id:
            params['intake_id'] = self.intake_id.external_id
        
        if self.enrolment_period_id or self.module_id:
            endpoint = 'student/getStudentsModular'
            if self.enrolment_period_id:
                params['enrolment_period_id'] = self.enrolment_period_id.external_id
            if self.module_id:
                params['module_id'] = self.module_id.external_id
        else:
            endpoint = 'student/getStudentsAcademic'
        
        url = f'{base_url}/{endpoint}'
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('students', [])
        except:
            return []
    
    def _normalize_phone(self, number):
        if not number:
            return False
        number = number.replace(' ', '').replace('-', '')
        if number.startswith('0'):
            return '+254' + number[1:]
        elif not number.startswith('+'):
            return '+254' + number
        return number