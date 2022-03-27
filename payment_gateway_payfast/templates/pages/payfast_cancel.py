from __future__ import unicode_literals
import socket
from werkzeug.urls import url_parse
import frappe
from frappe import _
from frappe.utils import flt
from urllib.parse import parse_qsl, quote_plus, urlparse
import hashlib
import json
from payment_gateway_payfast.payment_gateway_payfast.doctype.payfast_settings.payfast_settings import validate_payfast_host, validate_payfast_signature, validate_payfast_payment_amount, validate_payfast_transaction

def get_context(context):
    # make sure that only payfast host can update docs with url query
    is_valid_payfast_host = validate_payfast_host(url_parse(frappe.request.headers.get("Referer") or '').host or '')
    if is_valid_payfast_host:
        payfast_cancel_request = urlparse(frappe.request.url)
        payfast_cancel_data = dict(parse_qsl(payfast_cancel_request.query))
        print('payfast_cancel_data', payfast_cancel_data)
        integration_request = frappe.get_doc("Integration Request", payfast_cancel_data.get('integration_request_id'))
        integration_data = frappe._dict(json.loads(integration_request.data))
        print('integration_data', integration_request.status)
        integration_request.db_set('status', 'Cancelled')
        integration_request.save(
            ignore_permissions=True, # ignore write permissions during insert
            ignore_version=True # do not create a version record
        )
        frappe.db.commit()
        integration_request.reload()
        integration_data = frappe._dict(json.loads(integration_request.data))
        print('integration_data', integration_request.status)
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = integration_data.get('redirect_to')
        raise frappe.Redirect
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = frappe.utils.get_url()
    raise frappe.Redirect
