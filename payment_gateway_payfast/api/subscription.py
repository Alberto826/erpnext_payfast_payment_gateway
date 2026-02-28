import frappe
import json
import requests
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from ..utils import generateApiSignatureAlphabetical, get_payment_gateway, get_payment_gateway_settings


SUBSCRIPTION_BASE_URL = 'https://api.payfast.co.za/subscriptions'


def _parse_data(data):
	return data if isinstance(data, dict) else json.loads(data)


def _resolve_payment_gateway_settings(data):
	app_settings_doc = data.get('app_settings_doc', None)
	app_settings_doc_payment_gateway = data.get('app_settings_doc_payment_gateway', None)
	payment_gateway_name = data.get('payment_gateway', None)
	payment_gateway = get_payment_gateway(app_settings_doc, app_settings_doc_payment_gateway, payment_gateway_name)
	return get_payment_gateway_settings(payment_gateway)


def _error_response(message, status_code=400):
	frappe.local.response["http_status_code"] = status_code
	frappe.local.response["message"] = message
	return {"status": "error", "message": message}


def _get_token_and_merchant_id(data, payment_gateway_settings):
	token = (data.get('token') or '').strip()
	if not token:
		return None, None, _error_response("Missing required field: token")

	merchant_id = data.get('merchant_id') or payment_gateway_settings.merchant_id
	if not merchant_id:
		return None, None, _error_response("Missing required field: merchant_id")

	return token, merchant_id, None


def _build_signed_headers(merchant_id, payment_gateway_settings, payload=None):
	headers = {
		'merchant-id': merchant_id,
		'version': 'v1',
		'timestamp': frappe.utils.now_datetime().strftime('%Y-%m-%dT%H:%M:%S%z')
	}
	signature_payload = {**headers, **(payload or {})}
	headers['signature'] = generateApiSignatureAlphabetical(
		signature_payload,
		passPhrase=payment_gateway_settings.get_password("passphrase")
	)
	return headers


def _build_subscription_url(token, action, payment_gateway_settings):
	url = f"{SUBSCRIPTION_BASE_URL}/{token}/{action}"
	if payment_gateway_settings.environment == 'Sandbox':
		url = f"{url}?testing=true"
	return url


def _is_successful_payfast_response(response_data):
	return (
		isinstance(response_data, dict)
		and response_data.get('code') == 200
		and str(response_data.get('status') or '').lower() == 'success'
	)


def _save_subscription_snapshot(token, merchant_id, response_data):
	if not token or not isinstance(response_data, dict):
		return

	object_payload = response_data.get('data', {}).get('response', response_data)
	merchant_id_value = merchant_id
	try:
		merchant_id_value = int(merchant_id)
	except (TypeError, ValueError):
		pass

	try:
		payfast_subscription = frappe.get_doc('Payfast Subscriptions', token)
		payfast_subscription.merchant_id = merchant_id_value
		payfast_subscription.object = json.dumps(object_payload, indent=2)
		payfast_subscription.save(ignore_permissions=True)
	except frappe.DoesNotExistError:
		payfast_subscription = frappe.get_doc({
			'doctype': 'Payfast Subscriptions',
			'token': token,
			'merchant_id': merchant_id_value,
			'object': json.dumps(object_payload, indent=2)
		})
		payfast_subscription.insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(
			"Payfast Save Subscription Snapshot",
			f"Failed saving Payfast Subscription snapshot for token {token}: {str(e)}\n{frappe.get_traceback()}"
		)


def get_subscription(_suppress_http_error=False, **data):
	"""Fetch a subscription object from Payfast Recurring Billing API.

	Payfast endpoint:
		GET /subscriptions/:token/fetch

	Required request data:
		- token (str): Subscription token (path param).
		- merchant_id (str|int, optional if configured): Merchant ID.
		- payment_gateway / app settings context to resolve passphrase and environment.

	Authentication and headers:
		- merchant-id, version=v1, timestamp, signature
		- signature is generated from alphabetically sorted header values (+ passphrase).

	Sandbox behavior:
		- Appends testing=true query parameter when gateway environment is Sandbox.

	Returns:
		dict: Raw Payfast JSON response, typically:
			{
				"code": 200,
				"status": "success",
				"data": {"response": {...}}
			}
		On local validation/runtime failure returns:
			{"status": "error", "message": "..."}
	"""
	try:
		data = _parse_data(data)
		payment_gateway_settings = _resolve_payment_gateway_settings(data)
		token, merchant_id, error = _get_token_and_merchant_id(data, payment_gateway_settings)
		if error:
			return error

		headers = _build_signed_headers(merchant_id, payment_gateway_settings)
		url = _build_subscription_url(token, 'fetch', payment_gateway_settings)
		res = requests.get(url, headers=headers)
		response_data = res.json()
		if _is_successful_payfast_response(response_data):
			_save_subscription_snapshot(token, merchant_id, response_data)
		return response_data
	except Exception as e:
		frappe.log_error("Payfast Get Subscription", f"Error fetching Payfast Subscription: {str(e)}\n{frappe.get_traceback()}")
		if not _suppress_http_error:
			frappe.local.response["http_status_code"] = 500
			frappe.local.response["message"] = "Error fetching Payfast Subscription"
		return {"status": "error", "message": str(e)}

def update_subscription(**data):
	"""Update one or more subscription attributes on Payfast.

	Payfast endpoint:
		PATCH /subscriptions/:token/update

	Required request data:
		- token (str): Subscription token (path param).
		- merchant_id (str|int, optional if configured): Merchant ID.
		- At least one updatable field.

	Supported update fields:
		- cycles (int >= 0)
		- frequency (int in [1..6])
		- run_date (str, format YYYY-MM-DD)
		- amount (rand value from caller; converted to integer cents for Payfast)

	Authentication and headers:
		- merchant-id, version=v1, timestamp, signature
		- signature is generated from headers + body payload (+ passphrase).

	Sandbox behavior:
		- Appends testing=true query parameter when gateway environment is Sandbox.

	Returns:
		dict: Raw Payfast JSON response with updated subscription object in
		data.response on success, or local error payload on failure.
	"""
	try:
		data = _parse_data(data)
		payment_gateway_settings = _resolve_payment_gateway_settings(data)
		token, merchant_id, error = _get_token_and_merchant_id(data, payment_gateway_settings)
		if error:
			return error

		payload = {}

		cycles_input = data.get('cycles')
		if cycles_input is not None and str(cycles_input).strip() != '':
			try:
				cycles = int(str(cycles_input).strip())
				if cycles < 0:
					raise ValueError()
				payload['cycles'] = cycles
			except (TypeError, ValueError):
				return _error_response("Invalid cycles. Expected integer greater than or equal to 0")

		frequency_input = data.get('frequency')
		if frequency_input is not None and str(frequency_input).strip() != '':
			try:
				frequency = int(str(frequency_input).strip())
				if frequency < 1 or frequency > 6:
					raise ValueError()
				payload['frequency'] = frequency
			except (TypeError, ValueError):
				return _error_response("Invalid frequency. Expected integer between 1 and 6")

		if data.get('run_date') is not None and str(data.get('run_date')).strip() != '':
			run_date = str(data.get('run_date')).strip()
			try:
				datetime.strptime(run_date, '%Y-%m-%d')
			except ValueError:
				return _error_response("Invalid run_date. Expected format YYYY-MM-DD")
			payload['run_date'] = run_date

		amount_input = data.get('amount')
		if amount_input is not None and str(amount_input).strip() != '':
			try:
				amount_rand = Decimal(str(amount_input).strip())
				if amount_rand <= 0:
					raise ValueError()
				amount_cents = int((amount_rand * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
				payload['amount'] = amount_cents
			except (InvalidOperation, TypeError, ValueError):
				return _error_response("Invalid amount. Expected positive rand value")

		if not payload:
			return _error_response("At least one update field is required: cycles, frequency, run_date, amount")

		headers = _build_signed_headers(merchant_id, payment_gateway_settings, payload)
		url = _build_subscription_url(token, 'update', payment_gateway_settings)
		res = requests.patch(url, headers=headers, json=payload)
		response_data = res.json()
		if _is_successful_payfast_response(response_data):
			safe_response_data = get_subscription(
				_suppress_http_error=True,
				token=token,
				merchant_id=merchant_id,
				app_settings_doc=data.get('app_settings_doc', None),
				app_settings_doc_payment_gateway=data.get('app_settings_doc_payment_gateway', None),
				payment_gateway=data.get('payment_gateway', None),
			)
			if not _is_successful_payfast_response(safe_response_data):
				_save_subscription_snapshot(token, merchant_id, response_data)
		return response_data
	except Exception as e:
		frappe.log_error("Payfast Update Subscription", f"Error updating Payfast Subscription: {str(e)}\n{frappe.get_traceback()}")
		frappe.local.response["http_status_code"] = 500
		frappe.local.response["message"] = "Error updating Payfast Subscription"
		return {"status": "error", "message": str(e)}

def cancel_subscription(**data):
	"""Cancel an active Payfast subscription.

	Payfast endpoint:
		PUT /subscriptions/:token/cancel

	Required request data:
		- token (str): Subscription token (path param).
		- merchant_id (str|int, optional if configured): Merchant ID.

	Authentication and headers:
		- merchant-id, version=v1, timestamp, signature
		- signature is generated from header values (+ passphrase).

	Sandbox behavior:
		- Appends testing=true query parameter when gateway environment is Sandbox.

	Returns:
		dict: Raw Payfast JSON response, typically containing:
			{"code": 200, "status": "success", "data": {"response": true}}
		On local validation/runtime failure returns:
			{"status": "error", "message": "..."}
	"""
	try:
		data = _parse_data(data)
		payment_gateway_settings = _resolve_payment_gateway_settings(data)
		token, merchant_id, error = _get_token_and_merchant_id(data, payment_gateway_settings)
		if error:
			return error

		headers = _build_signed_headers(merchant_id, payment_gateway_settings)
		url = _build_subscription_url(token, 'cancel', payment_gateway_settings)
		res = requests.put(url, headers=headers)
		response_data = res.json()
		if _is_successful_payfast_response(response_data):
			safe_response_data = get_subscription(
				_suppress_http_error=True,
				token=token,
				merchant_id=merchant_id,
				app_settings_doc=data.get('app_settings_doc', None),
				app_settings_doc_payment_gateway=data.get('app_settings_doc_payment_gateway', None),
				payment_gateway=data.get('payment_gateway', None),
			)
			if not _is_successful_payfast_response(safe_response_data):
				_save_subscription_snapshot(token, merchant_id, response_data)
		return response_data
	except Exception as e:
		frappe.log_error("Payfast Cancel Subscription", f"Error cancelling Payfast Subscription: {str(e)}\n{frappe.get_traceback()}")
		frappe.local.response["http_status_code"] = 500
		frappe.local.response["message"] = "Error cancelling Payfast Subscription"
		return {"status": "error", "message": str(e)}

def charge_tokenization_payment(**data):
	"""Charge a tokenization payment against a stored subscription token.

	Payfast endpoint:
		POST /subscriptions/:token/adhoc

	Required request data:
		- token (str): Subscription token (path param).
		- merchant_id (str|int, optional if configured): Merchant ID.
		- amount (int cents, ZAR, no decimals)
		- item_name (str, max 100 chars)

	Optional request data:
		- item_description (str, max 255 chars)
		- itn (bool)
		- m_payment_id (str, max 100 chars)
		- cc_cvv (numeric string)
		- setup (JSON object/string)

	Authentication and headers:
		- merchant-id, version=v1, timestamp, signature
		- signature is generated from headers + body payload (+ passphrase).

	Sandbox behavior:
		- Appends testing=true query parameter when gateway environment is Sandbox.

	Returns:
		dict: Raw Payfast JSON response, e.g. success with response=true and
		pf_payment_id, or failure details from Payfast/local validation.
	"""
	try:
		data = _parse_data(data)
		payment_gateway_settings = _resolve_payment_gateway_settings(data)
		token, merchant_id, error = _get_token_and_merchant_id(data, payment_gateway_settings)
		if error:
			return error

		amount_input = data.get('amount')
		if amount_input is None or str(amount_input).strip() == '':
			return _error_response("Missing required field: amount")

		item_name = (data.get('item_name') or '').strip()
		if not item_name:
			return _error_response("Missing required field: item_name")

		if len(item_name) > 100:
			return _error_response("Invalid item_name. Max length is 100")

		try:
			amount = int(str(amount_input).strip())
			if amount <= 0:
				raise ValueError()
		except (TypeError, ValueError):
			return _error_response("Invalid amount. Expected positive integer cents (ZAR)")

		payload = {
			'amount': amount,
			'item_name': item_name,
		}

		if data.get('item_description') is not None and str(data.get('item_description')).strip() != '':
			item_description = str(data.get('item_description')).strip()
			if len(item_description) > 255:
				return _error_response("Invalid item_description. Max length is 255")
			payload['item_description'] = item_description

		if data.get('itn') is not None and str(data.get('itn')).strip() != '':
			itn_input = data.get('itn')
			if isinstance(itn_input, bool):
				payload['itn'] = 'true' if itn_input else 'false'
			else:
				itn_value = str(itn_input).strip().lower()
				if itn_value in ['true', '1', 'yes']:
					payload['itn'] = 'true'
				elif itn_value in ['false', '0', 'no']:
					payload['itn'] = 'false'
				else:
					return _error_response("Invalid itn. Expected boolean")

		if data.get('m_payment_id') is not None and str(data.get('m_payment_id')).strip() != '':
			m_payment_id = str(data.get('m_payment_id')).strip()
			if len(m_payment_id) > 100:
				return _error_response("Invalid m_payment_id. Max length is 100")
			payload['m_payment_id'] = m_payment_id

		if data.get('cc_cvv') is not None and str(data.get('cc_cvv')).strip() != '':
			cc_cvv = str(data.get('cc_cvv')).strip()
			if not cc_cvv.isdigit():
				return _error_response("Invalid cc_cvv. Expected numeric value")
			payload['cc_cvv'] = cc_cvv

		if data.get('setup') is not None and str(data.get('setup')).strip() != '':
			setup_input = data.get('setup')
			if isinstance(setup_input, dict):
				payload['setup'] = json.dumps(setup_input, separators=(',', ':'))
			else:
				setup_str = str(setup_input).strip()
				try:
					json.loads(setup_str)
				except Exception:
					return _error_response("Invalid setup. Expected valid JSON string or object")
				payload['setup'] = setup_str

		headers = _build_signed_headers(merchant_id, payment_gateway_settings, payload)
		url = _build_subscription_url(token, 'adhoc', payment_gateway_settings)
		res = requests.post(url, headers=headers, json=payload)
		return res.json()
	except Exception as e:
		frappe.log_error("Payfast Charge Tokenization Payment", f"Error charging Payfast Tokenization Payment: {str(e)}\n{frappe.get_traceback()}")
		frappe.local.response["http_status_code"] = 500
		frappe.local.response["message"] = "Error charging Payfast Tokenization Payment"
		return {"status": "error", "message": str(e)}