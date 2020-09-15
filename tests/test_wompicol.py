import logging
import math
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
        self.amount = 44900.23


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
                "amountcents": math.ceil(self.amount) * 100,
                "referenceCode": 'wompi_test_transaction',
                "redirectUrl": urls.url_join(
                                    base_url,
                                    '/payment/wompicol/client_return'),
                }

        # check form result
        tree = lxml.etree.fromstring(res)
        data_set = tree.xpath("//input[@name='data_set']")
        public_key = tree.xpath("//input[@name='public-key']")[0].get('value')
        currency = tree.xpath("//input[@name='currency']")[0].get('value')
        amount = tree.xpath("//input[@name='amount-in-cents']")[0].get('value')

        # Data set in the tree
        self.assertEqual(
                len(data_set),
                1,
                'Wompicol: Found %d "data_set" inputs instead of 1' % len(data_set))
        # Proper action url
        self.assertEqual(
                data_set[0].get('data-action-url'),
                'https://checkout.wompi.co/p/',
                'wompicol: wrong form action url')
        # Proper public key
        self.assertEqual(
                public_key,
                form_values["publickey"],
                'wompicol: wrong form render publicKey')
        # Proper amount in cents only 00 at the end
        self.assertTrue(str(amount)[-2:] == '00',
                'wompicol: wrong amount %s, only 00 allowed as last two digits.'
                % amount)
        # Proper amount in cents
        self.assertEqual(
                amount,
                str(form_values["amountcents"]),
                'wompicol: wrong amount of cents rendered')
        # Propeor currency value
        self.assertEqual(
                currency,
                'COP',
                'wompicol: Wrong currency only COP is supported')

    def test_20_wompicol_form_management(self):
        self.assertEqual(self.wompicol.state, 'test', 'wompicol: test without test environment')

        # typical data posted by wompi after client has successfully paid
        wompi_event_post = {
              "event": "transaction.updated",
              "data": {
                "transaction": {
                    "id": "01-1532941443-49201",
                    "amount_in_cents": 4490100,
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
              "sent_at":  "2018-07-20T16:45:05.000Z",
              "noconfirm": 1, # Avoids calling wompi api with false id
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
        # Check the transaction is set to done when APPROVED is received.
        self.assertEqual(
                tx.state,
                'done',
                'wompicol: wrong state after receiving a valid approved notification')
        # Check if the created acquirer reference is equal to what wompi sent
        self.assertEqual(
                tx.acquirer_reference,
                '01-1532941443-49201',
                'wompicol: wrong txn_id after receiving a valid event notification')
        # TODO: Implement this test.
        # Check the order was set as a sale order once the transaction was approved
        # self.assertEqual(
        #         tx.state,
        #         'done',
        #         'wompicol: wrong state after receiving a valid approved notification')

        # update transaction
        tx.write({
            'state': 'draft',
            'acquirer_reference': False})

        # Now test with a pending
        wompi_event_post["data"]["transaction"]["status"] = 'PENDING'

        # validate transaction now with new state
        tx.form_feedback(wompi_event_post, 'wompicol')

        # Check the transaction is set to done when PENDING is received.
        self.assertEqual(
                tx.state,
                'pending',
                'wompicol: wrong state after receiving a valid pending notification')
        # Check if the created acquirer reference is equal to what wompi sent
        self.assertEqual(
                tx.acquirer_reference,
                '01-1532941443-49201',
                'wompicol: wrong txn_id after receiving a valid event notification')
