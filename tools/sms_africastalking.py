# tools/sms_africastalking.py


"""
Africa's Talking helper utilities.

Mirrors the pattern in sms_twilio/tools/sms_twilio.py.
Provides phone formatting, callback URL generation, and signature helpers.
"""

import base64
import hashlib
import hmac

from werkzeug.urls import url_join


def format_at_phone_number(phone_number):
    """
    Normalise a phone number to AT's expected international format (+254...).

    Examples:
        '0712345678'    → '+254712345678'
        '254712345678'  → '+254712345678'
        '+254712345678' → '+254712345678'
    """
    cleaned = ''.join(c for c in phone_number if c.isdigit() or c == '+')

    if cleaned.startswith('+'):
        return cleaned
    if cleaned.startswith('254'):
        return '+' + cleaned
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '+254' + cleaned[1:]
    return '+254' + cleaned


def get_at_status_callback_url(company, uuid):
    """
    Build the full delivery-report callback URL for a given SMS UUID.

    Pattern from sms_twilio: get_twilio_status_callback_url()

    Returns:
        str, e.g. 'https://example.odoo.com/sms_africastalking/status/abc123…'
    """
    base_url = company.get_base_url()
    return url_join(base_url, f'/sms_africastalking/status/{uuid}')


def generate_at_callback_signature(company, sms_uuid, callback_params):
    """
    Compute the expected HMAC-SHA256 signature for an AT webhook call.

    Pattern from sms_twilio: generate_twilio_sms_callback_signature()

    Algorithm:
      1. Reconstruct the callback URL.
      2. Sort POST params by key, concatenate as key+value strings.
      3. HMAC-SHA256( url + sorted_params, key=at_api_key ).
      4. Return base64-encoded digest.

    Args:
        company:         res.company record (must have at_api_key).
        sms_uuid:        str – the 32-char hex UUID embedded in the URL.
        callback_params: dict – the POST form data from the webhook request.

    Returns:
        str – base64-encoded signature, or '' if api_key is missing.
    """
    if not company.at_api_key:
        return ''

    url = get_at_status_callback_url(company, sms_uuid)
    sorted_params = ''.join(
        f'{k}{v}' for k, v in sorted(callback_params.items())
    )
    data = url + sorted_params

    # NOTE: use hmac.new() is wrong – the function is hmac.HMAC() or hmac.new()
    # The correct stdlib call is hmac.new(key, msg, digestmod)
    digest = hmac.new(
        company.at_api_key.encode(),
        data.encode(),
        hashlib.sha256,
    ).digest()

    return base64.b64encode(digest).decode()


def validate_at_delivery_status(at_status):
    """
    Map an Africa's Talking delivery status to an Odoo sms.tracker state.

    AT status values (delivery report):
      'Success', 'Sent', 'Submitted', 'Buffered', 'Rejected', 'Failed'

    Returns one of:
      'outgoing' | 'sent' | 'error'
    """
    _AT_TO_ODOO = {
        'Success':   'sent',
        'Sent':      'sent',
        'Submitted': 'sent',
        'Delivered': 'sent',
        'Buffered':  'outgoing',
        'Queued':    'outgoing',
        'Rejected':  'error',
        'Failed':    'error',
    }
    return _AT_TO_ODOO.get(at_status, 'error')


def get_at_error_code_mapping():
    """
    Map AT numeric error codes to Odoo sms.tracker failure types.

    Used by the webhook controller when updating a failed tracker.
    """
    return {
        '401': 'sms_credit',             # Invalid credentials
        '402': 'wrong_number_format',    # Invalid number
        '403': 'sms_server',             # Invalid sender ID
        '404': 'sms_credit',             # Insufficient balance
        '405': 'sms_blacklist',          # User blacklisted
        '406': 'not_allowed',            # Risk hold
        '407': 'not_delivered',          # Rate limit
        '409': 'wrong_number_format',    # Rejected number
        '500': 'sms_server',             # Internal server error
        '503': 'not_delivered',          # Service unavailable
    }