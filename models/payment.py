# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import uuid

from hashlib import md5
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class PaymentAcquirerWompicol(models.Model):
    _inherit = 'payment.acquirer'

    # This fields are what's needed to configure the payment acquirer
    # These are extensions, there is a field state, which can be 'enabled'
    # 'test' or 'disabled' in this case, 'enabled' is 'prod'.
    provider = fields.Selection(selection_add=[('wompicol', 'Wompi Colombia')])
    wompicol_private_key = fields.Char(
            string="Wompi Colombia Private API Key",
            required_if_provider='wompicol',
            groups='base.group_user'
            )
    wompicol_public_key = fields.Char(
            string="Wompi Colombia Public API Key",
            required_if_provider='wompicol',
            groups='base.group_user'
            )
    wompicol_test_private_key = fields.Char(
            string="Wompi Colombia Test Private API Key",
            required_if_provider='wompicol',
            groups='base.group_user'
            )
    wompicol_test_public_key = fields.Char(
            string="Wompi Colombia Test Public API Key",
            required_if_provider='wompicol',
            groups='base.group_user'
            )
    wompicol_event_url = fields.Char(
            string="Wompi Colombia URL de Eventos",
            required_if_provider='wompicol',
            groups='base.group_user',
            readonly=True,
            store=False,
            compute='_wompicol_event_url'
            )
    wompicol_test_event_url = fields.Char(
            string="Wompi Colombia URL Test de Eventos",
            required_if_provider='wompicol',
            groups='base.group_user',
            readonly=True,
            store=False,
            compute='_wompicol_event_url'
            )

    def _wompicol_event_url(self):
        """Set the urls to config in the wompi console"""
        prod_url = ''
        test_url = ''
        if self.provider == 'wompicol':
            base_url = self.env[
                    'ir.config_parameter'
                    ].sudo().get_param('web.base.url')
            prod_url = f"{base_url}/payment/wompicol/response"
            test_url = f"{base_url}/payment/wompicol_test/response"

        self.wompicol_event_url = prod_url
        self.wompicol_test_event_url = test_url

    def _get_wompicol_api_url(self, environment):
        """This method should be called to get the api
        url to query depending on the environment."""
        if environment == 'prod':
            return 'https://production.wompi.co/v1'
        else:
            return 'https://sandbox.wompi.co/v1'

    def _get_wompicol_urls(self, environment):
        """ Wompi Colombia URLs this method should be called to
        get the url to post the form"""
        return "https://checkout.wompi.co/p/"

    def _get_keys(self, environment=None):
        """Wompi keys change wether is prod or test
        returns a tuple with (pub, prod) dending on
        environment return the appropiate key."""
        if not environment:
            environment = 'prod' if self.state == 'enabled' else 'test'

        if environment == 'prod':
            prv = self.wompicol_private_key
            pub = self.wompicol_public_key
            return(prv, pub)
        else:
            test_prv = self.wompicol_test_private_key
            test_pub = self.wompicol_test_public_key
            return(test_prv, test_pub)

    def wompicol_form_generate_values(self, values):
        # The base url
        base_url = self.env[
                'ir.config_parameter'
                ].sudo().get_param('web.base.url')
        # The payment transaction
        tx = self.env[
                'payment.transaction'
                ].search([('reference', '=', values.get('reference'))])
        # _logger.info(f"What is tx {tx}")
        # _logger.info(f"What is values {values}")

        # Wompi won't allow duplicate reference code even if payment was
        # failed last time, so replace reference code if payment is not
        # done or pending. Or is it handled by the base class?
        if tx.state not in ['done', 'pending']:
            # Replace the reference code with a new one
            tx.reference = str(uuid.uuid4())
        wompicol_tx_values = dict(
            values,
            # wompi_url="https://checkout.wompi.co/p/",
            publickey=self._get_keys()[1],
            currency=values['currency'].name,  # COP, is the only one supported
            amountcents=int(values['amount'] * 100),  # Cents, *100 and an int
            referenceCode=f"{values['reference']}-{tx.reference}",
            redirectUrl=urls.url_join(base_url, '/payment/wompicol/client_return'),
        )
        return wompicol_tx_values

    def wompicol_get_form_action_url(self):
        '''This method gets called by odoo and should return the url
        of to submit the form on button press'''
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_wompicol_urls(environment)


class PaymentTransactionWompiCol(models.Model):
    _inherit = 'payment.transaction'

    # Example Data dict comming from wompicol
    # {
    #   "event": "transaction.updated",
    #   "data": {
    #     "transaction": {
    #         "id": "01-1532941443-49201",
    #         "amount_in_cents": 4490000,
    #         "reference": "MZQ3X2DE2SMX",
    #         "customer_email": "juan.perez@gmail.com",
    #         "currency": "COP",
    #         "payment_method_type": "NEQUI",
    #         "redirect_url": "https://mitienda.com.co/pagos/redireccion",
    #         "status": "APPROVED",
    #         "shipping_address": null,
    #         "payment_link_id": null,
    #         "payment_source_id": null
    #       }
    #   },
    #   "sent_at":  "2018-07-20T16:45:05.000Z"
    # }

    @api.model
    def _wompicol_form_get_tx_from_data(self, data):
        """ Given a data dict coming from wompicol, verify it
        and find the related transaction record. """
        tx_data = data.get('data').get('transaction')
        # Important fields to recognize the transaction
        reference = tx_data.get('reference')
        txnid = tx_data.get('id')

        if not reference or not txnid:
            raise ValidationError(_('WompiCol: received data with missing reference (%s) or transaction id (%s)') % (reference, txnid))

        transaction = self.search([('reference', '=', reference)])

        if not transaction:
            error_msg = (_('WompiCol: received data for reference %s; no order found') % (reference))
            raise ValidationError(error_msg)
        elif len(transaction) > 1:
            error_msg = (_('WompiCol: received data for reference %s; multiple orders found') % (reference))
            raise ValidationError(error_msg)
        else:
            _logger.info = ('WompiCol: Recieved reference %s transaction id found %s', (reference, transaction.id))

        return transaction

    def _wompicol_form_get_invalid_parameters(self, data):
        """ Given a data dict coming from wompicol, verify it and
        return any invalid parameters, to stop the processing of the
        transaction and log it."""
        invalid_parameters = []
        tx_data = data.get('data').get('transaction')

        # If amount to pay don't match
        amount_in_cents = int(self.amount * 100)
        if int(tx_data.get('amount_in_cents', '0')) != amount_in_cents:
            invalid_parameters.append(('Amount', tx_data.get('amount_in_cents'), '%' % amount_in_cents))

        # If the reference code doesn't match
        if self.acquirer_reference and tx_data.get('reference') != self.acquirer_reference:
            invalid_parameters.append(('Reference code', tx_data.get('reference'), self.acquirer_reference))

        return invalid_parameters

    def _wompicol_form_validate(self, data):
        """ Given a data dict coming from wompicol, that has an
        existing payment transaction associated with it, and has
        passed the _wompicol_form_get_invalid_parameters set the
        state of the transaction."""

        # Make sure this method is run agains only one record
        self.ensure_one()

        tx_data = data.get('data').get('transaction')
        status = tx_data.get('status')
        res = {
            'acquirer_reference': tx_data.get('reference'),
            'state_message': f"Wompicol states the transactions as {status}"
        }

        if status == 'APPROVED':
            _logger.info('Validated WompiCol payment for tx %s: set as done' % (self.reference))
            res.update(state='done', date=fields.Datetime.now())
            self._set_transaction_done()
            self.write(res)
            self.execute_callback()
            return True
        elif status == 'PENDING':
            _logger.info('Received notification for WompiCol payment %s: set as pending' % (self.reference))
            res.update(state='pending')
            self._set_transaction_pending()
            return self.write(res)
        elif status in ['VOIDED', 'DECLINED', 'ERROR']:
            _logger.info('Received notification for WompiCol payment %s: set as Cancel' % (self.reference))
            res.update(state='cancel')
            self._set_transaction_cancel()
            return self.write(res)
        else:
            error = 'Received unrecognized status for WompiCol payment %s: %s, set as error' % (self.reference, status)
            _logger.info(error)
            res.update(state='cancel', state_message=error)
            self._set_transaction_cancel()
            return self.write(res)
