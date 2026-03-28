from __future__ import unicode_literals
import frappe
from frappe import _
from urllib.parse import parse_qsl, quote_plus, urlparse
import hashlib
import json
from payment_gateway_payfast.utils import *
# from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from ..utils import generateApiSignature, environment_url, build_param_string
from .subscription import get_subscription

@frappe.whitelist(allow_guest=True)
def notify(**data):
	data.pop('cmd', None)
	integration_request = frappe.get_doc("Payfast Payment Request Logs", data.get('m_payment_id'))
	if not integration_request:
		frappe.local.response["http_status_code"] = 400
		frappe.local.response["message"] = "Integration Request not found"
		raise Exception("Integration Request not found")
	
	# validate notify request
	integration_data = frappe._dict(json.loads(integration_request.request_data))
	gateway_doc = frappe.get_doc(integration_data.get('payment_gateway_settings_doctype'), integration_data.get('payment_gateway_settings_docname'))
	passphrase=gateway_doc.get_password('passphrase')
	pfParamString_Pass = build_validation_param_string(data, passphrase)
	pfParamString = build_validation_param_string(data)
	pfParamString += f"&signature={hashlib.md5(pfParamString_Pass.encode()).hexdigest()}"
	payfast_domain = urlparse(integration_request.get("request_url")).netloc
	payfast_host = urlparse(frappe.request.headers.get("Referer")).netloc

	is_valid_payfast_host = validate_payfast_host(payfast_host)
	is_valid_signature = validate_payfast_signature(data, pfParamString_Pass)
	is_valid_payment_amount = validate_payfast_payment_amount(integration_data.get('amount'), data)
	is_valid_transaction = validate_payfast_transaction(pfParamString, payfast_domain)

	if not (is_valid_payfast_host and  is_valid_signature and is_valid_payment_amount and is_valid_transaction):
		integration_request.db_set('status', 'Failed')
		integration_request.db_set('response_error', json.dumps({
			'message': 'Invalid Payfast Notification callback',
			'is_valid_payfast_host':is_valid_payfast_host,
			'is_valid_signature':is_valid_signature,
			'is_valid_payment_amount': is_valid_payment_amount,
			'is_valid_transaction':is_valid_transaction,
			'pfParamString_Pass': pfParamString_Pass,
			'pfParamString': pfParamString
		}))
		frappe.db.commit()
		frappe.local.response["http_status_code"] = 400
		frappe.local.response["message"] = "Invalid Payfast Notification request"
		raise Exception("Invalid Payfast Notification")
	
	# Insert Payfast Payment Notification
	payfast_payment_notification = frappe.get_doc({
		'doctype': 'Payfast Payment Notifications',
		**data
	})
	payfast_payment_notification.save(ignore_permissions=True)
	
	# Update Integration Request
	if not integration_request.get('first_payfast_itn'):
		integration_request.db_set('first_payfast_itn', json.dumps(data, indent=2))
	integration_request.db_set('status', "Completed")

	# Insert Subscription if data contains subscription token
	if data.get('token') and integration_data:
		if int(integration_data.get('subscription_type'))==1:
			# Get Subscription details from Payfast
			subscription_response = get_subscription(**{
				'token': data.get('token'),
				'merchant_id': data.get('merchant_id'),
				'payment_gateway': integration_data.get('payment_gateway_docname')
			}).json()
			subscription_object = None
			if subscription_response.get('code')==200:
				subscription_object = subscription_response.get('data').get('response')
			# Create or Update Payfast Subscription
			try:
				payfast_subscription = frappe.get_doc('Payfast Subscriptions', data.get('token'))
				payfast_subscription.object = json.dumps(subscription_object, indent=2)
				payfast_subscription.save(ignore_permissions=True)
			except frappe.DoesNotExistError:
				payfast_subscription = frappe.get_doc({
					'doctype': 'Payfast Subscriptions',
					'token': data.get('token'),
					'merchant_id': data.get('merchant_id'),
					'object': json.dumps(subscription_object, indent=2)
				})
				payfast_subscription.insert(ignore_permissions=True)

	frappe.local.response["http_status_code"] = 200
	return {"status": "success"}
	
	# if (is_valid_payfast_host and  is_valid_signature and is_valid_payment_amount and is_valid_transaction):
	# 	status = 'Completed' if payfast_notify_data.get('payment_status')=='COMPLETE' else 'Failed'
	# 	integration_request.db_set('status', status)
	# 	if integration_request.get('reference_doctype')=='Payment Request':
	# 		payment_request = frappe.get_doc(integration_request.get('reference_doctype'),integration_data.get('reference_docname'))
	# 		# Party = Customer/Student/etc
	# 		party = frappe.get_doc(payment_request.party_type, payment_request.party)
	# 		# Reference DocType = Sales Invoice/Sales Order/etc
	# 		reference_doc = frappe.get_doc(payment_request.reference_doctype, payment_request.reference_name)
	# 		payment_entry = frappe.get_doc({
	# 			'doctype':'Payment Entry',
	# 			'status':'Submitted',
	# 			'payment_type':'Receive',
	# 			'posting_date': frappe.utils.today(),
	# 			'mode_of_payment': gateway_doc.mode_of_payment,
	# 			'company': reference_doc.company,
	# 			'cost_center': gateway_doc.cost_center,
	# 			'party_type': 'Customer',
	# 			'party': party.name,
	# 			'party_name': party.customer_name,
	# 			'paid_from': gateway_doc.debit_to,
	# 			'paid_from_account_currency': integration_data.get('currency'),
	# 			'paid_to': gateway_doc.paid_to,
	# 			'paid_to_account_currency': integration_data.get('currency'),
	# 			'paid_amount': float(payfast_notify_data.get('amount_net')),
	# 			'received_amount': float(payfast_notify_data.get('amount_gross')),
	# 			'target_exchange_rate': 1.0,
	# 			'reference_no': payfast_notify_data.get('pf_payment_id'),
	# 			'reference_date': frappe.utils.today(),
	# 			'references':[{
	# 				'doctype':'Payment Entry Reference',
	# 				'reference_doctype':'Sales Invoice',
	# 				'reference_name': reference_doc.name,
	# 				'total_amount': float(payfast_notify_data.get('amount_gross')),
	# 				'allocated_amount': float(payfast_notify_data.get('amount_gross')),
	# 				'exchange_rate': 1.0
	# 			}],
	# 			'deductions':[{
	# 				'doctype':'Payment Entry Deduction',
	# 				'account':gateway_doc.expense_account,
	# 				'cost_center':gateway_doc.cost_center,
	# 				'amount': -float(payfast_notify_data.get('amount_fee'))
	# 			}]
	# 		})
	# 		payment_entry.insert(ignore_permissions=True)
	# 		payment_entry.save(ignore_permissions=True)
	# 		payment_entry.submit()
	# 		# print('Payment Entry', payment_entry.as_dict())
	# 	#if integration_request.get('reference_doctype')=='Web Form':
	# 	else: #assumes the reference_doctype is a Web Form
	# 		try:
	# 			user = frappe.get_doc('User',integration_data.get('payer_email'))
	# 			user.append_roles('Customer')
	# 			user.save(ignore_permissions=True)
	# 			# print('user', user.as_dict())
	# 			try:
	# 				customer = frappe.get_last_doc('Customer', filters={'email_id': integration_data.get('payer_email')})
	# 				# print('customer', customer.as_dict())
	# 			except Exception as e:
	# 				print('Customer Does not Exist', e)
	# 				contact = frappe.get_last_doc('Contact', filters={'user': integration_data.get('payer_email')})
	# 				# print('contact', contact.as_dict())
	# 				customer = frappe.get_doc({
	# 					'doctype': 'Customer',
	# 					'customer_name': contact.first_name,
	# 					'customer_type': 'Individual',
	# 					'customer_group': 'Individual',
	# 					'territory': 'South Africa',
	# 					'customer_primary_contact': contact.name
	# 				})
	# 				customer.insert(ignore_permissions=True)
	# 				# print('customer', customer.as_dict())
	# 			try:
	# 				sales_invoice = frappe.get_doc({
	# 					'doctype':'Sales Invoice',
	# 					'status': 'Paid',
	# 					'title': integration_data.get('order_id'), #data
	# 					'remarks': integration_data.get('description'), #data
	# 					'customer': customer.name, #link
	# 					'customer_name': customer.customer_name, #small text
	# 					'company': gateway_doc.company, #link
	# 					'posting_date': frappe.utils.today(), #date
	# 					'due_date': frappe.utils.today(), #date
	# 					'currency': integration_data.get('currency'), #link
	# 					'conversion_rate': 1.0, #float
	# 					'selling_price_list': gateway_doc.price_list, #link
	# 					'price_list_currency': integration_data.get('currency'), #link
	# 					'plc_conversion_rate': 1.0, #float
	# 					'base_grand_total': integration_data.get('amount'),
	# 					'debit_to':gateway_doc.debit_to, #link
	# 					'items':[{
	# 						'doctype':'Sales Invoice Item',
	# 						'qty': 1,
	# 						'item_name': integration_data.get('title'),
	# 						'description': integration_data.get('description'),
	# 						'uom': 'Unit',
	# 						'conversion_factor': 1.0,
	# 						'rate': integration_data.get('amount'),
	# 						'price_list_rate': integration_data.get('amount'),
	# 						'amount': integration_data.get('amount'),
	# 						'base_rate': integration_data.get('amount'),
	# 						'base_amount': integration_data.get('amount'),
	# 						'income_account': gateway_doc.income_account,
	# 						'cost_center': gateway_doc.cost_center,
	# 					}], #Table
	# 				})
	# 				sales_invoice.insert(ignore_permissions=True)
	# 				sales_invoice.save(ignore_permissions=True)
	# 				sales_invoice.submit()
	# 				# print('Sales Invoice', sales_invoice.as_dict())
	# 			except Exception as e:
	# 				print('Sales Invoice error', e)
	# 			payment_entry = frappe.get_doc({
	# 				'doctype':'Payment Entry',
	# 				'status':'Submitted',
	# 				'payment_type':'Receive',
	# 				'posting_date': frappe.utils.today(),
	# 				'mode_of_payment': gateway_doc.mode_of_payment,
	# 				'company': sales_invoice.company,
	# 				'cost_center': gateway_doc.cost_center,
	# 				'party_type': 'Customer',
	# 				'party': customer.name,
	# 				'party_name': customer.customer_name,
	# 				'paid_from': gateway_doc.debit_to,
	# 				'paid_from_account_currency': integration_data.get('currency'),
	# 				'paid_to': gateway_doc.paid_to,
	# 				'paid_to_account_currency': integration_data.get('currency'),
	# 				'paid_amount': float(payfast_notify_data.get('amount_net')),
	# 				'received_amount': float(payfast_notify_data.get('amount_gross')),
	# 				'target_exchange_rate': 1.0,
	# 				'reference_no': payfast_notify_data.get('pf_payment_id'),
	# 				'reference_date': frappe.utils.today(),
	# 				'references':[{
	# 					'doctype':'Payment Entry Reference',
	# 					'reference_doctype':'Sales Invoice',
	# 					'reference_name': sales_invoice.name,
	# 					'total_amount': float(payfast_notify_data.get('amount_gross')),
	# 					'allocated_amount': float(payfast_notify_data.get('amount_gross')),
	# 					'exchange_rate': 1.0
	# 				}],
	# 				'deductions':[{
	# 					'doctype':'Payment Entry Deduction',
	# 					'account':gateway_doc.expense_account,
	# 					'cost_center':gateway_doc.cost_center,
	# 					'amount': -float(payfast_notify_data.get('amount_fee'))
	# 				}]
	# 			})
	# 			payment_entry.insert(ignore_permissions=True)
	# 			payment_entry.save(ignore_permissions=True)
	# 			payment_entry.submit()
	# 			# print('Payment Entry', payment_entry.as_dict())
	# 			web_ref_doc =  frappe.get_doc(integration_request.get('reference_doctype'), integration_request.get('reference_docname'))
	# 			reference_doc = frappe.get_doc(web_ref_doc.doc_type,integration_data.get('order_id'))
	# 			meta = frappe.get_meta(web_ref_doc.doc_type)
	# 			if meta.has_field('paid'):
	# 				reference_doc.paid=True
	# 				reference_doc.save(ignore_permissions=True)
	# 		except Exception as e: 
	# 			print('Payment Gateway completion process error', e)
	# 			traceback.print_exc()





