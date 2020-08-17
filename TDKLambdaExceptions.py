# -*- coding: utf-8 -*-


class TDKLambdaException(Exception):
    def __init__(self, text):
        super(text)


class AddressInUseException(TDKLambdaException):
    def __init__(self):
        super('Address is in use')


addressInUseException = TDKLambdaException('Address is in use')
wrongAddressException = TDKLambdaException('Wrong address')
portCreationError = TDKLambdaException('COM port creation error')