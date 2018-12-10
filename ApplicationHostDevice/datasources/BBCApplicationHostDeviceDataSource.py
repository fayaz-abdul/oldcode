__doc__='''BBCApplicationHostDeviceDataSource.py

Defines datasource for BBCApplicationHostDevice
'''

from Globals import InitializeClass

import Products.ZenModel.BasicDataSource as BasicDataSource
from Products.ZenModel.ZenPackPersistence import ZenPackPersistence
from AccessControl import ClassSecurityInfo, Permissions
from Products.ZenUtils.ZenTales import talesCompile, getEngine

import os

class BBCApplicationHostDeviceDataSource(ZenPackPersistence, BasicDataSource.BasicDataSource):
    
    BBC_APPLICATION_HOST_DEVICE = 'BBCApplicationHostDevice'

    ZENPACKID = 'ZenPacks.BBC.ApplicationHostDevice' 

    sourcetypes = (BBC_APPLICATION_HOST_DEVICE,)
    sourcetype = BBC_APPLICATION_HOST_DEVICE

    eventClass = '/BBCApplication'
    enabled = False

    _properties = BasicDataSource.BasicDataSource._properties
        
    _relations = BasicDataSource.BasicDataSource._relations + ()

    factory_type_information = ( 
    { 
        'immediate_view' : 'editBBCApplicationHostDeviceDataSource',
        'actions'        :
        ( 
            { 'id'            : 'edit',
              'name'          : 'Data Source',
              'action'        : 'editBBCApplicationHostDeviceDataSource',
              'permissions'   : ( Permissions.view, ),
            },
        )
    },
    )

    security = ClassSecurityInfo()

    def __init__(self, id, title=None, buildRelations=True):
        BasicDataSource.BasicDataSource.__init__(self, id, title, buildRelations)

    def getDescription(self):
        if self.sourcetype == self.BBC_APPLICATION_HOST_DEVICE:
            return self.ipAddress
        return BasicDataSource.BasicDataSource.getDescription(self)

    def useZenCommand(self):
        return False

    def getCommand(self, context):
        # nothing to do
        pass

    def checkCommandPrefix(self, context, cmd):
        return cmd

    def addDataPoints(self):

        dps = (
            ('brokenAppOidCounter',     'GAUGE'),
            ('brokenKpiOidCounter',     'GAUGE'),
            ('collectedAppOidCounter',  'GAUGE'),
            ('collectedKpiOidCounter',  'GAUGE'),
            ('failedRequests',          'GAUGE'),
            ('foundAppOidCounter',      'GAUGE'),
            ('oidsCounter',             'GAUGE'),
            ('requestTime',             'GAUGE'),
            ('totalRequests',           'GAUGE'),
            ('totalTime',               'GAUGE'),
        )

        for dpd in dps:
            dp = self.manage_addRRDDataPoint(dpd[0])
            dp.rrdtype = dpd[1]
            dp.rrdmin = 0


    def zmanage_editProperties(self, REQUEST=None):
        '''validation, etc'''
        if REQUEST:
            # ensure default datapoint didn't go away
            self.addDataPoints()
            # and eventClass
            if not REQUEST.form.get('eventClass', None):
                REQUEST.form['eventClass'] = self.__class__.eventClass
        return BasicDataSource.BasicDataSource.zmanage_editProperties(self, REQUEST)

InitializeClass(BBCApplicationHostDeviceDataSource)
