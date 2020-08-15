# Wompi Colombia Payment Acquirer

This is an implementation of the [Wompi](https://wompi.co/) payment acquirer/gateway for Odoo, in the form of web checkout, as specified in the [documentation](https://docs.wompi.co/docs/en/widget-checkout-web).

## STATUS: WIP

### Progress

This are the check list to implement Wompi.

- [x] What is the private key used for?
    NOTE: To use the api integration, but also to check on the state of a transaction.
- [x] Url for prod and testing
- [x] Wompi controller with different url for testing.
    - [x] Implement a way to log if test Transaction
            NOTE: The state message will show if the transaction is a test
- [x] Key formatting per environment NOTE: Wompi doesn't format the keys, It just had completely different keys. So two new fields must be created to deal with this.
- [x] Values required by Wompi
    - [x] Fix method, odoo sends POST by default, Wompi wants GET.
        - [x] Fix the way I'm accomplishing this, use JS super instead.
    - [x] Seems like wompi wants values ending in 00 fix this
        NOTE: Fixed with `math.ciel` and also created test cases.
- [x] ResponseUrl, process when It's client GET and not wompi api POST.
    NOTE: Wompi client comes back with the wompi transcation ID. 
    - [x] Send the client to the transaction outcome page
    - [x] Filter so only wompi posts are processed
        NOTE: Ended up just not handling it in the same method.
    - [x] Test
- [x] Controller method on response url
    - [x] Payment Transaction methods to process Wompi events.
        - [x] Instruction to what url for events to set on the wompi console.
            - [x] Test if on change of the base url, test and prod url also changes in the config.
        - [x] _wompicol_form_get_tx_from_data process the data from the acquirer and validates, a transaction exists, if exists it's returned, if more than one or none are found, error out.
        - [x] _wompicol_form_get_invalid_parameters: Returns invalid parameters sent from the payment acquirer or a fake request, ant the parent class takes care of logging it.
        - [x] _wompicol_form_validate takes care of setting the transaction state from the received data given it passes the invalid_parameters method.
        - [x] Call wompi api to check if the event is actually true.
            - [ ] Test
- [x] Tests

## License MIT
