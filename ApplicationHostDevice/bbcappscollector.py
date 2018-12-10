__doc__ = """

   This is the daemon version of the BBCAppCollector

"""
import pdb
import logging
import Globals
import time, re, os, copy
from datetime import datetime
from twisted.internet import reactor, defer, utils
from twisted.internet.task import LoopingCall
from twisted.python import failure

from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSSH import BBCApplicationSSH
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSNMP import BBCApplicationSNMP
import ZenPacks.BBC.ApplicationHostDevice.lib.BBCCustomErrors
from ZenPacks.BBC.ApplicationHostDevice.lib.utils import * 
# next is needed to make jelly stuff work (pass deviceConfig objects between ZenHub & Collector)
from ZenPacks.BBC.ApplicationHostDevice.services.BBCConfig import deviceProperties

from Products.ZenUtils.DaemonStats import DaemonStats
# use NJobs to write the code to process N devices at a time
from Products.ZenUtils.NJobs import NJobs
from Products.ZenRRD.RRDDaemon import RRDDaemon
from Products.ZenRRD.RRDUtil import RRDUtil
# next line loads the different severities known to zenoss 
# plus a few default classes
from Products.ZenEvents.ZenEventClasses import *
import transaction
import traceback

class bbcappscollector(RRDDaemon):
    '''
      the BBC Collector Daemon
    '''
    name = 'BBCApplicationCollector'
     
    initialServices = RRDDaemon.initialServices + [
        'ZenPacks.BBC.ApplicationHostDevice.services.BBCConfig'
    ]

    def __init__(self):
        RRDDaemon.__init__(self, 'bbcappscollector')
        self.rrdStats                           = DaemonStats()
        self.devices                            = {}
        self.running                            = False
        self.configCycleInterval                = 60 * 30 
        self.HEARTBEAT_CYCLE                    = 60
        self.watchdogCycleInterval              = 60
        self.bbcappscollectorCycleInterval      = self.options.bbcappscollectorCycleInterval
        self.collectionThreshold                = self.bbcappscollectorCycleInterval + 60 
        self.startTime                          = None
        self.zenProcessParallelJobs             = self.options.zenProcessParallelJobs
        self.baseOid                            = self.options.oid
        self.verbose                            = self.options.verbose
        self.oidValidatorSeverity               = self.options.oidValidatorSeverity # not implemented, creating too much event noise
        self.oidTtlExpirySeverity               = self.options.oidTtlExpirySeverity 
        self.log                                = logging.getLogger('zen.bbcappscollector') 
        self.knownEventClasses                  = [] # to cache in memory event classes that ZenHub have validated
        self.postponeFlag                       = False
        # device statuses used for collection watchdog report
        self.deviceStatus                       = {
            'waiting'   : 'waiting',    # waiting for collection
            'finished'  : 'finished',   # collection finished properly
            'skipped'   : 'skipped'     # collection skipped for some problem reason (e.g. timeout )
        }
        self.log.info('bbcappscollector started')

    def updateHeartBeat( self ):
        self.heartbeat()
        self.log.debug("Daemon heart beat was sent")

    def collectionWatchdog( self ):
        actualCollTime = time.time() - self.startTime

        if actualCollTime > self.collectionThreshold:
            self.log.error( 'Devices\' collection exceeded: current value %s, threshold %s' % ( actualCollTime, self.collectionThreshold ) )
            self.log.info( 'NJOB - collection status: running %s queue_length %s  results_length %s ' % self.jobs.status() )

            allDevices = [ dev.id for dev in self.devices.values() ]
            stillToProcess = [ dev.id for dev in self.jobs.workQueue ]

            devicesStatus = {}
            for result in self.jobs.results:
                status = result.keys()[0]
                if devicesStatus.has_key( status ):
                    devicesStatus[ status ].append( result[ status ] )
                else:
                    devicesStatus[ status ] = [ result[ status ] ]

            doneDevices = devicesStatus[ 'finished' ] + devicesStatus[ 'skipped' ]
            runningDevices = list( set( allDevices ).difference( doneDevices ).difference( stillToProcess ) )

            self.log.info( '********** NJobs stats ***************' )
            self.log.info( 'NJobs - %s processed devices %s' % ( len( doneDevices ), doneDevices ) )
            self.log.info( '*************************************' )
            self.log.info( 'NJobs - %s devices to process %s' % ( len( stillToProcess ), stillToProcess ) )
            self.log.info( '*************************************' )
            self.log.info( 'NJobs - %s running devices %s' % ( len( runningDevices ), runningDevices ) )
            self.log.info( '*************************************' )

            #for status in self.deviceStatus.keys():
            #    self.log.info( '%s status devices %s' % ( status, finishedDevices[ status ] ) )

            evid = self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( self.options.monitor, 'bbcappscollector cycle time' ),
                 severity   = Error,
                 device     = self.options.monitor,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'bbcappscollector cycle time',
                 component  = 'collection daemon',
                 message    = 'timethreshold of bbcappscollector cycle time exceeded: current value %d, threshold %d' % ( actualCollTime, self.collectionThreshold ),
                 summary    = 'bbcappscollector cycle timethreshold' ) )

        # everything OK - clear event
        else:
             evid = self.sendEvent( dict (
                 dedupid    = "%s|%s" % ( self.options.monitor, 'bbcappscollector cycle time' ),
                 severity   = Clear,
                 device     = self.options.monitor,
                 eventClass = '/BBCApplication/Zenoss',
                 eventKey   = 'bbcappscollector cycle time',
                 component  = 'collection daemon',
                 message    = 'timethreshold of bbcappscollector cycle time not exceeded',
                 summary    = 'bbcappscollector cycle timethreshold' ) )

    def connected(self):

        def inner( imp ):
            self.postponeFlag = True

            if self.options.cycle:

                # build projects cache
                loadProjectsLoop = LoopingCall( self.fetchConfig )
                loadProjectsLoop.start( self.configCycleInterval )

                # process all valid projects
                processProjectsLoop = LoopingCall( self.collectBBCKPIs )
                processProjectsLoop.start( self.bbcappscollectorCycleInterval )

                # heart beat cycle loop
                heartBeatLoop = LoopingCall( self.updateHeartBeat )
                heartBeatLoop.start( self.HEARTBEAT_CYCLE )

                # report a collection problem if any
                reportLoop =  LoopingCall( self.collectionWatchdog )
                reportLoop.start( self.watchdogCycleInterval )

            else:

                self.log.info( 'Running only once ...' )
                d = self.collectBBCKPIs()
                d.addErrback( self.handleError )
                d.addCallback( self.stop )

        def firstConfigFetch( imp ):
            self.postponeFlag = False
            d = self.fetchConfig()
            d.addErrback( self.handleError )
            d.addCallback( inner )

        self.log.info("Connected to ZenHub")
        self.log.info("configCycleInterval %s" % self.configCycleInterval)
        self.log.info("bbcappscollectorCycleInterval %s" % self.bbcappscollectorCycleInterval)
        self.log.info("zenProcessParallelJobs %s" % self.zenProcessParallelJobs)

        d = self.fetchPreConfig()
        d.addErrback( self.handleError )
        d.addCallback( firstConfigFetch )

    def fetchPreConfig(self):
        """ This should be called only once when the daemon starts """

        # 3) finish
        def finish( imp ):
            self.log.info('Done initial config fetching from zenhub.')
            self.rrdStats.config(self.options.monitor, self.name, imp, self.createRRDCreateCommand)
            return defer.succeed( [] )
 
        # 2.1) Getting collector thresholds
        def getCollectorThresholds( imp ):
            self.createRRDCreateCommand = imp
            self.rrd = RRDUtil(self.createRRDCreateCommand, self.bbcappscollectorCycleInterval)
            self.log.info("Getting collector thresholds...")
            d = self.model().callRemote('getCollectorThresholds')
            d.addErrback( self.handleError )
            d.addCallback( finish )
            return d

        # 2) load default rrd command
        def getDefaultRRDCreateCommand( imp ):
            self.setPropertyItems( imp )	
            self.log.info("Getting default RRDCreateCommand...")
            d = self.model().callRemote('getDefaultRRDCreateCommand')
            d.addErrback( self.handleError )
            d.addCallback(  getCollectorThresholds )
            return d

        # 1) copy the collector properties
        # provides values for pingCycleInterval and configCycleInterval
        def propertyItems():
            self.log.info("Getting propertyItems...")
            d = self.model().callRemote('propertyItems')
            d.addErrback( self.handleError )
            d.addCallback( getDefaultRRDCreateCommand )
            return d
 
        return propertyItems()

    def fetchConfig(self):
        '''
           Get configuration values from ZenHub
        '''

        # 2) done
        def finish( imp ):
            devices = imp
            if not isinstance(devices, list) or len(devices) == 0:
                self.log.info("No devices config returned by ZenHub: %r" % devices)
            else:
                for devConfig in devices:
                    self.remote_updateDevice( devConfig )
            self.log.info('Done fetching config from zenhub.')
            self.log.debug('Found devices: %s' % self.devices.keys() )
            for dev in self.devices.keys():
                self.log.debug('Thresholds data for device %s is %s' %(dev, self.devices[dev].thresholds))
            self.sendEvents( self.rrdStats.gauge( 'configTime', self.configCycleInterval, time.time() - startCofigTime ) )
            return defer.succeed( [] ) 

        # 1) get the devices for the current collector
        def getDevices(): 
            self.log.info("Getting devices configs...")
            d = self.model().callRemote('getDevices', devices)
            d.addErrback( self.handleError )
            d.addCallback( finish )
            return d 

        # hack - to avoid an immediate second running
        if self.postponeFlag:
            return defer.succeed( [] )

        self.log.info( 'Start fetching devices configs from zenhub' )
        startCofigTime = time.time()

        # bbcappscollector -v 10 -d someDevice
        devices = []
        if self.options.device:
            devices = [ self.options.device ]

        return getDevices()

    def remote_deleteDevice(self, doomed):
        '''
           method called by ZenHub to update the collector with changes
        '''
        try:
            del self.devices[doomed]
        except KeyError:
            pass

    def remote_updateDevice(self, cfg):
        '''
           method called by ZenHub to update the collector with changes
        '''   
        cfg.modelledOids = self.oidsToCollect(cfg)
        self.devices[ cfg.id ] = cfg

    def oidsToCollect(self, device):
        '''
           return the list of oids currently modelled for the device
        '''
        deviceOids = []
        oidsPath   = os.path.join(os.environ['ZENHOME'],
                                  'perf',
                                  'Devices',
                                  device.id,
                                  'applications',
                                  'oids.1.3.6.1.4.1.2333.3.2.read')
        pf = None
        try:
            pf = open(oidsPath , 'r' )
            deviceOids = [oidsLine.rstrip() for oidsLine in pf]
            pf.close()
        except Exception, e:
            self.log.info('Problem to open oid file %s' % e )
            if isinstance(pf, file):
                pf.close()
            pass

        return deviceOids

    def collectBBCKPIs(self, results=None):
        '''
           Loop that drives collection of data for all devices received from zenhub
        '''

        def finishCollection( results ):
            '''
               Callback to complete the round of collection of devices data
            '''
            runTime = time.time() - self.startTime
            updatedRRDs = self.rrd.endCycle()
            self.running = False
            self.log.info('sending daemon events if any ...')
            self.sendEvents(
                    self.rrdStats.gauge( 'cycleTime', self.bbcappscollectorCycleInterval, runTime ) +
                    self.rrdStats.counter( 'dataPoints', self.bbcappscollectorCycleInterval, self.rrd.dataPoints ) +
                    self.rrdStats.gauge( 'cyclePoints', self.bbcappscollectorCycleInterval, updatedRRDs )
                    )
            self.log.info( '******** Cycle completed ********' )
            self.log.info( "Updated %s RRDs" % updatedRRDs )
            self.log.info( "Queried %d devices" % len( self.devices ) )
            self.log.info( 'Cycle lasted %.2f seconds' % runTime )
            self.log.info( '*********************************' )
            self.postponeFlag = False

        def inner():
            self.running = True
            self.startTime = time.time()
            self.log.info('Starting collecting perf data')
            self.log.debug('For devices: %s' %  str(self.devices.keys()))
            # processes in parallel (zenProcessParallelJobs) devices ( one device per job )
            self.jobs = NJobs(self.zenProcessParallelJobs,
                         self.collectDevice,
                         self.devices.values())

            d = self.jobs.start()
            # call this olny if all devices were collected
            d.addErrback( self.handleError )
            d.addCallback(finishCollection)
            return d

        if self.running:
            self.log.error('previous cycle still running')
            return

        return inner()

    def collectDevice(self, device):
        '''
           handle the collection of data for a particular device "d"
        '''

        def processDeviceOids(data):
            collection.stats['saveRRDTryCounter'] = 0
            collection.stats['saveRRDSuccessfulValueCounter'] = 0
            collection.stats['saveRRDThresholsSuccessfulCounter'] = 0
            collection.stats['saveRRDFailedCounter'] = 0
            # main loop for processDeviceOids
            for oid, value in data.items():
                processOid( ( oid, value ) )

            collection.stats[ 'totalTime' ] = time.time() - collection.stats[ 'totalTime' ]
            # save collection stats into RRDs
            saveCollectionStatsRRDs()
            return { self.deviceStatus[ 'finished' ] : device.id }

        def saveCollectionStatsRRDs():
            perfRoot  =  'Devices/' + device.id + '/'

            self.log.debug( '******** Device %s completed ********' % device.id )
            self.log.debug( 'Statistics:' )

            for key, value in collection.stats.items():
                self.log.debug( '%s : %s' % ( key, value ) )
                try:
                    deltaValue = self.rrd.save ( perfRoot + 'applicationCollector_' + key, value, 'GAUGE' )

                    if self.verbose:
                        self.log.debug( "After saving to RRD - original value:%s valueType:%s for kpiName:%s deltaValue:%s"
                            % ( value, 'GAUGE', key, deltaValue ) )

                except Exception, e:
                    summary= "Unable to save data for %s in RRD %s" % ( key, perfRoot + 'applicationCollector_' + key )
                    self.log.critical( summary )

                    evtmessage= "Data was value= %s, type=GAUGE, RRD create command: %s" % ( value, self.createRRDCreateCommand )

                    self.log.critical( evtmessage )
                    self.log.exception( e )

                    trace_info= traceback.format_exc()

                    evid = self.sendEvent( dict (
                         dedupid    = "%s|%s" % ( self.options.monitor, 'RRD write failure' ),
                         severity   = Critical,
                         device     = self.options.monitor,
                         eventClass = Status_Perf,
                         component  = "RRD",
                         statistic  = 'applicationCollector_' + key,
                         path       = perfRoot,
                         message    = evtmessage,
                         traceback  = trace_info,
                         summary    = summary ) )
                    pass
            
            self.log.debug( '*********************************' )
            return
 
        def processOid( oidData ):
            oid = None
            try:
               oid = OidParser( self.baseOid, oidData, self.log )
            except Exception, e:
               if self.verbose: self.log.info('skipping %s because %s' % (oidData, e))
               return
            
            if device.thresholds.has_key(oid.appName):
                self.log.debug("oid applicationname is %s" %oid.appName)
                for record, recval in device.thresholds[oid.appName].items():
                    if oid.isAppMessage() and record == oid.testName:
                        self.log.debug("oid testname is %s" %oid.testName)
                        self.log.debug("Replacing test record %s value from %s to %s and its url from %s to %s" %(oid.testName, oid.value, device.thresholds[oid.appName][record]['value'], oid.url, 
                                                                                                                  device.thresholds[oid.appName][record]['runbookurl']))
                        if device.thresholds[oid.appName][record]['value'] is not None:
                            oid.value = device.thresholds[oid.appName][record]['value']
                        else:
                            oid.value = 'U'
                        oid.url   = device.thresholds[oid.appName][record]['runbookurl']
                    if oid.isKPI() and record == oid.kpiName:
                        self.log.debug("oid kpiname is %s" %oid.kpiName)
                        for thresh, val in device.thresholds[oid.appName][record].items():
                            if thresh == "runbookurl":
                                self.log.debug("Replacing runbook url from %s to %s for kpi %s" %(oid.url, val, oid.kpiName))
                                oid.url   = val
                                continue
                            if oid.hasField(thresh):
                                self.log.debug("Replacing threshold %s value from %s to %s for kpi %s" %(thresh, oid.data[oid.fieldKey(thresh)], val, oid.kpiName))
                            else:
                                self.log.debug("Creating new threshold %s with value %s for kpi %s" %(thresh, val, oid.kpiName))
                            if val is not None:
                                oid.data[oid.fieldKey(thresh)] = val
                            else:
                                oid.data[oid.fieldKey(thresh)] = 'U'
                        self.log.debug("processed oid is %s" %oid.__dict__)   

            # overall oid counter
            collection.stats[ 'oidsCounter' ] += 1 

            if oid.isAppMessage():

                # application oid counter
                collection.stats[ 'foundAppOidCounter' ] += 1

                # create an approptiate event if there was not validation problem
                if  len(oid.validatorErrors) == 0:

                    # TTL - SNMP data expiration time event
                    if oid.hasField('ttl') and time.time() > float(oid.ttl):
                        # enable ttlSeverity to allow cronjobs ttl setting alerts
                        severity = self.oidTtlExpirySeverity
                        applicationName = 'Zenoss' # ttl expiry messages are reported under /BBCApplication/Zenoss

                        if oid.hasField('ttlSeverity'):
                            try:
                                oid.ttlSeverity =  int( oid.ttlSeverity )
                                if oid.ttlSeverity in range(5):
                                  severity = oid.ttlSeverity
                                  applicationName = oid.appName

                            except Exception, e:
                               if self.verbose: self.log.error("Failed to process ttlSeverity field for record: %s %s" % (oid.data, e))
                        
                        createEvent( oid.testName,                              # component
                            severity,                                                    # severity
                            "%s stale appMessage record data for %s" % ( oid.appName, oid.testName), # summary
                            "Application:%s Test:%s has a ttl of %s which indicates that it is expired (current time %s)<br/>OID: %s"
                                % ( oid.appName, oid.testName, 
                                   datetime.fromtimestamp(float( oid.ttl )).ctime(), 
                                   datetime.fromtimestamp(time.time()).ctime(), oid.id ),# message
                            applicationName,                                             # application
                            None,                                                        # event sub class
                            oid.url,                                                     # url
                            "%s:%s" % (oid.subOid, oid.appName))                         # eventKey
                        
                    else:
                        # send normal event
                        try:
                            if oid.value != 'U':
                                createEvent( oid.testName,                                 # component
                                             oid.value,                                    # severity
                                             oid.appMessage,                               # summary
                                             oid.appMessage + "<br/>OID: " + oid.id,       # message
                                             oid.appName,                                  # application
                                             oid.eventSubClass,                            # event sub class
                                             oid.url,                                      # url 
                                             "%s:%s" % (oid.subOid, oid.appName)           # eventKey
                                )
                        except Exception, e:
                            if self.verbose: self.log.error("Failed to create event for %s test name %s: %s" % (oid.appName, oid.testName, e))
                else:
                    # log for broken application record
                    collection.stats[ 'brokenAppOidCounter' ] += 1

                    # appMessage invalid
                    for error in oid.validatorErrors:
                        if self.verbose: self.log.error(error)                     
 

            elif oid.isKPI():

                # log for valid KPI record
                collection.stats[ 'collectedKpiOidCounter'] += 1

                # this is a KPI
                if  len(oid.validatorErrors) == 0:
                    # kpi is fine leti's process it
                    oid.valueType = oid.valueType.upper()
 
                    # handle ttlSeverity?
                    if oid.hasField('ttlSeverity'):
                        oid.deleteField('ttlSeverity')

                    # convert numbers to floats
                    for key in ['minThreshD','maxThreshD','minThreshI','maxThreshI','minThreshW',
                                'maxThreshW','minThreshE','maxThreshE' ,'minThreshC', 'maxThreshC', 'ttl']:
                            oid.toFloat(key) 

                    # prepare value
                    if oid.value.upper() == 'UNKNOWN':
                        oid.value = 'U'
                    elif oid.hasField('ttl') and time.time() > oid.ttl:
                        oid.value = 'U'
                        createEvent(oid.kpiName,                       # component
                                    self.oidTtlExpirySeverity,                                  # severity
                                    "%s stale KPI record data: %s" % (oid.appName, oid.kpiName),                                     # summary
                            "Application:%s KPI:%s has a ttl of %s which indicates that it is expired (current time %s)<br/>OID: %s"
                                % (oid.appName, oid.kpiName, 
                                   datetime.fromtimestamp(oid.ttl).ctime(),
                                   datetime.fromtimestamp(time.time()).ctime(), oid.id),    # message
                            'Zenoss',                                                    # application
                            None,                                                        # event sub class
                            oid.url,                                                 # url
                            "%s:%s:%s" % (oid.subOid, oid.appName, oid.kpiName)      # eventKey
                        )
                    else:
                        try:
                            oid.value = float( oid.value )
                        except Exception, e:
                            if self.verbose: self.log.error("Invalid value defined in %s: %s, stored as UNKNOWN" % (oid.kpiName, e))
                            # make it UNKNOWN 
                            oid.value = 'U'
                            pass
                    
                    if oid.value != 'U' and oid.valueType in ['DERIVE', 'COUNTER', 'ABSOLUTE']:
                        # this is rubish, we can not call long on str
                        # so we still depend on doing first float above
                        # then long
                        oid.value = long( oid.value )
                   
                    # store values & thresholds in RRD files 
                    saveOidRRD(oid)

                    # check tresholds and send events
                    checkThresholds(oid)
  
                else:
                    # log for broken KPI record
                    collection.stats[ 'brokenKpiOidCounter' ] += 1

                    # log for broken KPI record
                    for error in oid.validatorErrors:
                        if self.verbose: self.log.error(error) 

        def createEvent(component, evtseverity, summary, evtmessage, appName, subPath="", url=None, eventKey=""):

            if int(device.productionState) <= 300:
               return
            
            eventClassName = '/BBCApplication/%s' %  appName.lstrip('/')
            if subPath:
                eventClassName = '%s/%s' % (eventClassName, subPath.lstrip('/'))
            
            def checkClassError(error):
                self.log.error('failed to check/create event class: %s' % error )

            def queueEvent(eventClassName, component, evtseverity, summary, evtmessage, appName, url, eventKey):
                # cache validated event classes
                if eventClassName is None:
                    raise 

                if eventClassName not in self.knownEventClasses:
                    self.knownEventClasses.append(eventClassName)

                try:
                   # app or kpi records without defined url and severity higher then 0 are always going to have debug severity
                   if url:
                      evtmessage += "<br/> <a href='%s'>Run Book</a>" % url
                   else: 
                      evtmessage += "<br/> Run Book N/A"

                   if not url and evtseverity > 0 and not appName == 'Zenoss':
                       evtseverity = Debug
                       summary = 'URL link to runbook was not provided.' + summary

                   # ensure severity is integer
                   evtseverity = int(evtseverity)

                   if evtseverity in range(6):
                      self.sendEvent(dict(
                         device     = device.id,
                         eventClass = eventClassName,
                         severity   = evtseverity,
                         component  = component,
                         summary    = summary,
                         message    = evtmessage,
                         eventKey   = eventKey
                      ))
                   else:
                      # wrong severity!!!!
                      self.sendEvent(dict(
                          device      = device.id,
                          eventClass  = eventClassName,
                          severity    = Error,
                          component   = component,
                          summary     = "Attempted to raise an event with invalid severity value: %s" % severity,
                          message     = "Attempted to raise an event with invalid severity value: %s Original message: %s" % (evtseverity, evtmessage),
                          eventKey    = eventKey
                      ))

                except KeyError:
                   self.log.error("Creating event -> EventClassName:%s Severity:%s Component:%s Summary:%s Message:%s EventKey:%s" %\
                      (eventClassName, evtseverity, component, summary, evtmessage, eventKey) )
                   pass

                except Exception, e:
                   self.log.error('Create event failed: %s' % e)
                   pass

            if eventClassName in self.knownEventClasses:
                queueEvent(eventClassName, component, evtseverity, summary, evtmessage, appName, url, eventKey)
            else:
                # call ZenHub first to create the event class if needed
                d = self.model().callRemote('checkEventClass', eventClassName)
                # the return from remote_checkEventClass is passed to the callback as the first arg
                # so on next line we omit eventClassName
                d.addErrback(checkClassError)
                d.addCallback(queueEvent, component, evtseverity, summary, evtmessage, appName, url, eventKey)

        def saveOidRRD(oid):
            collection.stats['saveRRDTryCounter'] += 1
            origValue = oid.value
            perfRoot  =  'Devices/' + device.id + '/applications/'\
                        +  oid.appName  + '/ApplicationToKPI/'\
                        +  oid.kpiName  + '/value_'

            try:
                 # rewrite value for COUNTER
                 if oid.valueType == 'COUNTER' and oid.value != 'U':
                     oid.valueType = 'DERIVE'    
                     # y(actual_time) - y(actula_time - cycleTime*2) for COUNTER type
                     oid.value = self.rrd.save(perfRoot + 'value', oid.value, oid.valueType, None, None, 0)

                 elif oid.valueType == 'DERIVE' and oid.value != 'U':
                     # y(actual_time) - y(actula_time - cycleTime*2) for DERIVE type
                     oid.value = self.rrd.save(perfRoot + 'value', oid.value, oid.valueType)

                 else:
                     # GAUGE and ABSOLUTE and ''
                     self.rrd.save (perfRoot + 'value', oid.value, oid.valueType)

                 collection.stats['saveRRDSuccessfulValueCounter'] += 1
                 if self.verbose:
                    self.log.debug("After saving to RRD - original value:%s valueType:%s for kpiName:%s deltaValue:%s"
                        % (origValue, oid.valueType, oid.kpiName, oid.value))

                 # save thresholds to rrd files
                 for field in ['minThreshD','maxThreshD','minThreshI','maxThreshI',
                     'minThreshW','maxThreshW','minThreshE','maxThreshE',
                     'minThreshC', 'maxThreshC']:
                     if oid.hasField(field):
                         # store rdd value
                         self.rrd.save(perfRoot + field, oid.data[ oid.fieldKey( field ) ], 'GAUGE')
                         collection.stats['saveRRDThresholsSuccessfulCounter'] += 1

            except Exception, e:
                collection.stats['saveRRDFailedCounter'] += 1
                summary= "Unable to save data for OID %s in RRD %s" % \
                      ( oid.id, perfRoot + 'value' )
                self.log.critical( summary )

                evtmessage= "Data was value= %s, type=%s, RRD create command: %s" % \
                   ( oid.value,
                     oid.valueType,
                     self.createRRDCreateCommand )

                self.log.critical( evtmessage )
                self.log.exception( e )

                trace_info= traceback.format_exc()

                evid = self.sendEvent(dict(
                     dedupid    = "%s|%s" % (self.options.monitor, 'RRD write failure'),
                     severity   = Critical,
                     device     = self.options.monitor,
                     eventClass = Status_Perf,
                     component  = "RRD",
                     oid        = oid.id,
                     path       = perfRoot,
                     message    = evtmessage,
                     traceback  = trace_info,
                     summary    = summary))
                return
            return oid.value
    
         
        def checkThresholds(oid):
            ''' 
               compares the value vs threholds present in an kpi and raises events if needed
            '''
            severity = 0
            eventMessage = "Current value: %s<br/>Current Thresholds:" % oid.value 

            # threshold presence flag
            hasThreshold = False

            if oid.hasField('value') and oid.value != 'U':
                for threshold, setSeverity in (('minThreshC',Critical), ('maxThreshC',Critical),
                                               ('minThreshE',Error),    ('maxThreshE',Error),
                                               ('minThreshW',Warning),  ('maxThreshW',Warning),
                                               ('minThreshI',Info),     ('maxThreshI',Info),
                                               ('minThreshD',Debug),    ('maxThreshD',Debug)):

                    if oid.hasField(threshold):
                        hasThreshold = True
                        # add threshold to default clear event message
                        thresholdValue = oid.data[ oid.fieldKey(threshold) ]
                        eventMessage = eventMessage + "<br/>&nbsp;&nbsp;%s: %s" % (threshold, thresholdValue )
                        if threshold.find('min') > -1:
                            if oid.value < thresholdValue:
                                severity = setSeverity
                                eventMessage = "Value: %s (%s)<br/>%s: %s" % ( oid.value, oid.valueType, threshold, thresholdValue )
                                break
                        else:
                            if oid.value > thresholdValue:
                                severity = setSeverity
                                eventMessage = "Value: %s (%s)<br/>%s: %s" % ( oid.value, oid.valueType , threshold, thresholdValue )
                                break
                   
                if hasThreshold and thresholdValue != 'U':
                    # will send a clear event by default
                    createEvent(oid.kpiName,                                              # component
                                severity,                                                           # severity
                                'Application: %s KPI: %s %s' % (oid.appName,
                                                                oid.kpiName, 
                                                                re.sub(r'<br/>', ' ',eventMessage)),# summary
                                '%s<br/>OID:  %s' % (eventMessage, oid.id),                  # message
                                oid.appName,                                                 # application
                                oid.eventSubClass,                                           # event sub class
                                oid.url,                                                     # url
                                "%s:%s:%s" % (oid.subOid, oid.appName, oid.kpiName)       # eventKey
                       )
                       
        # trigger the collection itself
        collection_order = [ BBCApplicationSSH, BBCApplicationSNMP ]
        collection = None
        data = defer.succeed( { self.deviceStatus[ 'waiting' ] : device.id } )
        
        if len( device.modelledOids ) == 0:
            self.log.info('skipping %s: no modelled oids yet' % device.id )
            data = defer.succeed( { self.deviceStatus[ 'skipped' ] : device.id } )
        else:
            collectFlag = False
            for key in collection_order:
                collection = key ( device, self.log )
                if collection.getRunCondition():
                    collectFlag = True
                    data = collection.getData( deferred = True )
                    data.addErrback( collection.handleError )
                    data.addCallback( processDeviceOids )
                    break

            if collectFlag is False:
                self.log.info('skipping %s device, none collection method was defined (SSH,SNMP ... etc)' % device.id )
                data = defer.succeed( { self.deviceStatus[ 'skipped' ] : device.id } )

        return data

    def is_number(self, val):
        try:
            float(val)
            return True
        except ValueError:
            return False

    def handleError( self, err ):
        self.log.error( 'Collector daemon error %s' % err )

    def buildOptions(self):
        RRDDaemon.buildOptions(self)
        self.parser.add_option('--bbcappscollectorCycleInterval',
                               dest    = 'bbcappscollectorCycleInterval',
                               default = 5*60,
                               type    = 'int',
                               help    = "Number of seconds between data collection attempts")
        self.parser.add_option('--parallelJobs',
                               dest    = 'zenProcessParallelJobs',
                               default = 10,
                               type    = 'int',
                               help    = "Number parallel jobs to run")
        self.parser.add_option('--oid',
                               dest    = 'oid',
                               default = '.1.3.6.1.4.1.2333.3.2',
                               type    = 'string',
                               help    = "base oid")
        self.parser.add_option('--verbose',
                               dest    = 'verbose',
                               default = None,
                               type    = 'string',
                               help    = "base oid")
        self.parser.add_option('--maxModeledApplicationsPerDevice',
                               dest    = 'maxModeledApplicationsPerDevice',
                               default = 100,
                               type    = 'int',
                               help    = "Maximum number of applications per device ( only used by modeler code)")
        self.parser.add_option('--maxModeledKPIsPerApplication',
                               dest    = 'maxModeledKPIsPerApplication',
                               default = 550,
                               type    = 'int',
                               help    = "Maximum number of KPIs per application ( only used by modeler code)")
        self.parser.add_option('--oidValidatorSeverity',
                               dest    = 'oidValidatorSeverity',
                               default = 1,
                               type    = 'int',
                               help    = "Validator problems are going to be logged under this severity")
        self.parser.add_option('--oidTtlExpirySeverity',
                               dest    = 'oidTtlExpirySeverity',
                               default = 1,
                               type    = 'int',
                               help    = "TtlExpiry problems are going to be logged under this severity")
        self.parser.add_option('--thresholdsConfigDir',
                               dest    = 'thresholdsConfigDir',
                               default = '/opt/zenoss-dynamic-configs',
                               type    = 'string',
                               help    = "Thresholds output dir used by remote services(zenhub)")

if __name__ == '__main__':
   BBCAppCollector = bbcappscollector()
   BBCAppCollector.run()
