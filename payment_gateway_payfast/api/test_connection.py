
import frappe
import json
import requests
from ..utils import generateApiSignature, environment_url


@frappe.whitelist()
def test_connection(data):
	data = json.loads(data)
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
	if env=='Live':
		message = 'Merchant ID and/or Merchant Key and/or Passphrase are either incorrect or does not exist in the Payfast Live environment. Please ensure that these are configured in the Developer Settings.'
		if response.status_code==200:
			message = 'Connection was successful.'
	return {'status_code': response.status_code, 'message': message}