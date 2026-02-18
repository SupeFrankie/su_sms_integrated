# models/__init__.py
"""
REFACTORED: Removed parallel SMS implementations
"""

# Core Odoo extensions
from . import res_company
from . import res_config_settings
from . import res_partner
from . import res_users
from . import hr_department

# Odoo SMS extensions (native models == extended)
from . import sms_sms
from . import sms_tracker

# SU custom models
from . import sms_administrator
from . import sms_template
from . import sms_blacklist
from . import sms_balance
from . import su_sms_log
from . import su_sms_department_expenditure

# Webservice / integration
from . import webservice_connector

# Academic domain models
from . import su_academic_year
from . import su_course
from . import su_enrolment_period
from . import su_intake
from . import su_module
from . import su_program
from . import su_school


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
# from . import sms_gateway_config  # --> Deprecated in use
# from . import sms_department  # --> Deprecated in use
# from . import sms_department_expenditure  #--> Deprecated and changed to departent_expenditure_old.py