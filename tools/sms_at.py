# tools/sms_at.py

"""
Africa's Talking utility helpers.
Mirrors sms_twilio/tools/sms_twilio.py in structure and purpose.
"""
import re
import logging

_logger = logging.getLogger(__name__)

# Kenya country code is default when no country code present
_DEFAULT_COUNTRY_CODE = '254'

AT_PRODUCTION_ENDPOINT = 'https://api.africastalking.com/version1/messaging'
AT_SANDBOX_ENDPOINT = 'https://sandbox.africastalking.com/version1/messaging'

AT_BALANCE_PRODUCTION = 'https://api.africastalking.com/version1/user'
AT_BALANCE_SANDBOX = 'https://sandbox.africastalking.com/version1/user'


def get_at_messaging_endpoint(company):
    """Return the correct messaging URL based on environment."""
    if company.at_environment == 'sandbox':
        return AT_SANDBOX_ENDPOINT
    return AT_PRODUCTION_ENDPOINT


def get_at_balance_endpoint(company):
    if company.at_environment == 'sandbox':
        return AT_BALANCE_SANDBOX
    return AT_BALANCE_PRODUCTION


def normalize_phone_number(number, default_country_code=_DEFAULT_COUNTRY_CODE):
    """
    Normalise a phone number to E.164 format expected by Africa's Talking.

    Examples:
      '0727374660'   -> '+254727374660'
      '254727374660' -> '+254727374660'
      '+254727374660'-> '+254727374660'
    """
    if not number:
        return None
    # Strip all non-numeric characters except leading +
    cleaned = re.sub(r'[^\d+]', '', number.strip())
    if cleaned.startswith('+'):
        return cleaned  # already E.164
    if cleaned.startswith('0') and len(cleaned) == 10:
        # Local Kenyan format
        return f'+{default_country_code}{cleaned[1:]}'
    if cleaned.startswith(default_country_code):
        return f'+{cleaned}'
    # Unknown format - return as-is with + prefix
    return f'+{cleaned}'


def parse_at_cost(cost_str):
    """
    Parse AT cost string like 'KES 0.8000' to a float.
    Returns 0.0 if unparseable.
    """
    if not cost_str:
        return 0.0
    try:
        parts = str(cost_str).split()
        return float(parts[-1])
    except (ValueError, IndexError):
        _logger.warning("Could not parse AT cost string: %r", cost_str)
        return 0.0


# AT status - Odoo failure_type mapping (for _send_sms_batch results)
AT_STATUS_TO_ODOO_FAILURE = {
    'InvalidPhoneNumber': 'sms_number_format',
    'NotNetworkSubscriber': 'sms_number_format',
    'UserInBlacklist': 'sms_blacklist',
    'InsufficientBalance': 'at_insufficient_balance',
    'InvalidSenderId': 'at_invalid_sender',
    'UserAccountSuspended': 'at_authentication',
    'AuthenticationFailed': 'at_authentication',
    'NumberNotWhitelisted': 'sms_acc',  # sandbox restriction
}

AT_SUCCESS_STATUSES = {'Success'}
