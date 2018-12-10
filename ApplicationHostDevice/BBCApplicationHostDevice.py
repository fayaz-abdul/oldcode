import logging
log = logging.getLogger("zen.BBC.ApplicationHostDevice.BBCApplicationHostDevice")

from Globals import InitializeClass
from Products.ZenModel.Device import Device
from Products.ZenModel.ZenossSecurity import ZEN_VIEW
from Products.ZenRelations.RelSchema import *

import copy

class BBCApplicationHostDevice(Device):
    """BBCApplicationHostDevice"""

    _relations = Device._relations + (
                ('applications', ToManyCont(ToOne, "ZenPacks.BBC.ApplicationHostDevice.BBCApplication", "host")),
    )

    factory_type_information = (
            {
                'id'             : 'BBCApplicationHostDevice',
                'meta_type'      : 'BBCApplicationHostDevice',
                'immediate_view' : 'deviceStatus',
                'actions'        :
                (
                    { 'id'            : 'status'
                    , 'name'          : 'Status'
                    , 'action'        : 'deviceStatus'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'osdetail'
                    , 'name'          : 'OS'
                    , 'action'        : 'deviceOsDetail'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'bbcApplication'
                    , 'name'          : 'BBC Applications'
                    , 'action'        : 'bbcApplication'
                    , 'permissions'   : (ZEN_VIEW,)
                    },
                    { 'id'            : 'swdetail'
                    , 'name'          : 'Software'
                    , 'action'        : 'deviceSoftwareDetail'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'hwdetail'
                    , 'name'          : 'Hardware'
                    , 'action'        : 'deviceHardwareDetail'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'events'
                    , 'name'          : 'Events'
                    , 'action'        : 'viewEvents'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'perfServer'
                    , 'name'          : 'Perf'
                    , 'action'        : 'viewDevicePerformance'
                    , 'permissions'   : (ZEN_VIEW, )
                    },
                    { 'id'            : 'edit'
                    , 'name'          : 'Edit'
                    , 'action'        : 'editDevice'
                    , 'permissions'   : ("Change Device",)
                    },
                )
            },
        )

InitializeClass(BBCApplicationHostDevice)
