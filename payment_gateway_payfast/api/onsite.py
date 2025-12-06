import frappe
import re
import json
import requests
from ..utils import generateApiSignature, environment_url, get_payment_gateway, get_payment_gateway_settings
from frappe.integrations.utils import create_request_log


@frappe.whitelist()
def onsite(**data):
	data = data if isinstance(data, dict) else json.loads(data)
	
	# Get Payment Gateway Settings from params
	app_settings_doc = frappe.request.args.get('app_settings_doc')
	app_settings_doc_payment_gateway = frappe.request.args.get('app_settings_doc_payment_gateway')
	payment_gateway_name = frappe.request.args.get('payment_gateway')
	payment_gateway = get_payment_gateway(app_settings_doc, app_settings_doc_payment_gateway, payment_gateway_name)
	payment_gateway_settings = get_payment_gateway_settings(payment_gateway)

	# Prepare data for Payfast
	full_notify_url = frappe.utils.get_url("/api/method/payment_gateway_payfast.api.notify.notify")
	data['notify_url'] = re.sub(r':\d+', '', full_notify_url)  # Remove port number if present
	data["merchant_id"] = payment_gateway_settings.merchant_id
	data["merchant_key"] = payment_gateway_settings.get_password("merchant_key")
	signature = generateApiSignature(data, passPhrase=payment_gateway_settings.get_password("passphrase"))
	data['signature'] = signature

	# Make request to Payfast
	headers = {'Content-Type': 'application/json'}
	url = f"{environment_url(payment_gateway_settings.environment)}/onsite/process"
	res = requests.post(url, json=data, headers=headers)

	# Log request and response
	request_description = f"Payfast Onsite Payment Request. Payment Gateway: {payment_gateway.name}, Doctype: {payment_gateway_settings.doctype}, Docname: {payment_gateway_settings.name}"
	name = data.get("m_payment_id")
	if not res.ok:
		frappe.local.response["http_status_code"] = res.status_code
		frappe.local.response["message"] = "Error from Payfast Server"
		frappe.local.response['error'] = res.text
		payfast_integration_log = frappe.get_doc({
			'doctype': 'Payfast Payment Request Logs',
			'm_payment_id': data.get("m_payment_id"),
			'status': "Failed",
			'payment_gateway': payment_gateway.name,
			'payment_gateway_settings': payment_gateway_settings.name,
			'payment_workflow': 'Web App',
			'request_url': url,
			'request_method': 'POST',
			'request_headers': json.dumps(headers, indent=2),
			'request_data': json.dumps(data, indent=2),
			'response_status_code': res.status_code,
			'response_error': res.text,
		})
		payfast_integration_log.insert(ignore_permissions=True)
	else: 
		try:
			response = json.loads(res.content.decode('utf-8'))
			frappe.local.response['uuid'] = response.get('uuid')
			frappe.local.response.pop("message", None)
		except Exception as e:
			response = res.content.decode('utf-8')
			frappe.local.response['message'] = f"Error decoding JSON response"
			frappe.local.response['error'] = str(e)
		payfast_integration_log = frappe.get_doc({
			'doctype': 'Payfast Payment Request Logs',
			'm_payment_id': data.get("m_payment_id"),
			'status': "Initiated",
			'payment_gateway': payment_gateway.name,
			'payment_gateway_settings': payment_gateway_settings.name,
			'payment_workflow': 'Web App',
			'request_url': url,
			'request_method': 'POST',
			'request_headers': json.dumps(headers, indent=2),
			'request_data': json.dumps(data, indent=2),
			'response_status_code': res.status_code,
			'response_data': json.dumps(response, indent=2)
		})
		payfast_integration_log.insert(ignore_permissions=True)
