import logging
import uuid
import math
import requests
import pprint
import time
import random

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

    def _get_wompicol_api_url(self, environment=None):
        """This method should be called to get the api
        url to query depending on the environment."""
        if not environment:
            environment = 'prod' if self.state == 'enabled' else 'test'

        if environment == 'prod':
            return 'https://production.wompi.co/v1'
        else:
            return 'https://sandbox.wompi.co/v1'

    def _get_wompicol_urls(self):
        """ Wompi Colombia URLs this method should be called to
        get the url to GET the form"""
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
        # Get the payment transaction
        tx = self.env[
                'payment.transaction'
                ].search([('reference', '=', values.get('reference'))])

        if values['currency'].name != 'COP':
            error_msg = (
                _('WompiCol: Only accepts COP as the currency, received')
                % (values['currency'].name))
            raise ValidationError(error_msg)

        wompiref = f"{tx.reference}_{int(random.random() * 1000)}"

        wompicol_tx_values = dict(
            values,
            publickey=self._get_keys()[1],
            currency='COP',
            # Wompi wants cents (*100) and has to end on 00.
            amountcents=math.ceil(values['amount']) * 100,
            referenceCode=wompiref,
            redirectUrl=urls.url_join(base_url, '/payment/wompicol/client_return'),
        )
        return wompicol_tx_values

    def wompicol_get_form_action_url(self):
        '''This method gets called by odoo and should return the url
        of to action the form data on button press'''
        self.ensure_one()
        return self._get_wompicol_urls()


class PaymentTransactionWompiCol(models.Model):
    _inherit = 'payment.transaction'

    def _wompicol_get_data_manually(self, id, environment):
        """When the client has returned and the payment transaction hasn't been
        updated, check manually and update the transaction"""
        # Check first if this transaciont has been updated already
        if id:
            tx = self.env[
                    'payment.transaction'
                    ].search([('acquirer_reference', '=', id)])
            if len(tx):
                _logger.info("Wompicol: Not getting data manually, transaction already updated.")
                return

        api_url = self.acquirer_id._get_wompicol_api_url(environment)
        request_url = f"{api_url}/transactions/{id}"
        wompi_data = requests.get(request_url, timeout=60)
        # If request succesful
        if wompi_data.status_code == 200:
            wompi_data = wompi_data.json()
            _logger.info("Wompicol: Sucesfully called api for id: %s it returned data: %s"
                         % (id, pprint.pformat(wompi_data)))
            # pprint.pformat(post))
            # Data needed to validate is just on 'data'
            # Format it how it expects it
            wompi_data["data"] = {"transaction": wompi_data["data"]}
            # Fix the reference code, only what's previous to _ is what we want
            ref = wompi_data['data']['transaction']['reference']
            if '_' in ref:
                wompi_data['data']['transaction']['reference'] = ref.split('_')[0]
            # This avoid confirming the event, since the data is being
            # asked from the server. Instead of listening.
            wompi_data["noconfirm"] = True
            # If the transaction is a test.
            if environment == 'test':
                wompi_data["test"] = True
            _logger.info("Wompicol: creating transaction manually, by calling the api for acquirer reference %s" % id)
            self.env['payment.transaction'].sudo().form_feedback(wompi_data, 'wompicol')

    def _wompicol_confirm_event(self, data):
        """Wompi doesn't send anything to validate the event is
        truthful, or that it comes from them, this method validates
        by calling their api, and comparing values if values match
        returns True, else throws an error"""

        # This is the response from wompi when asking about a transaction
        # {
        #    "data": {
        #        "id": "16056-1597438570-47962",
        #        "created_at": "2020-08-14T20:56:10.676Z",
        #        "amount_in_cents": 3713000,
        #        "reference": "aba6c7cb-9846-482e-877f-1e55b556d588",
        #        "currency": "COP",
        #        "payment_method_type": "BANCOLOMBIA_TRANSFER",
        #        "payment_method": {
        #            "type": "BANCOLOMBIA_TRANSFER",
        #            "extra": {
        #                "async_payment_url": "https://sandbox.wompi.co/v1/payment_methods/redirect/bancolombia_transfer?transferCode=suDIdSULBpusICGr-approved",
        #                "external_identifier": "suDIdSULBpusICGr-approved"
        #            },
        #            "user_type": "PERSON",
        #            "sandbox_status": "APPROVED",
        #            "payment_description": "Pago a Cool Company, ref: aba6c7cb-9846-482e-877f-1e55b556d588"
        #        },
        #        "redirect_url": "http://localhost:8069/payment/wompicol/client_return",
        #        "status": "APPROVED",
        #        "status_message": null,
        #        "merchant": {
        #            "name": "Cool Company",
        #            "legal_name": "My Company",
        #            "contact_name": "John Doe",
        #            "phone_number": "+5730000000",
        #            "logo_url": null,
        #            "legal_id_type": "NIT",
        #            "email": "example@example.com",
        #            "legal_id": "90000000-8"
        #        }
        #    },
        #    "meta": {}
        # }

        # Values to check
        to_check = ['id', 'reference', 'currency', 'status', 'amount_in_cents']
        # Data posted to the server
        tx_data = data.get('data').get('transaction')
        # Get the api url
        api_url = self.acquirer_id._get_wompicol_api_url(data.get('test'))
        # Format the url
        request_url = f"{api_url}/transactions/{tx_data.get('id')}"
        # ask for the data
        wompi_data = requests.get(request_url, timeout=60)
        _logger.info('Wompicol: calling wompi api to validate the data.')
        # If request succesful
        if wompi_data.status_code == 200:
            # Data needed to validate is just on 'data'
            wompi_data = wompi_data.json().get('data')
            # Fix the reference code, only what's previous to _ is what we want
            if '_' in wompi_data['reference']:
                wompi_data['reference'] = wompi_data['reference'].split('_')[0]
            # Basically compare between event received and what wompi api says
            # if a value doesnt match add tuple (name, value)
            invalid = [(val, tx_data.get(val)) for val in to_check
                       if tx_data.get(val) != wompi_data.get(val)]

            if any(invalid):
                error_msg = (_('WompiCol: validation of data received vs reported by wompi api failed for parameters %s') % (invalid))
                raise ValidationError(error_msg)
            else:
                _logger.info('Wompicol: data received sucessfully validated with wompi api')
                return True
        else:
            _logger.warn('Wompicol: unable to query wompi api for transaction ref: %s, response code %s' % (self.reference, wompi_data.status_code))
            return False

    @api.model
    def _wompicol_form_get_tx_from_data(self, data):
        """ Given a data dict coming from wompicol, verify it
        and find the related transaction record. """
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

        # Important fields to recognize the transaction
        tx_data = data.get('data').get('transaction')
        reference = tx_data.get('reference')
        txnid = tx_data.get('id')

        if not reference or not txnid:
            raise ValidationError(_('WompiCol: received data with missing reference: (%s) or transaction id: (%s)') % (reference, txnid))

        transaction = self.search([('reference', '=', reference)])

        if not transaction:
            error_msg = (_('WompiCol: received data for reference: %s; no order found') % (reference))
            raise ValidationError(error_msg)
        elif len(transaction) > 1:
            error_msg = (_('WompiCol: received data for reference: %s; multiple orders found') % (reference))
            raise ValidationError(error_msg)
        else:
            _logger.info('WompiCol: received reference: %s transaction id found: %s' % (reference, transaction.id))

        return transaction

    def _wompicol_form_get_invalid_parameters(self, data):
        """ Given a data dict coming from wompicol, verify it and
        return any invalid parameters, to stop the processing of the
        transaction and log it."""
        invalid_parameters = []
        tx_data = data.get('data').get('transaction')

        # If amount to pay don't match
        # Wompi wants cents (*100) and has to end on 00.
        amount_in_cents = math.ceil(self.amount) * 100
        if int(tx_data.get('amount_in_cents', '0')) != amount_in_cents:
            invalid_parameters.append(('Amount',
                                       tx_data.get('amount_in_cents'), '%'
                                       % amount_in_cents))

        # If the id from wompi and the id set existing doesn't match
        # this is maínly for transaction updates.
        if self.acquirer_reference and tx_data.get('id') \
           != self.acquirer_reference:
            invalid_parameters.append(('Reference code',
                                       tx_data.get('id'),
                                       self.acquirer_reference))

        if not invalid_parameters:
            _logger.info('Wompicol: tx %s: has no invalid parameters'
                         % (self.reference))

        return invalid_parameters

    def _wompicol_form_validate(self, data):
        """ Given a data dict coming from wompicol, that has an
        existing payment transaction associated with it, and has
        passed the _wompicol_form_get_invalid_parameters set the
        state of the transaction."""

        # Make sure this method is run agains only one record
        self.ensure_one()

        # Simplify data access
        tx_data = data.get('data').get('transaction')
        status = tx_data.get('status')

        # Check if the data received matches what's in wompi servers
        # Do not do it if running and odoo test, or if the data was
        # queried, not received.
        if not data.get('noconfirm', False):
            self._wompicol_confirm_event(data)

        res = {
            'acquirer_reference': tx_data.get('id'),  # Wompi internal id
            'state_message': f"Wompicol states the transactions as {status}"
        }

        # If came from the test endpoint
        if data.get('test'):
            res["state_message"] = 'TEST TRANSACTION: ' + res["state_message"]

        if status == 'APPROVED':
            _logger.info('Validated WompiCol payment for tx %s: setting as done' % (self.reference))
            res.update(state='done', date=fields.Datetime.now())
            self._set_transaction_done()
            # Takes care of setting the order as paid right away
            self.write(res)
            self.execute_callback()
            if not self.is_processed:
                self._post_process_after_done()
            return True
        elif status == 'PENDING':
            _logger.info('Received notification for WompiCol payment %s: setting as pending' % (self.reference))
            res.update(state='pending')
            self._set_transaction_pending()
            return self.write(res)
        elif status in ['VOIDED', 'DECLINED', 'ERROR']:
            _logger.info('Received notification for WompiCol payment %s: setting as Cancel' % (self.reference))
            res.update(state='cancel')
            self._set_transaction_cancel()
            return self.write(res)
        else:
            error = 'Received unrecognized status for WompiCol payment %s: %s, setting as error' % (self.reference, status)
            _logger.info(error)
            res.update(state='cancel', state_message=error)
            self._set_transaction_cancel()
            return self.write(res)
