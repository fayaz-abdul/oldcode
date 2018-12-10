__doc__="""BBCApplicationMap

This modeler builds 2 level nested structures:
    Apps -> tests
    or
    Apps -> kpis
"""
import os
import time
import re
import subprocess
from Products.ZenModel.ZenPackPersistence import ZenPackPersistence
from Products.ZenUtils.Utils import cleanstring, unsigned, prepId
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import MultiArgs
from Products.ZenEvents.ZenEventClasses import *
import logging
import xmlrpclib

from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSNMPFormatTest import BBCApplicationSNMPFormatTest
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSSH import BBCApplicationSSH
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSNMP import BBCApplicationSNMP
from ZenPacks.BBC.ApplicationHostDevice.lib.utils import ConfigParser

log = logging.getLogger("zen.zenmodeler")

class BBCApplicationMap( PythonPlugin ):

    ZENPACKID = 'Zenpacks.BBC.ApplicationHostDevice'
    relname = "applications"
    modname = "ZenPacks.BBC.ApplicationHostDevice.BBCApplication"

    def copyDataToProxy(self, device, proxy):

        # ssh
        proxy.zKeyPath                          = device.zKeyPath
        proxy.zCommandUsername                  = device.zCommandUsername
        proxy.zBBCUseSSH                        = device.zBBCUseSSH
        proxy.zSSHTimeout                       = device.zSSHTimeout
        proxy.zBBCAdditionalAppOidSpace         = device.zBBCAdditionalAppOidSpace
        proxy.zMaxOIDPerRequest                 = device.zMaxOIDPerRequest

        # snmp
        proxy.zSnmpMonitorIgnore    = device.zSnmpMonitorIgnore
        proxy.zSnmpTries            = device.zSnmpTries
        proxy.zSnmpTimeout          = device.zSnmpTimeout
        proxy.zSnmpVer              = device.zSnmpVer
        proxy.zSnmpSecurityName     = device.zSnmpSecurityName
        proxy.zSnmpAuthType         = device.zSnmpAuthType
        proxy.zSnmpAuthPassword     = device.zSnmpAuthPassword
        proxy.zSnmpPrivType         = device.zSnmpPrivType
        proxy.zSnmpPrivPassword     = device.zSnmpPrivPassword
        proxy.zSnmpProxyContextName = device.zSnmpProxyContextName
        proxy.zSnmpProxy            = device.zSnmpProxy
        proxy.zSnmpPort             = device.zSnmpPort 
        proxy.zSnmpCommunity        = device.zSnmpCommunity

        proxy.perfServer            = device.getPerformanceServer().id
        #proxy.productionState       = device.productionState
        
        result                      = PythonPlugin.copyDataToProxy(self, device, proxy)

        return result

    def collect( self, device, log ):
     
        collection_order = [ BBCApplicationSSH, BBCApplicationSNMP ]
        collection = None
   
        try:
            for key in collection_order:
                collection = key ( device, log )
                if collection.getRunCondition():
                    return collection.getData()
        except Exception, e:
           log.error('An error has been detected during the collection of data from %s : %s' % ( device.id, str(e) ) )

        return {}

    def process( self, device, results, log ):
        """
        Convert data into interface objects.
        """
        log.info('Modeler %s processing data for device %s', self.name(), device.id)

        if len( results ) == 0:
            log.error("Unable to get data for %s" % device.id)
            return None

        rm = self.relMap()

        #load config values
        try:
            if device.perfServer == 'localhost':
                configFile = os.path.join(os.environ['ZENHOME'], 'etc', "bbcappscollector.conf")
            else:
                configFile = os.path.join(os.environ['ZENHOME'], 'etc', "%s_bbcappscollector.conf" % device.perfServer)
            config = ConfigParser( configFile, log )
            # limit number the OIDs saved until we fix zodb performance
            self.maxApps = int( config.get( 'maxModeledApplicationsPerDevice', 100 ) )
            self.maxOIDsperApp = int( config.get( 'maxModeledKPIsPerApplication', 550 ) )
            self.maxOIDsperAppFlag = False
            self.hubusername = str( config.get( 'hubusername', 'admin' ) )
            self.hubpassword = str( config.get( 'hubpassword', 'zenoss' ) ) 
            self.hubhost = str ( config.get( 'hubhost', 'localhost' ) )
            self.xmlrpcport = 8081
            log.info("Using %s applications per device and %s oids per app, as specified in file %s" % (self.maxApps, self.maxOIDsperApp, configFile ) )
        except Exception, e:
            log.error( "Problem parsing config file: %s" % e)
            return None

        # built data struct from SNMP response
        app_hash = {}
        app_uniq = []
        appOids = []
        kpi_hash = {}
        oidsToSave = []
        brokenAppOids = []
        appOidre = re.compile(r"(?P<appOid>\.1\.3\.6\.1\.4\.1\.2333\.3\.2\.\d+)\.")
        validator = BBCApplicationSNMPFormatTest()

        logStep = 50
        logCount = 0

        deviceValidatorLog = []
        totalOidCounter = 0
        totalBBCOidCounter = 0
        brokenAppOidCounter = 0
        brokenKpiOidCounter = 0

        for oid, appRow in results.items():
 
            totalOidCounter += 1

            # avoid timing out by printing some stuff
            logCount = logCount +1
            if logCount >= logStep:
                logCount = 0
                log.info('.')

            # next line for compatibility with original code from SNMP version
            appRow = {'app': appRow}

            # ignore if  appRow['app']  is not a string
            if type(appRow['app']) != type(str()):
                continue

            # keep orig to use in reporting of wrong oids
            rawRow = appRow['app']

            pairs = appRow['app'].split('|')
            del appRow['app']

            # there are minimaly two keys
            if len(pairs) < 2:
                continue
            else:
                # to save later the appOId
                m = appOidre.match(oid)

                totalBBCOidCounter += 1
                subOid = oid.replace('.1.3.6.1.4.1.2333.3.2', '')
                appOidNumber = subOid.split( '.' )[ 1 ] # eg: '.44444.9.1'

                if not appRow.has_key('appOid'):
                    appRow['appOid'] = '.1.3.6.1.4.1.2333.3.2.' + appOidNumber

                for pair in pairs:
                    pair = pair.split('=',1)
                    if len(pair) == 2:
                        appRow[pair[0]] = pair[1]

                # application record
                if appRow.has_key('testName') or appRow.has_key('appMessage'):

                    validationErrorOutput = []

                    # App - validation test                                                    
                    validationErrorOutput = validator.validateAppRecord ( oid, subOid, rawRow, appRow )

                    # do we have format problems ?
                    if  len(validationErrorOutput) == 0:

                        # store app base oid to later build a testName oid set
                        if m is not None:
                            if str(m.group('appOid')) not in appOids:
                                appOids.append( str(m.group('appOid')) )

                        appRow['appName'] = prepId(appRow['appName']).replace(' ','_').replace(',', '_')
                        if appRow['appName'] not in app_uniq:
                                app_uniq.append(appRow['appName'])

                        if not app_hash.has_key(appRow['appName']):
                            # exit the loop if we reached max number of Apps
                            if len(app_hash) >= self.maxApps:
                                continue

                            app_hash[appRow['appName']] = { 'appName':appRow['appName'], 'appOid':appRow['appOid'] }
                            log.debug('adding app ' + appRow['appName'] )
                            log.debug('adding appOid %s in %s' % ( appRow['appOid'], oid ) )

                    else:

                        # log for broken application record
                        brokenAppOidCounter += 1
                        deviceValidatorLog += validationErrorOutput

                        # add app oid to broken oids
                        brokenAppOids.append(oid) 

                # handle kpi relations
                elif appRow.has_key('kpiName') or appRow.has_key('valueType'):

                    # KPI - validation test
                    validationErrorOutput = validator.validateKpiRecord ( oid, subOid, rawRow, appRow )

                    if  len(validationErrorOutput) == 0:
                            
                            appRow['kpiName'] = prepId(appRow['kpiName']).replace(' ','_').replace(',', '_')

                            # store app base oid to later build a testName oid set
                            if m is not None:
                                if str(m.group('appOid')) not in appOids:
                                    appOids.append( str(m.group('appOid')) )

                            appRow['appName'] = prepId(appRow['appName']).replace(' ','_').replace(',', '_')

                            if appRow['appName'] not in app_uniq:
                                app_uniq.append(appRow['appName'])

                            # exit the loop if we reached max number of Apps
                            if len(app_hash) < self.maxApps:
                                if not app_hash.has_key( appRow['appName'] ):
                                    log.debug('adding app ' + appRow['appName'] )
                                    log.debug('adding appOid %s in %s' % ( appRow['appOid'], oid ) )
                                app_hash[appRow['appName']] = { 'appName':appRow['appName'], 'appOid':appRow['appOid'] }
                            else:
                                continue 

                            if not kpi_hash.has_key( appRow['appName'] ):
                                kpi_hash[ appRow['appName'] ] = {}

                            # skip this row if we reached max number of OIDS per App
                            if len(kpi_hash[appRow['appName']]) >= self.maxOIDsperApp:
                                self.maxOIDsperAppFlag = True
                                continue

                            # skip & log if the same kpiname has already been used
                            if kpi_hash[appRow['appName']].has_key( appRow['kpiName'] ):
                                log.error('%s\'s KPIname %s already used by %s with oid %s' % (oid, appRow['kpiName'], appRow['appName'], kpi_hash[appRow['appName']][appRow['kpiName']]['snmpindex'] ))
                                continue

                            kpi_row = { 'snmpindex':subOid, 'valueType':'GAUGE' }

                            if appRow.has_key('valueType'):
                                kpi_row['valueType'] = appRow['valueType']

                            kpi_row['kpiName'] =  appRow['kpiName']

                            if appRow.has_key('url'):
                                kpi_row['url'] = appRow['url']

                            kpi_hash[appRow['appName']][appRow['kpiName']] = kpi_row 
                            oidsToSave.append( oid )

                    else:

                        # log for broken kpi record
                        brokenKpiOidCounter += 1
                        deviceValidatorLog += validationErrorOutput

       # log BBC Application format errors and statistic into actual modeler log
        if deviceValidatorLog:
                for error in deviceValidatorLog:
                     log.debug(error)


        # log BBC Application format errors and statistic into device modeler log
        # device dir
        validatorDeviceLogDir = os.path.join(os.environ['ZENHOME'], 'log', 'snmpModelerValidator', device.id)
        if not os.access(validatorDeviceLogDir, os.F_OK):
           os.makedirs(validatorDeviceLogDir, 0755)

        validatorDeviceLogFilePath = os.path.join(os.environ['ZENHOME'], 'log', 'snmpModelerValidator', device.id ,'modelerValidator.log')

        try:
            validatorDeviceLogFile = open(validatorDeviceLogFilePath, 'w')
        except:
            log.error("Failed to create device log validator file %s" % validatorDeviceLogFilePath)
            try:
                validatorDeviceLogFile.close()
            except:
                pass

        else:
            # log format problems
            if deviceValidatorLog:
                for error in deviceValidatorLog:
                     log.debug(error)
                     validatorDeviceLogFile.write(error + "\n")

            log.info( "totalOidCounter=%s testedOidCounter=%s brokenAppOidCounter=%s brokenKpiOidCounter=%s" % (totalOidCounter, totalBBCOidCounter, brokenAppOidCounter, brokenKpiOidCounter) )
 
            # log statistic
            validatorDeviceLogFile.write( "totalOidCounter=%s testedOidCounter=%s brokenAppOidCounter=%s brokenKpiOidCounter=%s\n" %
                   (totalOidCounter, totalBBCOidCounter, brokenAppOidCounter, brokenKpiOidCounter)
            )
            validatorDeviceLogFile.close() 

        # maxOIDsperApp event bussines
        if self.maxOIDsperAppFlag:
            self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( device.id, 'maxOIDsperApp limit' ),
                 severity   = Warning,
                 device     = device.id,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'maxOIDsperApp limit',
                 component  = 'BBCApplicationMap zenmodeler plugin',
                 message    = 'maxOIDsperApp limit %d was exceeded' % self.maxOIDsperApp,
                 summary    = 'maxOIDsperApp limit exceeded' ) )
            log.warning( 'maxOIDsperApp limit %d was exceeded' % self.maxOIDsperApp )
        else:
            self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( device.id, 'maxOIDsperApp limit' ),
                 severity   = 0,
                 device     = device.id,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'maxOIDsperApp limit',
                 component  = 'BBCApplicationMap zenmodeler plugin',
                 message    = 'maxOIDsperApp limit %d was not exceeded' % self.maxOIDsperApp,
                 summary    = 'maxOIDsperApp limit ok' ) )

         # maxApps event bussines
        if len( app_uniq ) > self.maxApps:
            self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( device.id, 'maxApps limit' ),
                 severity   = Warning,
                 device     = device.id,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'maxApps limit',
                 component  = 'BBCApplicationMap zenmodeler plugin',
                 message    = 'maxApps limit %d was exceeded %d ' % ( self.maxApps, len( app_uniq ) ),
                 summary    = 'maxApps limit exceeded' ) )
            log.warning( 'maxApps limit %d was exceeded' % self.maxApps )
        else:
            self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( device.id, 'maxApps limit' ),
                 severity   = 0,
                 device     = device.id,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'maxApps limit',
                 component  = 'BBCApplicationMap zenmodeler plugin',
                 message    = 'maxApps limit %d was not exceeded' % self.maxApps,
                 summary    = 'maxApps limit ok' ) )

        # build relationships 
        for appName, appRow in app_hash.items():    
            om = self.objectMap(appRow)
            om.id = appName

            if kpi_hash.has_key(appName):
                om.getAppKPISetup = MultiArgs(kpi_hash[appName])

            rm.append(om)

        # build 50 testName oids per application
        for app in appOids:
            for x in range(1,51):
                appOid = "%s.75025.%s" % (app,x) # 75025 if fibonacci seq f(25)
                newAppOid = "%s.75025.500.%s" % (app,x) # new oid space
                if appOid not in brokenAppOids:
                    oidsToSave.append(appOid)
                if newAppOid not in brokenAppOids:
                    if device.zBBCAdditionalAppOidSpace:
                        oidsToSave.append(newAppOid)

        oidsPath = os.path.join(os.environ['ZENHOME'], 'perf', 'Devices', device.id, 'applications', 'oids.1.3.6.1.4.1.2333.3.2.write')
        # check if you need to create path
        if not os.path.exists(os.path.join(os.environ['ZENHOME'], 'perf', 'Devices', device.id, 'applications')):
            try:
                os.makedirs(os.path.join(os.environ['ZENHOME'], 'perf', 'Devices', device.id, 'applications'))
            except Exception, e:
                log.error(e)

        try:
            pf = open(oidsPath, 'w')
        except: 
            log.error("failed to create oids storage file %s" % oidsPath)
            try:
                pf.close()
            except:
                pass
        else:
            # save 128 oids per line
            totalOids = len(oidsToSave)
            oidsPerLine = 128
            if device.zMaxOIDPerRequest > 0: oidsPerLine =  device.zMaxOIDPerRequest

            for nextOids in [oidsToSave[x:x+oidsPerLine] for x in range(0, totalOids, oidsPerLine)]:
                pf.write( " ".join( nextOids ) + "\n" )
            pf.close()

            if os.access(oidsPath, os.F_OK):
                for attempts in range(3):
                    try:
                        os.rename(oidsPath, os.path.join(os.environ['ZENHOME'], 'perf', 'Devices', device.id, 'applications', 'oids.1.3.6.1.4.1.2333.3.2.read'))
                        break
                    except:
                        time.sleep(1)

        return rm

    def sendEvent( self, event ):
       proxy = xmlrpclib.ServerProxy(
          'http://%s:%s@%s:%d/' % ( self.hubusername, self.hubpassword, self.hubhost, self.xmlrpcport ),
          #verbose=1,
          encoding='iso-8859-1')
       proxy.sendEvent( event )
