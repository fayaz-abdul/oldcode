from Globals import InitializeClass
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPI import BBCApplicationKPI

class BBCApplicationKPIDerive(BBCApplicationKPI):

    portal_type = meta_type = 'BBCApplicationKPIDerive'

    factory_type_information = (
        {
            'id'             : 'BBCApplicationKPIDerive',
            'meta_type'      : 'BBCApplicationKPIDerive',
            'description'    : 'BBC Application KPI',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplicationKPIDerive',
            'factory'        : 'manage_addBBCApplicationKPIDerive',
            'immediate_view' : 'applicationPerformance',
            'actions'        : ()
        },
    )

InitializeClass(BBCApplicationKPIDerive)
