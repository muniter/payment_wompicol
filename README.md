# Wompi Colombia Payment Acquirer

This is an implementation of the [Wompi](https://wompi.co/) payment acquirer/gateway for Odoo 13, in the form of web checkout, as specified in the [documentation](https://docs.wompi.co/docs/en/widget-checkout-web).

## Notes

This integration uses the *checkout* type of integration, in which the client is sent with an HTTP GET request, with the data encoded in the url, to the Wompi site, in which they perform the payment. After the payment has been completed, Wompi servers POST some json to the event url (which is defined in their platform backend, this module will tell you what you should set it to), this data is processed to set the transaction state in Odoo, if the client get's back and no event has been received we ask their api.

### Steps

1. Client redirected to Wompi page with the data encoded in the url.
1. Wompi POST event (what happened with the transaction).
    1. The posted data is processed to see if it makes sense
    1. Since there's no crypto to verify is legit, we query their endpoint, and compare what they report vs what was received.
    1. Set the transaction state.
1. Client browser comes back only with Wompi internal transaction id.
    1. We check if there's transaction with reference code that matches wompi transcation id.
    1. If there's one we do nothing, this means the event reached first and it has been processed.
    1. If there's nothing, we call their api with the transaction id, and we simulate as if it was a received event, but in this case their api won't be called for the information to confirm.

## STATUS: WORKING Odoo 13.0

## License MIT
