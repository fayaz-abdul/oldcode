__doc__='''BBCConfig

ZenHub service for handling BBCApplicationHost configuration
'''
from Products.ZenHub.services.PerformanceConfig import PerformanceConfig
from twisted.spread import pb
import transaction
import traceback
import simplejson
import os
# next two needed to be able to check instances
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationHostDevice import BBCApplicationHostDevice
from Products.ZenEvents.EventClass import EventClass
from ZenPacks.BBC.ApplicationHostDevice.lib.utils import ConfigParser

thresholds_data = {}
thresholds_config_dir = ""
default_thresholds_config_dir = '/opt/zenoss-dynamic-configs'

ATTRIBUTES = (
    'id',
    'zBBCUseSSH',
    'zSSHTimeout',
    'zBBCAdditionalAppOidSpace',
    'zCollectorClientTimeout',
    'zKeyPath',
    'zCommandUsername',
    'zSnmpAuthPassword',
    'zSnmpAuthType',
    'zSnmpCommunity',
    'zSnmpPort',
    'zSnmpPrivPassword',
    'zSnmpPrivType',
    'zSnmpProxy',
    'zSnmpProxyContextName',
    'zSnmpSecurityName',
    'zSnmpTimeout',
    'zSnmpTries',
    'zSnmpVer'
)


class deviceProperties(pb.Copyable, pb.RemoteCopy):
    """
    Represents the needed configuration for an individual device object.
    """

    def __init__(self, device):
        "Store the properties from the device"
        for propertyName in ATTRIBUTES:
            try:
                setattr(self, propertyName, getattr(device, propertyName, None))
            except:
                pass
        self.id              = device.id
        self.productionState = device.productionState
        self.thresholds      = {}

        platenv = [x.replace('/Platform/', '') for x in device.getSystemNames() if x.startswith("/Platform/")]
        if len(platenv) == 1:
            platenv = platenv[0]
            if not thresholds_data.has_key(platenv):
                thresholds_config_path = os.path.join(thresholds_config_dir, platenv, 'thresholds.cfg')
                if os.path.exists(thresholds_config_path):
                    try:
                        f = open(thresholds_config_path, 'r')
                        thresholds_data[platenv] = simplejson.loads(f.read())
                        f.close()
                    except Exception, e:
                        pass
                        #No instance of logger                        
                        #self.log.error('Failed to load the JSON config file %s: exception is %s' % (thresholds_config_path, str(e)))
            if thresholds_data.has_key(platenv):
                apps = [x.id for x in device.applications()]
                for app in thresholds_data[platenv].keys():
                    if app in apps:
                        self.thresholds[app]= thresholds_data[platenv][app]
                    

pb.setUnjellyableForClass(deviceProperties, deviceProperties)


class BBCConfig(PerformanceConfig):
   

    # note: if configuration of device changes on HUB side (e.g. zProperties etc) it will call getDeviceConfig() and then sendDeviceConfig()
    # to propagate changes back to the collector daemon (this is PUSH)
    def getDeviceConfig(self, device):
        '''
           override method from PerformanceConfig
           load the properties that we need for a particular device
        '''
        #self.log.info('getDeviceConfig(%s)' % device.id)
        #return deviceProperties(device.primaryAq())

        dev = device.primaryAq()
        devicePropObj = self._filterDevice(dev) or None
        if devicePropObj is not None:
           self.log.info('BBCConfig.getDeviceConfig(%s) - device will be added for collection' % device.id)
        else:
           self.log.info('BBCConfig.getDeviceConfig(%s) - device will be removed from collection' % device.id)
           # this should call listener.callRemote('deleteDevice', device.id) defined in PerformanceConfig.py
           # on the collector daemon (this is PUSH)
        return devicePropObj
 
    def sendDeviceConfig(self, listener, config):
        '''
           override method from PerformanceConfig
           how do we push updates to the collector
        '''
        return listener.callRemote('updateDevice', config)


    def _filterDevice(self, device):
        """
        Determines if the specified device should be included for consideration
        in being sent to the remote collector client.

        Subclasses should override this method, call it for the default
        filtering behavior, and then add any additional filtering as needed.

        @param device: the device object to filter
        @return: deviceProperties object if this device should be included for further processing or None 
        @rtype: deviceProperties object or None
        """
        #self.log.info('device %s is BBCApplicationHostDevice? %s' % (device.id,isinstance(device, BBCApplicationHostDevice) ))
        # monitorDevice() -> is device in production state
        if device.monitorDevice() and isinstance(device, BBCApplicationHostDevice):
            return deviceProperties(device)
        
        return None#device.monitorDevice() and isinstance(device, BBCApplicationHostDevice) 


    def remote_getDevices(self, devices=[]):
        '''
           service registered in zenhub to provide the list of devices in current remote collector
        '''
        global thresholds_data, thresholds_config_dir
        thresholds_data = {} #start with empty collection when the collector requests the devices
        try:
            configFile = os.path.join(os.environ['ZENHOME'], 'etc', 'bbcappscollector.conf')
            config = ConfigParser( configFile, self.log )
            thresholds_config_dir = str(config.get('thresholdsConfigDir', default_thresholds_config_dir))
        except Exception, e:
            self.log.error('Failed to parse the config file bbcappscollector.conf: exception is %s' % (str(e))) 
        
        configs = []
        # device provided by options
        if len(devices)>0:
            for devId in devices:
                # self.config -> current collector / monitor
                device = self.config.findDevice(devId) or None
                # device.primaryAq() -> to get proper device from ZODB
                # note: only simple objects can be passed ( not callable )
                if device: #and self._filterDevice(device.primaryAq()):
                    devicePropObj = self._filterDevice(device.primaryAq())
                    if devicePropObj is not None:
                        configs.append(devicePropObj)
        else:
            for device in self.config.devices():
                devicePropObj = self._filterDevice(device.primaryAq())
                if devicePropObj is not None:
                    configs.append(devicePropObj)

        return configs
            #return [ deviceProperties(d.primaryAq()) for d in self.config.devices() ]


    def remote_checkEventClass(self, eventClassName=""):
        '''
           Try to find the event class, create it on thefly if it does not exists
           returns the event class name if found/created or None if it fails to create it.
        '''
        #self.log.info('remote_checkEventClass %s' % eventClassName)
        if not eventClassName: return
        evtClass = ""
        try:
            evtClass = self.dmd.Events.getOrganizer(eventClassName)
        except KeyError:
            try:
                # TODO: figure out how to do the syncdb call
                # we need a robust conflict handling here
                #self.syncdb()
                if eventClassName.startswith('/'):
                    #remove initial /
                    eventClassName = eventClassName.lstrip('/')
          
                self.dmd.Events.manage_addOrganizer('/Events/%s' % eventClassName)
                # maybe there is better way of doing this (possible conflicts)
                transaction.get().commit()
                evtClass = self.dmd.Events.getOrganizer(eventClassName)
            except Exception, e:
                self.log.error('Failed to create event class %s: %s' % (eventClassName, e))
                self.log.info(traceback.format_exc())
            

        if isinstance(evtClass, EventClass):
             return '/' + '/'.join(evtClass.getPrimaryPath()[4:] )

        return None 


