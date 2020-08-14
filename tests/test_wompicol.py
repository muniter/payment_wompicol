import logging
import lxml
from werkzeug import urls

from odoo.addons.payment.tests.common import PaymentAcquirerCommon
from odoo.tests import tagged


_logger = logging.getLogger(__name__)
class WompicolCommon(PaymentAcquirerCommon):

    def setUp(self):
        super(WompicolCommon, self).setUp()
        self.wompicol = self.env.ref('payment_wompicol.payment_acquirer_wompicol')
        self.wompicol.write({
            'wompicol_private_key': 'dummy',
            'wompicol_public_key': 'dummy',
            'wompicol_test_private_key': 'dummy',
            'wompicol_test_public_key': 'dummy',
            'state': 'test',
            # 'wompicol_test_event_url': 'dummy',
            # 'wompicol_event_url': 'dummy',
        })
        self.currency_col = self.env.ref('base.COP')
        self.amount = 44900.00


@tagged('post_install', '-at_install', 'external', '-standard', 'wompicol')
class WompicolForm(WompicolCommon):

    def test_10_wompicol_form_render(self):
        '''Check the form is rendering correctly'''
        self.assertEqual(self.wompicol.state, 'test', 'test without test environment')

        # ----------------------------------------
        # Test: button direct rendering
        # ----------------------------------------

        self.env['payment.transaction'].create({
            'reference': 'wompi_test_transaction',
            'amount': self.amount,
            'currency_id': self.currency_col.id,
            'acquirer_id': self.wompicol.id,
            'partner_id': self.buyer_id
        })

        # render the button
        res = self.wompicol.render('wompi_test_transaction',
                                   self.amount,
                                   self.currency_col.id,
                                   values=self.buyer_values)

        base_url = self.env[
                'ir.config_parameter'
                ].sudo().get_param('web.base.url')

        form_values = {
                "publickey": self.wompicol.wompicol_public_key,
                "currency": self.currency_col.name,
                "amountcents": int(self.amount * 100),
                "referenceCode": 'wompi_test_transaction',
                "redirectUrl": urls.url_join(
                                    base_url,
                                    '/payment/wompicol/client_return'),
                }

        # check form result
        tree = lxml.etree.fromstring(res)
        data_set = tree.xpath("//input[@name='data_set']")
        public_key = tree.xpath("//input[@name='public-key']")
        public_key = tree.xpath("//input[@name='public-key']")
        currency = tree.xpath("//input[@name='currency']")
        # reference = tree.xpath("//input[@name='reference']")

        # Checking number of 'data_set' in the tree
        self.assertEqual(
                len(data_set),
                1,
                'Wompicol: Found %d "data_set" input instead of 1' % len(data_set))
        self.assertEqual(
                data_set[0].get('data-action-url'),
                'https://checkout.wompi.co/p/',
                'wompicol: wrong form GET url')
        self.assertEqual(
                public_key[0].get('value'),
                self.wompicol.wompicol_public_key,
                'wompicol: wrong form render publicKey')
        self.assertEqual(
                currency[0].get('value'),
                'COP',
                'wompicol: Wrong currency only COP is supported')

        # TODO: Test case when currency is not an int, or doesn't end in 00

    def test_20_wompicol_form_management(self):
        self.assertEqual(self.wompicol.state, 'test', 'wompicol: test without test environment')

        # typical data posted by wompi after client has successfully paid
        wompi_event_post = {
              "event": "transaction.updated",
              "data": {
                "transaction": {
                    "id": "01-1532941443-49201",
                    "amount_in_cents": 4490000,
                    "reference": "wompi_test_transaction",
                    "customer_email": "juan.perez@gmail.com",
                    "currency": "COP",
                    "payment_method_type": "NEQUI",
                    "redirect_url": "https://mitienda.com.co/pagos/redireccion",
                    "status": "APPROVED",
                    "shipping_address": None,
                    "payment_link_id": None,
                    "payment_source_id": None
                  }
              },
              "sent_at":  "2018-07-20T16:45:05.000Z"
            }

        # create tx
        tx = self.env['payment.transaction'].create({
            'reference': 'wompi_test_transaction',
            'amount': self.amount,
            'currency_id': self.currency_col.id,
            'acquirer_id': self.wompicol.id,
            'partner_id': self.buyer_id,
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france.id,
            'partner_id': self.buyer_id
        })

        # validate transaction
        tx.form_feedback(wompi_event_post, 'wompicol')
        # check
        self.assertEqual(tx.state, 'done', 'wompicol: wrong state after receiving a valid pending notification')
        self.assertEqual(tx.state_message, f'Wompicol states the transactions as APPROVED', 'wompicol: bad state message')
        self.assertEqual(tx.acquirer_reference, 'wompi_test_transaction', 'wompicol: wrong txn_id after receiving a valid approved notification')

        # update transaction
        tx.write({
            'state': 'draft',
            'acquirer_reference': False})

        # Now test with a pending
        wompi_event_post["data"]["transaction"]["status"] = 'PENDING'
        # validate transaction
        tx.form_feedback(wompi_event_post, 'wompicol')
        # check transaction
        self.assertEqual(tx.state, 'pending', 'wompicol: wrong state after receiving a valid pending notification')
        self.assertEqual(tx.state_message, f'Wompicol states the transactions as PENDING', 'wompicol: bad state message')
