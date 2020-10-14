import logging
import pprint
import werkzeug
import json

from odoo import http
from odoo.http import request
from odoo.http import Response
from odoo.addons.payment.models.payment_acquirer import ValidationError

_logger = logging.getLogger(__name__)


class WompiColController(http.Controller):

    @http.route(['/payment/wompicol/response',
                '/payment/wompicol_test/response'],
                type='json', auth='public', csrf=False)
    def wompicol_response(self):
        """ Wompi Colombia """
        # Wompi servers will post the event information
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
        post = json.loads(request.httprequest.data)
        if post:
            # If entered on the test endpoint, let's add it to the data
            if 'wompicol_test' in request.httprequest.path:
                post["test"] = 1

            # Log the event data
            _logger.info(
                'Wompicol: entering form_feedback with post response data %s',
                pprint.pformat(post))

            ref = post.get('data', {}).get('transaction', {}).get('reference', {})
            if '_' in ref:
                post['data']['transaction']['reference'] = ref.split('_')[0]

            if post.get('noconfirm'):
                raise ValidationError('Wompicol: should not receive "noconfirm" on the controller')

            # Process the data
            request.env['payment.transaction'].sudo().form_feedback(
                    post,
                    'wompicol')
        else:
            _logger.info(
                'Wompicol: for feedback entered with incomplete data %s',
                pprint.pformat(post))

        return werkzeug.utils.redirect('/')

    @http.route('/payment/wompicol/client_return', type='http',
                auth='public', csrf=False)
    def wompicol_client_return(self, **post):
        """ Wompi Colombia """
        # The client browser will comeback with the following data
        # {
        #   'env': 'test',
        #   'id': '16056-1597266116-33603'
        # }

        _logger.info('Wompicol: client browser returning. %s',
                     pprint.pformat(post))
        if post:
            id = post.get('id')
            env = post.get('env')
            env = env if env == 'test' else 'prod'
            # Process the data
            request.env[
                    'payment.transaction'
                    ].sudo()._wompicol_get_data_manually(id, env)

        return werkzeug.utils.redirect('/payment/process')
