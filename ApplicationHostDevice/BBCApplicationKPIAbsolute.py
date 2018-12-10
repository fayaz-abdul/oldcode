from Globals import InitializeClass
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPI import BBCApplicationKPI

class BBCApplicationKPIAbsolute(BBCApplicationKPI):

    portal_type = meta_type = 'BBCApplicationKPIAbsolute'

    factory_type_information = (
        {
            'id'             : 'BBCApplicationKPIAbsolute',
            'meta_type'      : 'BBCApplicationKPIAbsolute',
            'description'    : 'BBC Application KPI',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplicationKPIAbsolute',
            'factory'        : 'manage_addBBCApplicationKPIAbsolute',
            'immediate_view' : 'applicationPerformance',
            'actions'        : ()
        },
    )

InitializeClass(BBCApplicationKPIAbsolute)
