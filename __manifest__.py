# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Wompi Payment Acquirer',
    'author': 'Lintec Tecnología',
    'category': 'Accounting/Payment',
    'summary': 'Payment Acquirer: Wompi Colombia Implementation',
    'description': """Wompi Colombia payment acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payment_views.xml',
        'views/payment_wompicol_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'post_init_hook': 'create_missing_journal_for_acquirers',
}
