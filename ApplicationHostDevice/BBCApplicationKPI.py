import os

from Globals import InitializeClass

from Products.ZenRelations.RelSchema import *
from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenModel.ZenossSecurity import ZEN_VIEW, ZEN_CHANGE_SETTINGS

_kw = dict(mode='w')

class BBCApplicationKPI(DeviceComponent, ManagedEntity):
    "BBC Application KPI"
    
    portal_type = meta_type = 'BBCApplicationKPI'

    snmpindex = -1
    kpiName   = ''
    url       = ''

    _properties = (
        dict(id='kpiName',          type='string', **_kw),
        #dict(id='url',              type='string', **_kw),
    )

    _relations = (
        ('KPIToApplication', ToOne(ToManyCont, 'ZenPacks.BBC.ApplicationHostDevice.BBCApplication', 'ApplicationToKPI')),
    )
    
        # Screen action bindings (and tab definitions)
    factory_type_information = (
        {
            'id'             : 'BBCApplicationKPI',
            'meta_type'      : 'BBCApplicationKPI',
            'description'    : 'BBC Application KPI',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplicationKPI',
            'factory'        : 'manage_addBBCApplicationKPI',
            'immediate_view' : 'applicationPerformance',
            'actions'        :
            (
#                { 'id'            : 'templates'
#                , 'name'          : 'Templates'
#                , 'action'        : 'objTemplates'
#                , 'permissions'   : (ZEN_CHANGE_SETTINGS, )
#                },
            )
        },
    )

    def device(self):
        return self.host()

    def snmpIgnore(self):
        return ManagedEntity.snmpIgnore(self) or self.snmpindex < 0

InitializeClass(BBCApplicationKPI)
