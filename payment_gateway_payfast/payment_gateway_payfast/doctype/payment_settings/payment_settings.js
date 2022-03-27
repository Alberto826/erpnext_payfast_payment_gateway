// Copyright (c) 2022, Alberto Gutierrez and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payment Settings', {
	// refresh: function(frm) {

	// }
});

frappe.ui.form.on('Payment Settings', 'test_connection', function(){
	frappe.call({
		method:'payment_gateway_payfast.payment_gateway_payfast.doctype.payment_settings.payment_settings.test_connection',
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
	})
});
