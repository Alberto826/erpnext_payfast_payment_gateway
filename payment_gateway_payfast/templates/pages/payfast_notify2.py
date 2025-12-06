from __future__ import unicode_literals
import socket
import traceback
from werkzeug.urls import url_parse
import frappe
from frappe import _
from urllib.parse import parse_qsl, quote_plus
import hashlib
import json
from payment_gateway_payfast.payment_gateway_payfast.utils import *
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

def get_context(context):
	payfast_notify_data = dict(parse_qsl(frappe.request.data.decode('UTF-8'), keep_blank_values=True))
	print('payfast_notify_data', payfast_notify_data)





