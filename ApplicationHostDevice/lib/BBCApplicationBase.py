import os, re, subprocess, time
 
class BBCApplicationBase:
 
    BASE_OID        = '.1.3.6.1.4.1.2333.3.2'
    device          = None

    def __init__( self, device, log ):
        self.device = device
        self.log = log

        self.stats = {
            'requestTime'               :0.0,
            'totalRequests'             :0,
            'failedRequests'            :0,
            'totalTime'                 :time.time(),
            'oidsCounter'               :0,
            'collectedAppOidCounter'    :0,
            'brokenAppOidCounter'       :0,
            'foundAppOidCounter'        :0,
            'collectedKpiOidCounter'    :0,
            'brokenKpiOidCounter'       :0
        }

    def getRunCondition( self ):
        """ Test if the device zProperties for device collection were set. """
        pass
 
    def getData( self ):
        """ Get the data in BBC Application format. """
        pass
