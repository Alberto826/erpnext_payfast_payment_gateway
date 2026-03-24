import frappe
import re
import json
import requests
from ..utils import generateApiSignatureAlphabetical, get_payment_gateway, get_payment_gateway_settings

# @frappe.whitelist()
def get_subscription(**data):
	data = data if isinstance(data, dict) else json.loads(data)

	# Get Payment Gateway Settings from params
	# app_settings_doc = frappe.request.args.get('app_settings_doc')
	# app_settings_doc_payment_gateway = frappe.request.args.get('app_settings_doc_payment_gateway')
	# payment_gateway_name = frappe.request.args.get('payment_gateway')
	app_settings_doc = data.get('app_settings_doc') 
	app_settings_doc_payment_gateway = data.get('app_settings_doc_payment_gateway')
	payment_gateway_name = data.get('payment_gateway')
	payment_gateway = get_payment_gateway(app_settings_doc, app_settings_doc_payment_gateway, payment_gateway_name)
	payment_gateway_settings = get_payment_gateway_settings(payment_gateway)
    
	# Prepare data for Payfast
	params = {
		# 'token': data.get('token'),
		'merchant-id': data.get('merchant_id'),
		'version': 'v1',
		'timestamp': frappe.utils.now_datetime().strftime('%Y-%m-%dT%H:%M:%S%z')
	}
	signature = generateApiSignatureAlphabetical(params, passPhrase=payment_gateway_settings.get_password("passphrase"))
	params['signature'] = signature

	# Make request to Payfast
	base_url = 'https://api.payfast.co.za/subscriptions'
	if payment_gateway_settings.environment == 'Sandbox': url = f"{base_url}/{data.get('token')}/fetch?testing=true"
	else: url = f"{base_url}/{data.get('token')}/fetch"
	print('url', url)
	res = requests.get(url, headers=params)
	return res
	# if not res.ok:
	# 	frappe.local.response["http_status_code"] = res.status_code
	# 	frappe.local.response["message"] = "Error from Payfast Server"
	# 	frappe.local.response['error'] = res.text
	# else: 
	# 	try:
	# 		response = json.loads(res.content.decode('utf-8'))
	# 		frappe.local.response['data'] = response
	# 		frappe.local.response.pop("message", None)
	# 	except Exception as e:
	# 		frappe.local.response['message'] = f"Error decoding JSON response"
	# 		frappe.local.response['error'] = str(e)