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
from urllib.parse import urlencode
from frappe.utils import get_url, call_hook_method, cint, flt
from frappe.integrations.utils import make_get_request, make_post_request, create_request_log, create_payment_gateway


class PaymentSettings(Document):
	supported_currencies = [
		"ZAR"
	]
	def on_update(self):
		create_payment_gateway('Payfast-' + self.gateway_name, settings='Payfast Settings', controller=self.gateway_name)
		call_hook_method('payment_gateway_enabled', gateway='Payfast-' + self.gateway_name)


	
def generateApiSignature(dataArray, passPhrase = ''):
	payload = ""
	# if passPhrase != '':
	# 	dataArray['merchant_passphrase'] = passPhrase
	sortedData = sorted (dataArray)
	for key in sortedData:
		# Get all the data from PayFast and prepare parameter string
		print(key)
		payload += key + "=" + urllib.parse.quote_plus(str(dataArray[key]).replace("+", " ")) + "&"
	# After looping through, cut the last & or append your passphrase
	payload = payload[:-1]
	if passPhrase!='': payload += f"&passphrase={passPhrase}"
	return hashlib.md5(payload.encode()).hexdigest()

def environment_url(env):
	if env=='Live': return 'https://www.payfast.co.za'
	return 'https://sandbox.payfast.co.za'

@frappe.whitelist()
def test_connection(data):
	data = json.loads(data)
	print('test_connection_py', data)
	timestamp_var=datetime.now().isoformat()
	data['amount']='5'
	data['item_name']='Test Product'
	signature = generateApiSignature(data)
	data['signature']=signature
	response = requests.post(f"{environment_url(data.get('environment'))}/eng/process", 
		params=data,
		# params={
		# 	'merchant_id':int(data.get('merchant_id')),
		# 	'merchant_key': data.get('merchant_key'),
		# 	'version':'v2',
		# 	'timestamp':timestamp_var,
		# 	'signature':generateApiSignature(
		# 		dataArray={
		# 			'merchant-id':str(data.get('merchant_id')), 
		# 			'version':'v2',
		# 			'timestamp':timestamp_var,
		# 			'passphrase':data.get('merchant_passphrase')
		# 		}
		# 	)
		# },
		headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
		},
	)
	print(response.text)
	return {'status_code': response.status_code, 'message': response.text}

