from Globals import InitializeClass
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPI import BBCApplicationKPI

class BBCApplicationKPICounter (BBCApplicationKPI):

    portal_type = meta_type = 'BBCApplicationKPICounter'

    factory_type_information = (
        {
            'id'             : 'BBCApplicationKPICounter',
            'meta_type'      : 'BBCApplicationKPICounter',
            'description'    : 'BBC Application KPI',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplicationKPICounter',
            'factory'        : 'manage_addBBCApplicationKPICounter',
            'immediate_view' : 'applicationPerformance',
            'actions'        : ()
        },
    )

InitializeClass(BBCApplicationKPICounter)
