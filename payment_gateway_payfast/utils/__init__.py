import urllib.parse
import hashlib
import requests
import socket
import frappe

def get_ordered_fields():
	# Payfast validates against a particular order before processing for payment
	ordered_fields = [
		'merchant_id','merchant_key','return_url','cancel_url','notify_url', 'fica_idnumber', # merchant details
		'name_first','name_last','email_address','cell_number', # customer details
		'm_payment_id','amount','item_name','item_description', # transaction details
		'custom_int1','custom_int2','custom_int3','custom_int4','custom_int5', # transaction custom details
		'custom_str1','custom_str2','custom_str3','custom_str4','custom_str5', # transaction custom details
		'email_confirmation','confirmation_address', # transaction options
		'payment_method',
		'subscription_type', 'billing_date', 'recurring_amount', 'frequency', 'cycles', # subscriptions
        'subscription_notify_email','subscription_notify_webhook','subscription_notify_buyer',
		'setup', 'percentage', 'min', 'max', # split payment
		'signature',
	]
	return ordered_fields

def build_submission_data(data):
	submission_data={
		key:data.get(key) or '' for key in data.keys()
	}
	return submission_data

def build_param_string(data, passPhrase = ''):
	payload = "" 
	for key in get_ordered_fields():
		if data.get(key):
			payload += key + "=" + urllib.parse.quote_plus(data[key].replace("+", " ")) + "&"
	# After looping through, cut the last & or append your passphrase
	payload = payload[:-1]
	if passPhrase!='': payload += f"&passphrase={passPhrase}"
	return payload

def build_param_string_alphabetical(data, passPhrase=''):
	data['passphrase'] = passPhrase
	payload = ""
	# Sort keys alphabetically from the data dictionary
	for key in sorted(data.keys()):
		if data.get(key):
			value = urllib.parse.quote_plus(data[key].replace("+", " "))
			payload += f"{key}={value}&"
	# Remove trailing '&' if present
	payload = payload[:-1]
	return payload


def build_validation_param_string(data, passPhrase = ''):
	payload = "" 
	for key in data.keys():
		if key not in ['signature','cmd']:
			payload += key + "=" + urllib.parse.quote_plus(data[key].replace("+", " ")) + "&"
	# After looping through, cut the last & or append your passphrase
	payload = payload[:-1]
	if passPhrase!='': payload += f"&passphrase={passPhrase}"
	return payload

def generateApiSignature(dataArray, passPhrase = ''):
	payload = build_param_string(dataArray, passPhrase)
	return hashlib.md5(payload.encode()).hexdigest()

def generateApiSignatureAlphabetical(dataArray, passPhrase = ''):
	payload = build_param_string_alphabetical(dataArray, passPhrase)
	return hashlib.md5(payload.encode()).hexdigest()

def environment_url(env):
	if env=='Live': return 'https://www.payfast.co.za'
	return 'https://sandbox.payfast.co.za'

def validate_payfast_signature(pfData, pfParamString):
	# Generate our signature from PayFast parameters
	signature = hashlib.md5(pfParamString.encode()).hexdigest()
	return (pfData.get('signature') == signature)

def validate_payfast_host(host=''):    
	valid_hosts = [
		'www.payfast.co.za',
		'sandbox.payfast.co.za',
		'w1w.payfast.co.za',
		'w2w.payfast.co.za',
    ]
	valid_ips = []

	for item in valid_hosts:
		try:
			ips = socket.gethostbyname_ex(item)
			if ips:
				for ip in ips:
					if ip:
						valid_ips.append(ip)
		except Exception as e:
			print(f'Error occurred while resolving host {item}', e)
    # Remove duplicates from array
	clean_valid_ips = []
	for item in valid_ips:
		# Iterate through each variable to create one list
		if isinstance(item, list):
			for prop in item:
				if prop not in clean_valid_ips:
					clean_valid_ips.append(prop)
		else:
			if item not in clean_valid_ips:
				clean_valid_ips.append(item)

    # Security Step 3, check if referrer is valid
	if host not in clean_valid_ips:
		return False
	else:
		return True 

def validate_payfast_payment_amount(amount, pfData):
    return not (abs(float(amount)) - float(pfData.get('amount_gross'))) > 0.01

def validate_payfast_transaction(pfParamString, pfHost = 'sandbox.payfast.co.za'):
    url = f"https://{pfHost}/eng/query/validate"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
        }
    response = requests.post(url, data=pfParamString, headers=headers)
    return response.text == 'VALID'

def get_payment_gateway(app_settings_doc=None, app_settings_field=None, payment_gateway_name=None):
	if app_settings_doc and app_settings_field:
		app_payment_gateway_name = frappe.get_doc(app_settings_doc, app_settings_field)
		if app_payment_gateway_name:
			payment_gateway_name = app_payment_gateway_name
		else:
			frappe.local.response["http_status_code"] = 400
			frappe.local.response["message"] = f"App Payment Gateway not found in single doc: {app_settings_doc} and field: {app_settings_field}"
			raise Exception(f"Payment Gateway not found in {app_settings_doc} {app_settings_field}")
	if not app_settings_doc or not app_settings_field:
		if not payment_gateway_name:
			frappe.local.response["http_status_code"] = 400
			frappe.local.response["message"] = "payment_gateway, or app_settings_doc and app_settings_field not specified in params"
			raise Exception("payment_gateway, or app_settings_doc and app_settings_field not specified in params")
	payment_gateway = frappe.get_doc("Payment Gateway", payment_gateway_name)
	if not payment_gateway:
		frappe.local.response["http_status_code"] = 400
		frappe.local.response["message"] = f"Payment Gateway {payment_gateway_name} not found"
		raise Exception(f"Payment Gateway {payment_gateway_name} not found")
	return payment_gateway

def get_payment_gateway_settings(payment_gateway):
	payment_gateway_settings = frappe.get_doc(payment_gateway.gateway_settings, payment_gateway.gateway_controller)
	if not payment_gateway_settings:
		frappe.local.response["http_status_code"] = 400
		frappe.local.response["message"] = f"Payment Gateway Settings for {payment_gateway.name} not found"
		raise Exception(f"Payment Gateway Settings for {payment_gateway.name} not found")
	return payment_gateway_settings