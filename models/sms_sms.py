# models/sms_sms.py

from collections import defaultdict

from odoo import api, fields, models


class SmsSms(models.Model):
    _inherit = 'sms.sms'

    # Extra failure types for Africa's Talking
    failure_type = fields.Selection(
        selection_add=[
            ('at_authentication', "Africa's Talking Authentication Error"),
            ('at_insufficient_balance', "Africa's Talking Insufficient Balance"),
            ('at_invalid_sender', "Africa's Talking Invalid Sender ID"),
            ('at_number_format', "Africa's Talking Invalid Phone Number"),
        ],
    )

    # Link back to SU message campaign (nullable - not all SMS go through SU compose)
    su_message_id = fields.Many2one(
        'su.sms.message',
        string='SU SMS Campaign',
        index=True,
        ondelete='set null',
    )

    # Company tracking (mirror of sms_twilio approach)
    record_company_id = fields.Many2one(
        'res.company', 'Company', ondelete='set null',
    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['record_company_id'] = (
                vals.get('record_company_id') or self.env.company.id
            )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Provider routing - mirrors sms_twilio._split_by_api exactly
    # ------------------------------------------------------------------
    def _split_by_api(self):
        sms_by_company = defaultdict(lambda: self.env['sms.sms'])
        todo_via_super = self.browse()

        for sms in self:
            sms_by_company[sms._get_sms_company()] += sms

        for company, company_sms in sms_by_company.items():
            if company.sms_provider == 'africas_talking':
                sms_api = company._get_sms_api_class()(self.env)
                sms_api._set_company(company)
                yield sms_api, company_sms
            else:
                todo_via_super += company_sms

        if todo_via_super:
            yield from super(SmsSms, todo_via_super)._split_by_api()

    def _get_sms_company(self):
        return (
            self.mail_message_id.record_company_id
            or self.record_company_id
            or super()._get_sms_company()
        )

    # ------------------------------------------------------------------
    # Post-send hook - update SU message details
    # ------------------------------------------------------------------
    def _handle_call_result_hook(self, results):
        """
        After batch send, update su.sms.detail records that are linked
        to SU SMS campaigns with per-recipient status from AT.
        """
        at_sms = self.filtered(
            lambda s: s._get_sms_company().sms_provider == 'africas_talking'
        )
        if at_sms:
            grouped = at_sms.grouped('uuid')
            for result in results:
                sms = grouped.get(result.get('uuid'))
                if sms and sms.su_message_id:
                    # Update the corresponding su.sms.detail
                    detail = self.env['su.sms.detail'].search([
                        ('message_id', '=', sms.su_message_id.id),
                        ('sms_uuid', '=', result.get('uuid')),
                    ], limit=1)
                    if detail:
                        state_map = {
                            'sent': 'sent',
                            'pending': 'sent',
                            'process': 'sent',
                        }
                        new_state = (
                            state_map.get(result.get('state'))
                            or ('failed' if result.get('failure_type') else 'sent')
                        )
                        detail.write({
                            'status': new_state,
                            'failure_reason': result.get('failure_reason') or False,
                            'at_message_id': result.get('at_message_id') or False,
                            'cost': result.get('credit') or 0.0,
                        })
                        # Trigger expenditure update on success
                        if new_state == 'sent':
                            sms.su_message_id._update_department_expenditure(detail)

        super(SmsSms, self - at_sms)._handle_call_result_hook(results)
