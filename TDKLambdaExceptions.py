# -*- coding: utf-8 -*-


class TDKLambdaException(Exception):
    pass

class AddressInUseException(TDKLambdaException):
    pass

addressInUseException = TDKLambdaException('Address is in use')
wrongAddressException = TDKLambdaException('Wrong address')
portCreationException = TDKLambdaException('COM port creation error')