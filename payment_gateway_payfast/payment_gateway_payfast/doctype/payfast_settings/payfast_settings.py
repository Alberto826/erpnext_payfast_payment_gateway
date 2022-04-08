# Copyright (c) 2022, Alberto Gutierrez and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
import json
from datetime import datetime
import urllib.parse
import hashlib
import requests
import socket
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, cint, flt
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log, create_payment_gateway


class PayfastSettings(Document):
	supported_currencies = [
		"ZAR"
	]

	currency_wise_minimum_charge_amount = {
		'ZAR': 5
	}

	def on_update(self):
		create_payment_gateway('Payfast-' + self.gateway_name, settings='Payfast Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='Payfast-' + self.gateway_name)

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. Payfast does not support transactions in currency '{0}'").format(currency))

	def validate_minimum_transaction_amount(self, currency, amount):
		if currency in self.currency_wise_minimum_charge_amount:
			if flt(amount) < self.currency_wise_minimum_charge_amount.get(currency, 0.0):
				frappe.throw(_("For currency {0}, the minimum transaction amount should be {1}").format(currency,
					self.currency_wise_minimum_charge_amount.get(currency, 0.0)))

	def get_payment_url(self, **kwargs):
		# add payment gateway details, don't send secrets in url
		kwargs['payfast_url']=f"{environment_url(self.environment)}/eng/process"
		kwargs['payfast_domain']=f"{environment_url(self.environment)}"
		kwargs['gateway_docname']=self.gateway_name
		kwargs['gateway_doctype']='Payfast Settings'
		self.integration_request = create_request_log(kwargs, "Host", "Payfast")
		# Payfast allows for up to 5 custom string fields. We can pass the integration request id 
		kwargs['integration_request_id']=self.integration_request.name
		return get_url("./payfast_checkout?{0}".format(urlencode(kwargs)))

def get_gateway_controller(doc):
	payment_request = frappe.get_doc("Payment Request", doc)
	gateway_controller = frappe.db.get_value("Payment Gateway", payment_request.payment_gateway, "gateway_controller")
	return gateway_controller

def get_ordered_fields():
	# Payfast validates against a particular order before processing for payment
	ordered_fields = [
		'merchant_id','merchant_key','return_url','cancel_url','notify_url', # merchant details
		'name_first','name_last','email_address','cell_number', # customer details
		'm_payment_id','amount','item_name','item_description', # transaction details
		'custom_int1','custom_int2','custom_int3','custom_int4','custom_int5', # transaction custom details
		'custom_str1','custom_str2','custom_str3','custom_str4','custom_str5', # transaction custom details
		'email_confirmation','confirmation_address', # transaction options
	]
	return ordered_fields

def build_submission_data(data):
	submission_data={
		key:data.get(key) or '' for key in data.keys()
	}
	return submission_data

def generateApiSignature(dataArray, passPhrase = ''):
	payload = "" 
	for key in get_ordered_fields():
		if dataArray.get(key):
			payload += key + "=" + urllib.parse.quote_plus(dataArray[key].replace("+", " ")) + "&"
	# After looping through, cut the last & or append your passphrase
	payload = payload[:-1]
	if passPhrase!='': payload += f"&passphrase={passPhrase}"
	print('payload', payload)
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
		ips = socket.gethostbyname_ex(item)
		if ips:
			for ip in ips:
				if ip:
					valid_ips.append(ip)
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

def validate_payfast_transaction(pfParamString, pfHost = 'https://sandbox.payfast.co.za'):
    url = f"{pfHost}/eng/query/validate"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
        }
    response = requests.post(url, data=pfParamString, headers=headers)
    return response.text == 'VALID'

@frappe.whitelist()
def test_connection(data):
	data = json.loads(data)
	timestamp_var=datetime.now().isoformat()
	env = data.get('environment') or 'Sandbox'
	data.pop('environment', None)
	passphrase = data.get('passphrase') or ''
	data.pop('passphrase', None)
	data['amount']='5'
	data['item_name']='Test Product'
	signature = generateApiSignature(data, passPhrase=passphrase)
	data['signature']=signature
	response = requests.post(f"{environment_url(env)}/eng/process", 
		params=data,
		headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
		},
	)
	message = response.text
	message = response.text.replace('/eng/images/',f"{environment_url(env)}/eng/images/")
	message = message.replace('/onsite/images/',f"{environment_url(env)}/onsite/images/")
	# message = message.replace('/eng/js/',f"{environment_url(env)}/eng/js/")
	# print(response.text)
	if env=='Live':
		message = 'Merchant ID and/or Merchant Key and/or Passphrase are either incorrect or does not exist in the Payfast Live environment. Please ensure that these are configured in the Developer Settings.'
		if response.status_code==200:
			message = 'Connection was successful.'
	return {'status_code':response.status_code, 'message': message}
	

