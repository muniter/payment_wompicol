# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import werkzeug

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WompiColController(http.Controller):

    @http.route(['/payment/wompicol/response',
                 '/payment/wompicol_test/response'],
                type='http',
                auth='public', csrf=False)
    def wompicol_response(self, **post):
        """ Wompi Colombia """
        # The actual response url is configured in Wompi Console, so this url
        # will be hit by the client returning from Web Checkout, but also
        # from Wompi servers, when posting
        # the events.
        if post:
            _logger.info(
                'Wompicol: entering form_feedback with post response data %s',
                pprint.pformat(post))
            request.env['payment.transaction'].sudo().form_feedback(
                    post, 'wompicol')
        else:
            _logger.info('Wompicol: entering form_feedback, client browser.')

        return werkzeug.utils.redirect('/payment/process')
