from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
import json
from payment_gateway_payfast.payment_gateway_payfast.doctype.payfast_settings.payfast_settings import *


no_cache = 1

def get_context(context):
	context.no_cache = 1
	data = frappe.form_dict
	context.payment_details = data
	gateway_doc = frappe.get_doc(data.get('gateway_doctype'), data.get('gateway_docname'))
	context.gateway_details=gateway_doc.as_dict()
	context.gateway_details.merchant_key=gateway_doc.get_password('merchant_key')
	submission_data={
		'amount':data.get('amount') or '',
		'item_name':data.get('title') or '',
		'item_description':data.get('description') or '',
		'custom_str1':data.get('integration_request_id'),
		'name_first':data.get('payer_name') or '',
		# 'email_address':data.get('payer_email') or '',
		'm_payment_id':data.get('order_id') or '',
		'merchant_id':context.gateway_details.get('merchant_id') or '',
		'merchant_key':context.gateway_details.get('merchant_key') or '',
		'return_url':context.gateway_details.get('return_url') or f"{frappe.utils.get_url()}/payfast_success",
		'cancel_url':f"https://16c8-102-132-149-57.ngrok.io/payfast_cancel?integration_request_id={data.get('integration_request_id')}",
		# 'cancel_url':data.get('redirect_to') or '',
		'notify_url':'https://16c8-102-132-149-57.ngrok.io/payfast_notify',
		# 'notify_url':context.gateway_details.get('notify_url') or f"{frappe.utils.get_url()}/payfast_notify",
	}
	submission_data=build_submission_data(submission_data)
	submission_data['signature'] = generateApiSignature(submission_data, passPhrase=gateway_doc.get_password('passphrase'))
	context.payment_details['signature']=submission_data['signature']
	context.submission_data=submission_data
	ref_doc =  frappe.get_doc(data.get('reference_doctype'), data.get('reference_docname'))
	context.reference_details = ref_doc.as_dict()

	# print(context)
	return context




@frappe.whitelist(allow_guest=True)
def make_payment(payload_nonce, data, reference_doctype, reference_docname):
	data = json.loads(data)

	data.update({
		"payload_nonce": payload_nonce
	})

	gateway_controller = get_gateway_controller(reference_docname)
	data =  frappe.get_doc("Payfast Settings", gateway_controller).create_payment_request(data)
	frappe.db.commit()
	return data
