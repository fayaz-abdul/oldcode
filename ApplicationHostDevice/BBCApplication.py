from Globals import InitializeClass

from Products.ZenRelations.RelSchema import *
from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenUtils.Utils import convToUnits

from Products.ZenModel.ZenossSecurity import ZEN_VIEW, ZEN_CHANGE_SETTINGS

_kw = dict(mode='w')

#import logging
#log = logging.getLogger("zen.zenmodeler")

from Products.ZenUtils.Utils import prepId
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPIDerive import BBCApplicationKPIDerive
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPICounter import BBCApplicationKPICounter
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPIGauge import BBCApplicationKPIGauge
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPIAbsolute import BBCApplicationKPIAbsolute

def manage_addKPI(context, id, type='GAUGE'):
    """build a performance indicator object"""

    perfId = prepId(id)
    type = type.upper()
    perfIndicator = None

    # get KPI object from database if it already exists
    try:
       perfIndicator = context._getOb(perfId)
       return perfIndicator
    except:
       pass

    # call a proper KPI class
    # COUNTER to DERIVE conversion: There is a class BBCApplicationKPICounter. Reseting counterts lid
    # to a big amount of fake alerts, so we convert them to DERIVE with min value = 0
    if type == 'COUNTER' or type == 'DERIVE':
        perfIndicator = BBCApplicationKPIDerive(perfId)
    elif type == 'GAUGE':
        perfIndicator = BBCApplicationKPIGauge(perfId)
    elif type == 'ABSOLUTE':
        perfIndicator = BBCApplicationKPIAbsolute(perfId)
    
    if perfIndicator: context._setObject(perfId, perfIndicator)
    return perfIndicator


class BBCApplication(DeviceComponent, ManagedEntity):
    "BBC Application"
    
    portal_type = meta_type = 'BBCApplication'

    snmpindex = -1
    appName = ""
    appOid = ""

    _properties = (
        dict(id='appName',        type='string',    **_kw),
    )

    _relations = (
        ('host', ToOne(ToManyCont, 'ZenPacks.BBC.ApplicationHostDevice.BBCApplicationHostDevice', 'applications')),
        ('ApplicationToKPI', ToManyCont(ToOne, 'ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPI', 'KPIToApplication')),
    )

    # Screen action bindings (and tab definitions)
    factory_type_information = (
        {
            'id'             : 'BBCApplication',
            'meta_type'      : 'BBCApplication',
            'description'    : 'Application',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplication',
            'factory'        : 'manage_addBBCApplication',
            'immediate_view' : 'applicationPerformance',
            'actions'        :
            ()
        },
    )

    def device(self):
        return self.host()

    def loadPath(self, path):
        return self.dmd.unrestrictedTraverse(path)

    def snmpIgnore(self):
        return ManagedEntity.snmpIgnore(self) or self.snmpindex < 0

    def getAppKPISetup(self, perf_data):
        # Do work to extract the information ...

        # clean the old not existing KPIs from ApplicationToKPI
        newKPIids = perf_data.keys()
        oldKPIids = self.ApplicationToKPI.objectIdsAll()
        for oldKPIid in oldKPIids:
            if not oldKPIid in newKPIids:
                self.ApplicationToKPI._delObject(oldKPIid)

        for key in perf_data.keys():
            # build kpi
            kpi = manage_addKPI(self.ApplicationToKPI, key, perf_data[key]['valueType'] )

            for subkey in perf_data[key]:
                # format exmaple => key:Queue_2 subkey:valueType data:COUNTER
                perf_attr = getattr(kpi, subkey, None)

                if callable(perf_attr):
                    perf_attr(perf_data[key][subkey])
                else:
                    setattr(kpi, subkey, perf_data[key][subkey])

    def getPerformanceList(self):
        return self.ApplicationToKPI

InitializeClass(BBCApplication)
