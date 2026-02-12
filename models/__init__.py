# models/__init__.py
"""
REFACTORED: Removed parallel SMS implementations
"""

from . import hr_department
from . import res_partner
from . import res_users
from . import sms_department
from . import sms_administrator
from . import sms_department_expenditure
from . import sms_blacklist
from . import sms_gateway_config
from . import sms_template
from . import iap_africas_talking
from . import sms_balance
from . import odoo_sms_integration
from . import su_school
from . import su_program
from . import su_course
from . import su_academic_year
from . import su_intake
from . import su_enrolment_period
from . import su_module
from . import webservice_connector

# ARCHIVED (commented out):
# from . import sms_message      # → Use sms.sms
# from . import sms_campaign     # → Use mailing.mailing
# from . import sms_recipient    # → Use sms.sms (one per recipient)
# from . import sms_detail       # → Merged into sms.sms
# from . import sms_queue        # → Use sms.sms state machine
# from . import sms_contact      # → Use mailing.contact
# from . import sms_mailing_list # → Use mailing.list
# from . import sms_type         # → Selection field on sms.sms
# from . import sms_dashboard      # --> Could cause circular import error