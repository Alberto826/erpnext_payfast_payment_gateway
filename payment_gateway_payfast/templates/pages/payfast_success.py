from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
import json
from payment_gateway_payfast.payment_gateway_payfast.doctype.payfast_settings.payfast_settings import *

def get_context(context):
	# print(context)
	return context