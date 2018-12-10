'''
  Define some custom error classes
'''
class CustomError(Exception):
        """ Base Class for my exceptions """
        def __init__(self, value):
            self.msg = value

        def __str__(self):
            return repr(self.msg)

        pass

class FailedToGetData( CustomError ):
    pass

class FailedSnmpGet(CustomError):
        def __init__(self, msg):
            self.msg  = msg

class CollectionError(CustomError):
        def __init__(self, msg):
            self.msg  = msg

class FailedToLoadRRDUtil(CustomError):
        def __init__(self, msg):
            self.msg  = msg

class OidsReadError(CustomError):
       def __init__(self, msg):
            self.msg  = msg

class DBConnectionError(CustomError):
        def __init__(self, msg):
            self.msg  = msg

