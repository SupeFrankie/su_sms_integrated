# models/__init__.py
"""
REFACTORED: Removed parallel SMS implementations
"""

# Core Odoo Extensions
from . import odoo_sms_integration
from . import hr_department
from . import res_partner
from . import res_users

# SU Custom Models
from . import sms_administrator
from . import sms_template
from . import sms_blacklist
from . import sms_balance
from . import sms_gateway_config
from . import sms_gateway_provider  
from . import su_sms_log  # (replaces sms_detail)
from . import su_sms_department_expenditure  # REFACTORED

# Webservice Connectors
from . import webservice_connector

# Student/Academic Models (if still needed)
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