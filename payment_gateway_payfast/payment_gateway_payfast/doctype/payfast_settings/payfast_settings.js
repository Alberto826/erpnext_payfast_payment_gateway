// Copyright (c) 2022, Alberto Gutierrez and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payfast Settings', {
	refresh: function(frm) {
		frm.disable_save();
		frm.set_query('paid_to', () => {
			return {
				filters: {
					account_type: 'Bank',
					root_type: 'Asset',
					report_type: 'Balance Sheet',
					account_currency: 'ZAR',
					company: frm.doc.company
				}
			}
		});
		frm.set_query('debit_to', () => {
			return {
				filters: {
					account_type: 'Receivable',
					root_type: 'Asset',
					report_type: 'Balance Sheet',
					account_currency: 'ZAR',
					company: frm.doc.company
				}
			}
		});
		frm.set_query('expense_account', () => {
			return {
				filters: {
					account_type: 'Expense Account',
					root_type: 'Expense',
					report_type: 'Profit and Loss',
					account_currency: 'ZAR',
					company: frm.doc.company
				}
			}
		});
		frm.set_query('income_account', () => {
			return {
				filters: {
					account_type: 'Income Account',
					root_type: 'Income',
					report_type: 'Profit and Loss',
					account_currency: 'ZAR',
					company: frm.doc.company
				}
			}
		});
		frm.set_query('mode_of_payment', () => {
			return {
				filters: {
					account_type: 'Income Account',
					root_type: 'Income',
					report_type: 'Profit and Loss',
					account_currency: 'ZAR',
					company: frm.doc.company
				}
			}
		});
	}
});

frappe.ui.form.on('Payfast Settings', 'test_connection', function(){
	// cur_frm.doc.test_connection.read_only=1;
	frappe.call({
		method:'payment_gateway_payfast.payment_gateway_payfast.doctype.payfast_settings.payfast_settings.test_connection',
		args: { data:{
			merchant_id: cur_frm.doc.merchant_id,
			merchant_key: cur_frm.doc.merchant_key,
			passphrase: cur_frm.doc.passphrase,
			environment: cur_frm.doc.environment
		}},
		callback: (r) => {
			console.log(r)
			if (r.message.status_code==200){
				frappe.msgprint({
					title: __('Test Connection Success'),
					indicator: 'green',
					message: __(r.message.message),
				})
				cur_frm.enable_save();
			}
			else {
				frappe.msgprint({
					title: __('Test Connection Error'),
					indicator: 'red',
					message: __(r.message.message),
				})
			}
			
		},
		error: (r) => {
			frappe.throw(r.message.message)
		}
	});
	// cur_frm.doc.test_connection.read_only=0;
});
