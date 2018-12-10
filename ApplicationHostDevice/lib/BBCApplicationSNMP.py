import os, re, subprocess, time

from twisted.internet import utils
from twisted.internet.defer import DeferredSemaphore, gatherResults

from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationBase import BBCApplicationBase
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCCustomErrors import FailedToGetData

class BBCApplicationSNMP( BBCApplicationBase ):

    sanityOid = '.1.3.6.1.2.1.1.1.0'
    deferred = False 

    def getRunCondition( self ):
        if not getattr( self.device, 'zSnmpMonitorIgnore', None ):
            return True
        else:
            return False

    def getData( self, deferred = False, workers = 1 ):
        self.deferred = deferred
        self.workers = workers

        if self.deferred:

            def inner( runFlag ):
                if runFlag:
                    return self.runDeferredCommand()    
                else:
                    return {}
 
            d = self.snmpSanityCheckDeferred()
            d.addErrback( self.handleError )
            d.addCallback( inner )

            return d

        else:
            if self.snmpRunning( self.snmpSanityCheck() ):
                return self.runCommand()
            else:
                return {}

    def prepareSnmpCmdArgList( self ):
        argList = []

        if  self.device.zSnmpVer == 'v3':
            if getattr(self.device, 'zSnmpProxyContextName', None):
                #/usr/bin/snmpget -Onq -r %s -t %s -%s -u %s -l authPriv -a %s -A %s -x %s -X %s -n %s %s:%s"
                argList.append('-Onq')
                argList.append('-r%s' % getattr(self.device, 'zSnmpTries', 3))
                argList.append('-t%s' % getattr(self.device, 'zSnmpTimeout', 3))
                argList.append('-v3')
                argList.append('-u%s' % getattr(self.device, 'zSnmpSecurityName',     ''))
                argList.append('-lauthPriv')
                argList.append('-a%s' % getattr(self.device, 'zSnmpAuthType'    ,     ''))
                argList.append('-A%s' % getattr(self.device, 'zSnmpAuthPassword',     ''))
                argList.append('-x%s' % getattr(self.device, 'zSnmpPrivType'    ,     ''))
                argList.append('-X%s' % getattr(self.device, 'zSnmpPrivPassword',     ''))
                argList.append('-n%s' % getattr(self.device, 'zSnmpProxyContextName', ''))
                argList.append('%s:%s' % (getattr(self.device, 'zSnmpProxy', ''), getattr(self.device, 'zSnmpPort', '')))

            else:
                #/usr/bin/snmpget -Onq -r %s -t %s -%s -u %s -l authPriv -a %s -A %s -x %s -X %s %s:%s"
                argList.append('-Onq')
                argList.append('-r%s' % getattr(self.device, 'zSnmpTries', 3))
                argList.append('-t%s' % getattr(self.device, 'zSnmpTimeout', 3))
                argList.append('-v3')
                argList.append('-u%s' % getattr(self.device, 'zSnmpSecurityName',     ''))
                argList.append('-lauthPriv')
                argList.append('-a%s' % getattr(self.device, 'zSnmpAuthType'    ,     ''))
                argList.append('-A%s' % getattr(self.device, 'zSnmpAuthPassword',     ''))
                argList.append('-x%s' % getattr(self.device, 'zSnmpPrivType'    ,     ''))
                argList.append('-X%s' % getattr(self.device, 'zSnmpPrivPassword',     ''))
                argList.append('%s:%s' % (self.device.id, getattr(self.device, 'zSnmpPort', '')))
        else:
            #"/usr/bin/snmpget -Onq -r%s -t%s -%s -c%s %s:%s"
            argList.append('-Onq')
            argList.append('-r%s' %  getattr(self.device, 'zSnmpTries',      3))
            argList.append('-t%s' %  getattr(self.device, 'zSnmpTimeout',    3))
            argList.append('-%s'   %  getattr(self.device, 'zSnmpVer',       ''))
            argList.append('-c%s' %  getattr(self.device, 'zSnmpCommunity', ''))
            argList.append('%s:%s' % (self.device.id, getattr(self.device, 'zSnmpPort','')) )

        return argList

    def snmpSanityCheck( self ):
        """ To avoid delays when trying to pull data from device without running SNMP daemon """

        retCode = stdOut = stdErr = None
        cmd = '/usr/bin/snmpget %s %s' % ( ' '.join( self.prepareSnmpCmdArgList() ), self.sanityOid )

        try:
            process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            ( stdOut, stdErr ) = process.communicate()
            retCode = process.returncode
        except Exception, e:
            raise FailedToGetData( "snmpSanityCheck test host %s: \n%s" % ( self.device.id, e ) )

        return ( stdOut, stdErr, retCode )

    def snmpSanityCheckDeferred( self ):
        """ To avoid delays when trying to pull data from device without running SNMP daemon """

        d = utils.getProcessOutputAndValue ( '/usr/bin/snmpget', self.prepareSnmpCmdArgList() + [ self.sanityOid ] )
        d.addErrback( self.handleError )
        d.addCallback( self.snmpRunning )

        return d

    def snmpRunning( self, output ):
        flag = False
        ( stdOut, stdErr, retCode ) = output

        if retCode == 0:
            flag = True 
        else:
            self.handleError( 'SNMP daemon probably down error:%s' % stdErr )
        
        return flag

    def runDeferredCommand( self ):
        self.startTime = time.time()
        self.log.info( '%s using BBCApplicationSNMP' % self.device.id ) 
        self.stats[ 'totalRequests' ] = len( self.device.modelledOids )
        semaf = DeferredSemaphore( self.workers )
        jobs = []

        for oids in self.device.modelledOids:
            self.stats[ 'collectedAppOidCounter' ] += oids.count( '.75025.' )
            df = semaf.run( utils.getProcessOutputAndValue, '/usr/bin/snmpget', self.prepareSnmpCmdArgList() + oids.split() )
            df.addErrback( self.handleError )
            jobs.append( df )

        df = gatherResults( jobs )
        df.addErrback( self.handleError )
        df.addCallback( self.parseOutput )

        return df

    def runCommand( self ):
        self.startTime = time.time()
        self.log.info( '%s using BBCApplicationSNMP' % self.device.id ) 
        ret = val = stErr = None
        cmd = '/usr/bin/snmpwalk %s %s' % ( ' '.join( self.prepareSnmpCmdArgList() ), BBCApplicationBase.BASE_OID )

        try:
            self.log.debug( 'snmp retrieval using %s' % cmd )
            process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            ( val, stErr ) = process.communicate()
            ret = process.returncode
        except Exception, e:
            raise FailedToGetData( "data collection failed for host %s: \n%s" % ( self.device.id, e ) )

        # did it fail ?
        if ret != 0:
            self.log.error( 'An error has been detected during the collection of data: %s\n' % stErr )
            #if int( self.device.productionState ) <= 300:
            #    pass # nothing to do

        return self.parseOutput( val )

    def parseOutput( self, output ):
        self.stats[ 'requestTime' ] = time.time() - self.startTime
        results = {}
        oldSNMPOid = re.compile( '^\.*1.3.6.1.4.1.30754.2.1' )

        if not output: return results # nothing to do

        def parseLine( line ):
                oid, value = line.split( ' ', 1 )

                # get rid of snmp `"` for strings
                value = value.strip( '"' )
                pairs = value.split( '|' )

                # is it BBCApplicationHost meta data ?
                # are there at least two  '|' (3 columns)? If not then skip this row 
                if len( pairs ) < 3:
                    return 
                else:
                    # translate old oid into new format
                    oid = re.sub( oldSNMPOid, BBCApplicationBase.BASE_OID, oid )
                    # add dot if line does not start with it
                    if oid.find( '.' ) != 0:
                        oid = '.' + oid

                    results[ oid ] = value

        # deferred dataset
        if self.deferred:
            for ( stdOut, stdErr, retCode ) in output:

                if retCode == 0:
                    for line in stdOut.split( '\n' ):
                        if len( line ) == 0: continue
                        parseLine( line )
                else:
                    self.handleError( stdErr )
                    self.stats[ 'failedRequests' ] += 1

        else: # for not deferred
            for line in output.split( '\n' ):
                if len( line ) == 0: continue
                parseLine( line )

        return results

    def handleError( self, err ):
        self.log.error( 'Failed to collect data from %s:\n%s' % ( self.device.id, err ) )
