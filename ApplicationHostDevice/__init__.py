# needed for defining portlets
from Products.ZenModel.ZenossSecurity import ZEN_COMMON, ZEN_MANAGE_DMD
from Products.ZenUtils.Utils import zenPath

from Products.ZenEvents.EventManagerBase import EventManagerBase
from Products.ZenEvents.MySqlSendEvent import MySqlSendEventMixin 
import types
# and to handle ajax/json
import simplejson as json
import Globals
import os
import re
import sys
import shutil
from Products.AdvancedQuery import MatchRegexp, Or, Eq, In
from Products.ZenEvents.browser.EventPillsAndSummaries import \
                                   ObjectsEventSummary,    \
                                   getEventPillME
import time

skinsDir = os.path.join(os.path.dirname(__file__), 'skins')
from Products.CMFCore.DirectoryView import registerDirectory
if os.path.isdir(skinsDir):
    registerDirectory(skinsDir, globals())
    # manua
    registerDirectory("skins", globals())


###
#  Classes to build a portlet for the dashboard
###
from Products.ZenModel.ZenPack import ZenPackBase

class ZenPack(ZenPackBase):
    """
    BBC.ApplicationHost ZenPack class
    """
    packZProperties = [
        ('zSnmpProxy', '', 'string'),
        ('zSnmpProxyContextName', '', 'string'),
        ('zBBCUseSSH', False, 'boolean'),
        ('zBBCAdditionalAppOidSpace', False, 'boolean')
    ]

    daemonSource = os.path.join( os.path.dirname( __file__ ), 'daemons', 'bbcappscollector' )
    daemonLink = os.path.join( os.environ['ZENHOME'], 'bin', 'bbcappscollector' )

    def install(self, app):
        """
        Initial installation of the ZenPack
        """
        try:
            # zSSHTimeout zproperty is added as part of this zenpack
            if app.dmd.Devices.getProperty('zSSHTimeout') is None:
                app.dmd.Devices.manage_addProperty('zSSHTimeout', 10, 'int')
            app.dmd.Devices.createOrganizer('/BBC')
            app.dmd.Events.createOrganizer('/BBCApplication')
            app.dmd.Events.createOrganizer('/BBCApplication/Zenoss')
            app.dmd.Events.createOrganizer('/Status/SSH')
        except:
            pass

        ZenPackBase.install(self, app)
        self._registerBBCAppPortlet(app)
        self._patchCollectionEdit()
        #self._registerDaemon()
        self._updateZenossDaemonsPerfStats()

    def upgrade(self, app):
        """
        Upgrading the ZenPack procedures
        """
        ZenPackBase.upgrade(self, app)
        self._patchCollectionEdit()
        self._registerBBCAppPortlet(app)
        #self._registerDaemon()
        self._updateZenossDaemonsPerfStats()

    def remove(self, app, leaveObjects=False ):
        """
        Remove the ZenPack from Zenoss
        """
        # NB: As of Zenoss 2.2, this function now takes three arguments.
        ZenPackBase.remove(self, app, leaveObjects)
        zpm = app.zport.ZenPortletManager
        zpm.unregister_portlet('BBCAppPortlet')
        zpm.unregister_portlet('BBCDevicesPortlet')
        zpm.unregister_portlet('ZDaemonsPorlet')
        #self._unregisterDaemon()

        # restore original template for editCollection
        template = os.path.join(os.environ['ZENHOME'], 'Products', "ZenModel", "skins", "zenmodel", "editCollection.pt") 
        backup   = os.path.join(os.environ['ZENHOME'], 'Products', "ZenModel", "skins", "zenmodel", "editCollection.backup")
        try:
            if os.access(template, os.F_OK) and os.access(backup, os.F_OK):
                for attempts in range(3):
                    try:
                        os.rename(backup, template)
                        break
                    except:
                        time.sleep(1)
        except Exception, e:
            sys.stdout.write("Failed to restore editCollection.pt from backup: %s" % e)
            pass

    def _updateZenossDaemonsPerfStats( self ):
        backupDaemonsPerf = os.path.join( os.environ['ZENHOME'], 'Products', 'ZenModel', 'data' , 'monitorTemplates.xml.backup' )
        bbcDaemonsPerf = os.path.join( os.path.dirname( __file__ ), 'xml', 'monitorTemplatesBBCApplicationHostDevice.xml' )
        
        if not os.access( backupDaemonsPerf, os.F_OK ):
            import subprocess

            sys.stdout.write( 'Doing backup of original template /zport/dmd/Monitors/rrdTemplates/PerformanceConf into %s\n' % backupDaemonsPerf )
            cmd = '/opt/zenoss/bin/zendump -R /zport/dmd/Monitors --ignore devices --ignore instances -o %s' % backupDaemonsPerf

            try:
                process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
                ( val, stErr ) = process.communicate()
                ret = process.returncode

                if ret == 0:
                    sys.stdout.write( 'Updating zenoss daemons preformance stats template from %s\n' % bbcDaemonsPerf )
                    cmd = '/opt/zenoss/bin/zenload -i %s' % bbcDaemonsPerf

                    try:
                        process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
                        ( val, stErr ) = process.communicate()
                        ret = process.returncode
                        if ret != 0:
                            sys.stdout.write( "Error:%s\n" % stErr )
                        else:
                            sys.stdout.write( "Output:%s\n" % stErr )

                    except Exception, e:
                        sys.stdout.write( "Failed to load new zenoss daemons performance stats template %s\n" % e )
                        pass
                else:
                    sys.stdout.write( "Error:%s" % stErr )

            except Exception, e:
                sys.stdout.write( "Failed to create backup of zenoss daemons performance stats template %s\n" % e )
                pass

    #def _registerDaemon( self ):
    #    if not os.access( self.daemonLink, os.F_OK ):
    #        try:
    #            os.symlink ( self.daemonSource, self.daemonLink )
    #        except Exception, e:
    #            print 'Failed to create daemon script symlink: %s' % e
    #            pass

    #def _unregisterDaemon( self ):
    #    try:
    #        os.remove ( self.daemonLink )
    #    except Exception, e:
    #        print 'Failed to remove daemon script symlink: %s' % e
    #        pass

    def _registerBBCAppPortlet(self, app):
        zpm = app.zport.ZenPortletManager
        '''
        BBC Applications Portlet
        '''
        portletsrc = os.path.join(os.path.dirname(__file__),'BBCAppPortlet.js')
        p=re.compile(zenPath(''))
        portletsrc=p.sub('',portletsrc) 

        zpm.register_portlet(sourcepath=portletsrc,
            id='BBCAppPortlet',
            title='BBC Applications',
            permission=ZEN_COMMON)
        
        '''
        BBC Devices portlet
        '''
        portletsrc = os.path.join(os.path.dirname(__file__),'BBCDevicesPortlet.js')
        p=re.compile(zenPath(''))
        portletsrc=p.sub('',portletsrc)

        zpm.register_portlet(sourcepath=portletsrc,
            id='BBCDevicesPortlet',
            title='BBC Devices',
            permission=ZEN_COMMON)

        '''
        zenoss daemons portlet    
        '''
        zdportletsrc = os.path.join(os.path.dirname(__file__),'ZDaemonsPorlet.js')
        portletsrc=p.sub('',zdportletsrc)

        zpm.register_portlet(sourcepath=zdportletsrc,
                id='ZDaemonsPorlet',
                title='Zenoss Daemons',
                permission=ZEN_MANAGE_DMD)

    def _patchCollectionEdit(self):
        """update the report template & make a backup of template we are going to modify"""
        try:
            template = os.path.join(os.environ['ZENHOME'], 'Products', "ZenModel", "skins", "zenmodel", "editCollection.pt")
            newtemplate = os.path.abspath( os.path.join( os.path.dirname(__file__), 'skins', 'ZenPacks.BBC.ApplicationHostDevice', 'zenmodel', "editCollection.pt") )
            # first make a backup copy
            shutil.copy2(template, os.path.join(os.environ['ZENHOME'], 'Products', "ZenModel", "skins", "zenmodel", "editCollection.backup"))
            if os.access(template, os.F_OK):
                for attempts in range(3):
                    try:
                        # now try to replace template with our version
                        shutil.copy2(newtemplate, template)
                        break
                    except:
                        time.sleep(1)
                        pass
        except:
            pass

class MySQLEManager(MySqlSendEventMixin, EventManagerBase):

    backend = "mysql"

    perf = {} 

    def timeRun(self, newpoint):
        self.perf[newpoint] = time.time() - sum(self.perf.values()) 

    def pillsetcompare(self, a, b):
        '''
          Sort pills by severity
        '''
        # data structure is:
        # [link, [
        #        [ [ackStatus, countCritical], [ackStatus, countError], ..
        #             ], pillsHTML ]
        a = a[1][0] # point to the ackstatus/count array
        b = b[1][0]
        ackCountsCmp = 0 # used to keep track to sort on faded is nothing else worked out
        #for sindex in range(6):
        bLength = len(b)
        for sindex in range(bLength):
           if cmp(b[sindex], a[sindex]) == 0:
                 # both ackStatus & cnt are identical
                 if ackCountsCmp == 0: ackCountsCmp = cmp(b[sindex][1], a[sindex][1])
                 continue
           else:
                 # we've got a diff
                 if cmp(b[sindex][1], a[sindex][1]) == 0:
                    if b[sindex][1] > 0:
                        return cmp(b[sindex][0], a[sindex][0])
                    else:
                        if ackCountsCmp == 0: ackCountsCmp = cmp(b[sindex][0], a[sindex][0])
                        continue
                 else:
                    return cmp(b[sindex][1], a[sindex][1])
        return  ackCountsCmp


    def getDeviceSummaries(self, zem, severity=0, state=1, prodState=[1000], systemPaths=[], eventClasses=[]):
        '''
          SELECT device, concat('zport/dmd/Devices', DeviceClass, '/' , device) as devPath, severity, count(*) as cnt, sum(eventState) as ack
          FROM status 
          WHERE 
              severity >= 0
              AND prodState IN (1000)
              AND eventState < 2 
              AND (Systems LIKE '%/ServerType/App%' OR Systems LIKE '%/ReleaseEnvironment/Live%')
              GROUP BY device,severity DESC ORDER BY device DESC

            returns { devId1: [['zenevents_5', 0, 3], ...],
                      devId2: [['zenevents_5', 0, 3], ...],
                    }
        '''
        #self.timeRun('start')
 
        select = 'SELECT %s, concat(\'/zport/dmd/Devices\', %s, \'/devices/\', %s ) as %s, %s, count(*) as cnt, sum(%s) as akw FROM %s WHERE ' %\
                    (self.deviceField,
                    'DeviceClass',
                    self.deviceField,
                    self.deviceField,
                    self.severityField,
                    self.stateField,
                    self.statusTable)
        
        where = ''
        # 1) filter by severity
        where = self._wand(where, "%s >= %s", self.severityField, severity)
        # 2) filter by prodState
        if len(prodState) > 0:
            where = self._wand(where, "%s IN (%s)", self.prodStateField, "'"+ "', '".join(map(str,prodState)) + "'")
        # 3) filter by state
        where = self._wand(where, "%s <= %s", self.stateField, state)
        # 4) and by Systems
        if len(systemPaths) > 0:
            link = "%%' OR %s LIKE '%%" % self.SystemField
            #where = self._wand(where,
            where +=   " AND (" + self.SystemField + " LIKE '%" + link.join(map(str,systemPaths)) + "%')"

        # 5) or filter by eventClass (applications)
        if len(eventClasses) > 0:
            link = "%%' OR %s LIKE '%%" % self.eventClassField
            where +=   " AND (" +  self.eventClassField + " LIKE '%" + link.join(map(str,eventClasses)) + "%')"

        select += where
        select += 'GROUP BY %s, %s DESC ORDER BY %s DESC' % (self.deviceField, self.severityField, self.deviceField)
        
        
        sevsum = self.checkCache(select)
        if sevsum: return sevsum
        
        #self.timeRun('checkCache')

        resultsTmp = {}
        results    = []
        colors     = dict({'5':'red', '4':'orange', '3':'yellow', '2':'blue', '1':'grey', '0':'green'})

        conn = zem.connect()
        try:
            curs = conn.cursor()
            curs.execute(select)

            #self.timeRun('mysql_connect')

            outWrapDiv = '<div style="width: 320px">%s</div>'
            template   = ('<div class="evpill-%s" style="%s" onclick="location.href='
                    '\'%s/viewEvents\'" title="%s acknowledged"><span>%s</span> </div>')
            prettyLink = '<a href="%s" class="prettylink">%s</a>'
            for row in curs.fetchall():
                dev, devPath, sev, evtCnt, evtAck = row[:5]
                evtCnt = int(evtCnt)
                evtAck = int(evtAck)
                if not resultsTmp.has_key(dev):
                    resultsTmp[dev] = {'devicePath':devPath}

                resultsTmp[dev][str(sev)] = [ evtAck, evtCnt ]
            
            #self.timeRun('aggregateMysql')          

            for device in resultsTmp.keys():
                pillSet   = ''
                sortStack = []
                for sev in ['5', '4', '3', '2', '1', '0']:
                    if int(sev) < severity: continue
                    color  = colors[sev]
                    style  = 'float: left;'
                    status = [0,0] # default
                    if resultsTmp[device].has_key(sev):
                         status = resultsTmp[device][sev]

                    if (status[1] - status[0]) == 0:
                        # faded
                        if color == 'red':
                            style += ' color:#fff;'
                        else:
                            style += ' color:#999;'
                        color += '-acked'

                    pillSet += template % (color, style, resultsTmp[device]['devicePath'], status[0], status[1] )
                    sortStack.append(status)

                results.append([ prettyLink % (resultsTmp[device]['devicePath'], device) , [sortStack, outWrapDiv % pillSet]])

        finally: 
            #self.timeRun('createdHtml')
            zem.close(conn)
            # sort results before caching
            resultsTmp = {}
            if len(results) > 0:
                results.sort(self.pillsetcompare)

            #self.timeRun('sorted')

            mydict = {'columns':['Device', 'Events'], 'data':[]}
            mydict['data'] = [{'Device':x[0],'Events':x[1][1]} for x in results]

            self.addToCache(select, mydict)
            #self.timeRun('cached') 
            #mydict['perf'] = self.perf
            self.cleanCache()

        return mydict

    def getAppSummaries(self, zem, severity=0, state=1, prodState=None, systemPaths=[], eventClasses=[]):
        '''
        SELECT SUBSTR(eventClass FROM 17) as app, concat('zport/dmd/Events', eventClass), severity, count(*) as cnt, sum(eventState) as akw
        FROM status 
        WHERE 
            severity >= 0
            AND eventClass LIKE '%/BBCApplication/%'
            AND prodState <= 1000
            AND eventState < 2 
            AND (Systems LIKE '%/ServerType/App%')
            GROUP BY eventClass,severity DESC ORDER BY app DESC;
        '''

        #self.timeRun('start')

        select = 'SELECT SUBSTR(%s FROM 17) as app, concat(\'zport/dmd/Events\', %s), %s, count(*) as cnt, sum(%s) as akw FROM %s WHERE ' %\
                   (self.eventClassField,
					self.eventClassField,
                    self.severityField,
                    self.stateField,
                    self.statusTable)
        
        where = ''
        # 1) filter by severity
        where = self._wand(where, "%s >= %s", self.severityField, severity)
        # 2) only BBC Apps please
        where = self._wand(where, "%s LIKE '%s'", self.eventClassField, '/BBCApplication/%')
        # 3) filter by prodState
        if len(prodState) > 0:
            where = self._wand(where, "%s IN (%s)", self.prodStateField, "'"+ "', '".join(map(str,prodState)) + "'")
        # 4) filter by state
        where = self._wand(where, "%s <= %s", self.stateField, state)
        # 5) and by Systems
        if len(systemPaths) > 0:
            link = "%%' OR %s LIKE '%%" % self.SystemField
            where +=   " AND (" + self.SystemField + " LIKE '%" + link.join(map(str,systemPaths)) + "%')"
		# 6) or filter by eventClass (applications)
        if len(eventClasses) > 0:
            link = "%%' OR %s LIKE '%%" % self.eventClassField
            where +=   " AND (" +  self.eventClassField + " LIKE '%" + link.join(map(str,eventClasses)) + "%')"

        select += where
        select += ' GROUP BY %s, %s DESC ORDER BY app DESC' % (self.eventClassField, self.severityField)

        sevsum = self.checkCache(select)
        if sevsum: return sevsum
        
        #self.timeRun('checkCache')

        resultsTmp = {}
        results    = []
        colors     = dict({'5':'red', '4':'orange', '3':'yellow', '2':'blue', '1':'grey', '0':'green'})

        conn = zem.connect()
        try:
            curs       = conn.cursor()
            curs.execute(select)

            #self.timeRun('mysql')

            outWrapDiv = '<div style="width: 320px">%s</div>'
            template   = ('<div class="evpill-%s" style="%s" onclick="location.href='
                    '\'%s/viewEvents\'" title="%s acknowledged"><span>%s</span> </div>')
            prettyLink = '<a href="%s" class="prettylink">%s</a>'

            for row in curs.fetchall():
                app, appPath, sev, evtCnt, evtAck = row[:5]
                evtCnt = int(evtCnt)
                evtAck = int(evtAck)
                if not resultsTmp.has_key(app):
                    resultsTmp[app] = {'applicationPath':appPath}

                resultsTmp[app][str(sev)] = [ evtAck, evtCnt ]
            
            #self.timeRun('aggregateMysql')            

            for application in resultsTmp.keys():
                pillSet   = ''
                sortStack = []
                for sev in ['5', '4', '3', '2', '1', '0']:
                    if int(sev) < severity: continue
                    style  = 'float: left;'
                    color  = colors[sev]
                    status = [0,0] # default
                    if resultsTmp[application].has_key(sev):
                         status = resultsTmp[application][sev]

                    if (status[1] - status[0]) == 0:
                        # faded
                        if color == 'red':
                            style += ' color:#fff;'
                        else:
                            style += ' color:#999;'
                        color += '-acked'

                    pillSet += template % (color, style, resultsTmp[application]['applicationPath'], status[0], status[1] )
                    sortStack.append(status)

                results.append([ prettyLink % (resultsTmp[application]['applicationPath'], application) , [sortStack, outWrapDiv % pillSet]])

        finally: 
            #self.timeRun('createdHtml')
            zem.close(conn)
            # sort results before caching
            resultsTmp = {}
            if len(results) > 0:
                results.sort(self.pillsetcompare)

            #self.timeRun('sorted')

            mydict = {'columns':['Application', 'Events'], 'data':[]}
            mydict['data'] = [{'Application':x[0],'Events':x[1][1]} for x in results]

            self.addToCache(select, mydict)
            #self.timeRun('cached')
            #mydict['perf'] = self.perf
            #mydict['SQL']  = select
            self.cleanCache()

        return mydict

def getBBCAppEvents(self):
    '''
    Crawl Events/BBCApplication  classes to build event summary for the
    dashboard
    '''
    # 1) prepare requested options 
    severity = self.REQUEST.form.get('severity') or 0
    severity = int(severity)

    zem = self.dmd.ZenEventManager

    prodState  = self.REQUEST.form.get('prodState') or zem.dmd.prodStateDashboardThresh
    if not isinstance(prodState, list):
        prodState  = [prodState]
    prodState = [int(x) for x in prodState]

    systemPaths = self.REQUEST.form.get('systemPaths') or []
    if systemPaths:
        if not isinstance(systemPaths, list):
            systemPaths = [ systemPaths ]
        systemPaths = [x.replace('/Systems','',1) for x in systemPaths]

    eventClasses = self.REQUEST.form.get('eventClasses') or []
    if eventClasses:
        if not isinstance(eventClasses, list):
            eventClasses = [ eventClasses ]
        eventClasses = [x.replace('/Events','',1) for x in eventClasses]
        
    myEManager = MySQLEManager('ZenEventManager', hostname=zem.host, username=zem.username,
                               password=zem.password, database=zem.database,
                               port=zem.port)
    return myEManager.getAppSummaries(zem, severity, None, prodState, systemPaths, eventClasses);

def getBBCDevicesEvents(self):
    '''
    Crawl devices and build event pills for the
    dashboard
    '''
    severity = self.REQUEST.form.get('severity') or 0 
    severity = int(severity)

    zem = self.dmd.ZenEventManager

    prodState  = self.REQUEST.form.get('prodState') or zem.dmd.prodStateDashboardThresh
    if not isinstance(prodState, list):
        prodState = [ prodState ]
    prodState = [int(x) for x in prodState]
    
    systemPaths = self.REQUEST.form.get('systemPaths') or []
    if systemPaths:
        if not isinstance(systemPaths, list):
            systemPaths = [ systemPaths ]
        systemPaths = [x.replace('/Systems','',1) for x in systemPaths]

    eventClasses = self.REQUEST.form.get('eventClasses') or []
    if eventClasses:
        if not isinstance(eventClasses, list):
            eventClasses = [ eventClasses ]
        eventClasses = [x.replace('/Events','',1) for x in eventClasses]

    myEManager = MySQLEManager('ZenEventManager', hostname=zem.host, username=zem.username,
                               password=zem.password, database=zem.database,
                               port=zem.port)
    return myEManager.getDeviceSummaries(zem, severity, None, prodState, systemPaths, eventClasses);


def getZenossStatus(self):
    '''
    Return status of all Zenos Daemons
    '''
    daemons = self.dmd.zport.About.zenossInfo.getZenossDaemonStates()
    
    mydict = {'columns':[], 'data':[]}
    mydict['columns'] = ['Daemon', 'PID', 'Status']    
    
    for daemon in daemons:
        status = '<img src="/zport/dmd/img/red_dot.png"/>'
        if daemon['color'] == '#0F0':
            status = '<img src="/zport/dmd/img/green_dot.png"/>'

        if not daemon['pid']:
                    daemon['pid'] = ' '

        mydict['data'].append({ mydict['columns'][0]:daemon['name'], 
                mydict['columns'][1]:daemon['pid'],
                mydict['columns'][2]:status 
            })    
    return mydict

def getSeveritiesAndProdStates(self):
    self.REQUEST.RESPONSE.setHeader('content-type','application/json')
    return json.dumps({
        'severities':self.dmd.ZenEventManager.severities,
        'prodStates':self.dmd.getProdStateConversions(),
        'systems':   [ '/Systems' + x for x in self.dmd.Systems.getOrganizerNames()],
        'eventClasses': [ '/Events' + x for x in self.dmd.Events.getOrganizerNames() ]
    });

def getDevices(self):
    devs = []
    devClasses  = self.REQUEST.get('deviceClass') or None
    devIds      = self.REQUEST.get('deviceId') or None

    query = {'sort_on':'id'}

    if devClasses:
        if  not isinstance(devClasses, (list, tuple)):
            devClasses = [devClasses]
        query['getDeviceClassPath'] = devClasses

    if devIds:
        if not isinstance(devIds, (list, tuple)):
            devIds = [devIds]
        query['id'] = devIds

    brains = self.dmd.Devices.deviceSearch( query )
    self.REQUEST.RESPONSE.setHeader('content-type','application/json')
    return json.dumps([ brain['id']  for brain in brains  ])

def getApps(self):
    paths = [['manual', 'manual']]
    devices = self.REQUEST.get('deviceId')
    if not devices:
       self.REQUEST.RESPONSE.setHeader('status', 404)
       paths['ERROR'] = 'Device ids not specified'
       self.REQUEST.RESPONSE.setHeader('content-type','application/json')
       return json.dumps(paths)

    if isinstance(devices, basestring):
        devices = [devices]
    for devId in devices:
        dev = self.dmd.Devices.deviceSearch({'id': devId}) 
        if len(dev):
            dev = dev[0].getObject()
            for brain in dev.componentSearch({'getParentDeviceName':devId, 'monitored':True, 'meta_type':'BBCApplication'}):
                path = (brain.getPrimaryId.split('/'))[-1]
                paths.append([path, path])        
    self.REQUEST.RESPONSE.setHeader('content-type','application/json')
    return json.dumps(paths)

def getAppKpis(self):
    paths = [] 

    devices = self.REQUEST.get('deviceId')
    if not devices:
       self.REQUEST.RESPONSE.setHeader('status', 404)
       paths.append(['ERROR', 'Device ids not specified'])
       self.REQUEST.RESPONSE.setHeader('content-type','application/json')
       return json.dumps(paths)

    if isinstance(devices, basestring):
        devices = [devices]

    applicationIds = self.REQUEST.get('applicationId')
    if not applicationIds:
       applicationIds = []
    elif isinstance(applicationIds, basestring):
       applicationIds = [applicationIds]

    for devId in devices:
        dev = self.dmd.Devices.deviceSearch({'id': devId}) 
        if len(dev):
            dev = dev[0].getObject()
            devPathL = len(dev.getPrimaryId()) + 1
            for brain in dev.componentSearch({'getParentDeviceName':devId, 'monitored':True, 'meta_type':'BBCApplication'}):
                # skip if not requested
                if  len(applicationIds) and (brain.getPrimaryId.split('/'))[-1] not in applicationIds: continue
                # we got here so this is one of the wanted records
                app = brain.getObject()
                for kpi in app.ApplicationToKPI():
                    paths.append( [ kpi.getPrimaryId()[devPathL:], kpi.name() ] )

            # fetch non-automated datasources
            if 'manual' in applicationIds:
                for brain in dev.componentSearch.evalAdvancedQuery(
                                 Eq('getParentDeviceName', devId) & 
                                 Eq('monitored', True) & 
                                 ~ In( 'meta_type', ['BBCApplication', 'BBCApplicationKPI', 'BBCApplicationKPIDerive', 
                                       'BBCApplicationKPIAbsolute', 'BBCApplicationKPICounter', 'BBCApplicationKPIGauge'])):
                    dsId = (brain.getPrimaryId.split('/'))[-1] 
                    if dsId == '-': continue
                    try:
                        ds = brain.getObject()
                        paths.append( [ ds.getPrimaryId()[devPathL:], ds.name() ] )
                    except:
                        continue
    
    self.REQUEST.RESPONSE.setHeader('content-type','application/json')
    return json.dumps(paths)

# Monkey-patch onto zport
from Products.ZenModel.ZentinelPortal import ZentinelPortal
ZentinelPortal.getBBCEvents = getBBCAppEvents
ZentinelPortal.getBBCDevicesEvents = getBBCDevicesEvents
ZentinelPortal.getZenossStatus = getZenossStatus
ZentinelPortal.getMonitoredApps = getApps
ZentinelPortal.getMonitoredKpis = getAppKpis
ZentinelPortal.getDevicesByClass = getDevices
ZentinelPortal.getSeveritiesAndProdStates = getSeveritiesAndProdStates
