import os, re, subprocess, time, commands

from twisted.internet import defer, utils, reactor

from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationBase import BBCApplicationBase
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCCustomErrors import FailedToGetData


class BBCApplicationSSH( BBCApplicationBase ):

    def getRunCondition( self ):
        if getattr( self.device, 'zBBCUseSSH', None ) \
            and getattr( self.device, 'zKeyPath', None ) \
            and os.path.isfile( self.device.zKeyPath ) \
            and getattr( self.device, 'zCommandUsername', None ):
                return True
        else:
            return False

    def getData( self, deferred = False ):
        if deferred:
            return self.runDeferredCommand()
        else:
            return self.runCommand()

    def runDeferredCommand( self ):
        self.log.info( '%s using BBCApplicationSSH Deferred' % self.device.id )
        self.startTime = time.time()
        self.stats[ 'failedRequests' ] = 1
        self.stats[ 'totalRequests' ] = 1
        
        sshwrapper = os.path.join(os.path.dirname(__file__),'sshWrapper.py')
        self.log.debug("file name is %s" %sshwrapper )
        d = defer.Deferred()
        try:
        # 'ssh -q -o StrictHostKeyChecking=no -i %s %s@%s "grep -h \'|\' /usr/local/var/snmp/data/1.3.6.1.4.1*"'
            d = utils.getProcessOutputAndValue( sshwrapper, args = [str(getattr(self.device, 'zSSHTimeout', 10)), self.device.zKeyPath, self.device.zCommandUsername, self.device.id], path = None, env = {})
            d.addCallbacks( self.parseOutput, self.handleError )
        except Exception, e:
            self.log.error("Error in run deferred command, exception is %s" %str(e))
        return d

    def runCommand( self ):
        self.startTime = time.time()
        self.log.info( '%s using BBCApplicationSSH' % self.device.id )
        val = ret = stErr = None
        sshwrapper = os.path.join(os.path.dirname(__file__),'sshWrapper.py')
        self.log.debug("file name is %s" %sshwrapper )
        cmd = '%s %s %s %s %s' %(sshwrapper, str(getattr(self.device, 'zSSHTimeout', 10)), self.device.zKeyPath, self.device.zCommandUsername, self.device.id)
        
        try:
            self.log.debug( 'ssh retrieval using %s' % cmd )
            process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
            ( val, stErr ) = process.communicate()
            ret = process.returncode
        except Exception, e:
            raise FailedToGetData( "ssh failed for host %s: \n%s" % ( self.device.id , e ) )

        # did it fail ?
        if ret != 0:
            self.log.error( 'An error has been detected during the collection of data for device %s: <%s>' %(self.device.id, stErr) )        
    
        return self.parseOutput( val, deferred =False )

    def parseOutput( self, output, deferred = True ):
        if deferred:
            (out, err, code) = output
            self.log.debug("out is %s err is %s and code is %s" %(out, err, code))
            if code != 0:
                raise FailedToGetData( "ssh failed for host %s: \n%s" % ( self.device.id , err ) )
            output = out
        self.stats[ 'failedRequests' ] -= 1
        self.stats[ 'requestTime' ] = time.time() - self.startTime
        results = {}
        
        if not output: return results

        self.stats[ 'collectedAppOidCounter' ] += output.count('.75025.')
        # parse results table
        oldSNMPOid = re.compile( '^\.*1.3.6.1.4.1.30754.2.1' )
      
        for line in output.split( '\n' ):
            # translate old oid into new format
	        #print str(line) + '#'
            line = re.sub( oldSNMPOid, BBCApplicationBase.BASE_OID, line )

            # add dot if line does not start with it
            if line.find( '.' ) != 0:
                line = '.' + line

            # split line
            lineParts = re.split( '[\s|\t]+', line, 2 )
            if len( lineParts ) == 3:
            	lineParts[ 1 ] = lineParts[ 1 ].lower()

            	# is it BBCApplicationHost meta data ?
                if lineParts[ 1 ] == "string" :
                    results[ lineParts[ 0 ] ] = lineParts[ 2 ]
        return results

    def handleError( self, err ):
        self.log.error( 'Failed to collect data from %s:\n%s' % ( self.device.id, err ) )
