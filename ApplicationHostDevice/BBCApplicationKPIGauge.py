from Globals import InitializeClass
from ZenPacks.BBC.ApplicationHostDevice.BBCApplicationKPI import BBCApplicationKPI

class BBCApplicationKPIGauge (BBCApplicationKPI):

    portal_type = meta_type = 'BBCApplicationKPIGauge'

    factory_type_information = (
        {
            'id'             : 'BBCApplicationKPIGauge',
            'meta_type'      : 'BBCApplicationKPIGauge',
            'description'    : 'BBC Application KPI',
            'icon'           : 'Device_icon.gif',
            'product'        : 'BBCApplicationKPIGauge',
            'factory'        : 'manage_addBBCApplicationKPIGauge',
            'immediate_view' : 'applicationPerformance',
            'actions'        : ()
        },
    )

InitializeClass(BBCApplicationKPIGauge)
