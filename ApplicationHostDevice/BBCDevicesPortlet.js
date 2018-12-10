var BBCDevicesPortlet = YAHOO.zenoss.Subclass.create(YAHOO.zenoss.portlet.Portlet);

BBCDevicesPortlet.prototype = {
    __class__:"YAHOO.zenoss.portlet.BBCDevicesPortlet",
    __init__: function(args) {
        args = args || {};
        id          = 'id'          in args? args.id         : getUID('BBCDevices');
        title       = 'title'       in args? args.title      : "BBC Devices";
        bodyHeight  = 'bodyHeight'  in args? args.bodyHeight :200;
        refreshTime = 'refreshTime' in args? args.refreshTime: 60;
        prodState   = 'prodState'   in args? args.prodState  : [1000, 500, 400, 300, -1];
        systemPaths = 'systemPaths' in args? args.systemPaths: [ '/Systems/' ];
        eventClasses= 'eventClasses'in args? args.eventClasses: [];
        severity    = 'severity'    in args? args.severity   : 1;
        datasource  = 'datasource'  in args? args.datasource :
            new YAHOO.zenoss.portlet.TableDatasource({
                method: 'GET',
                url:'/zport/getBBCDevicesEvents',
                queryArguments: {
                    'prodState'  : prodState,
                    'systemPaths': systemPaths,
                    'severity'   : severity,
                    'eventClasses' : eventClasses
                } 
            });
        this.superclass.__init__(
            {id:          id, 
             title:       title,
             datasource:  datasource,
             refreshTime: refreshTime,
             bodyHeight:  bodyHeight
            }
        );
       this.buildSettingsPane();
    },
    buildSettingsPane: function() {
        s = this.settingsSlot;

        var inArr = function(a, val) {
            var i = a.length;
            while (i--) {
                if (a[i] == val) {
                  return true;
                }
            }
            return false;
        };

        var getopt = method(this, function(x) {
                        // build prodState option
                        var opts = {'value':x[1]};
                        var prodStates = this.datasource.queryArguments['prodState'];
                        if (inArr(prodStates, x[1])){ opts['selected']=true; }
                        return OPTION(opts, x[0]); 
        });
        var getSeverityOpt = method(this, function(value, name) {
                        // build severity option
                        var opts = {'value':value};
                        var severity = this.datasource.queryArguments['severity'];
                        if (severity==value){ opts['selected']=true; }
                        return OPTION(opts, name);
        });
        var getSystemsOpt = method(this, function(x) {
                        // build prodState option
                        var opts = {'value':x};
                        var systemPaths = this.datasource.queryArguments['systemPaths'];
                        if ( inArr(systemPaths, x) ){ opts['selected']=true; }
                        return OPTION(opts, x);
        });
        var getEventClassesOpt = method(this, function(x) {
                        // build prodState option
                        var opts = {'value':x};
                        var evtClasses = this.datasource.queryArguments['eventClasses'];
                        if ( inArr(evtClasses, x) ){ opts['selected']=true; }
                        return OPTION(opts, x);
        });
        var createOptions = method(this, function(jsondoc) {
                        // deal with prodStates
                        forEach(jsondoc['prodStates'], method(this, function(x) {
                            var opt = getopt(x);
                            appendChildNodes(this.prodState, opt);
                        }));
                        
                        var severitiesCount = keys(jsondoc['severities']).length -1;
                        var opt;
                        var i;
                        for (i = severitiesCount; i>0; i--){
                            opt = getSeverityOpt(i, jsondoc['severities'][i]);
                            appendChildNodes(this.severity, opt);
                        }

                        var systemsCount = jsondoc['systems'].length;
                        for (i=0; i<systemsCount; i++){
                            opt = getSystemsOpt(jsondoc['systems'][i]);
                            appendChildNodes(this.systemPaths, opt);
                        }

                        var eventClassesCount = jsondoc['eventClasses'].length;
                        for (i=0; i<eventClassesCount; i++){
                            opt = getEventClassesOpt(jsondoc['eventClasses'][i]);
                            appendChildNodes(this.eventClasses, opt);
                        }

                    });

        this.prodState = SELECT({'size':'5', 'multiple':'multiple'}, null);
        prodStateSelect = DIV({'class':'portlet-settings-control'}, [
                            DIV({'class':'control-label'}, 'Production State'),
                             this.prodState
                           ]);
        appendChildNodes(s, prodStateSelect);

        this.severity = SELECT(null, null);
        severitySelect = DIV({'class':'portlet-settings-control'}, [
                            DIV({'class':'control-label'}, 'Min Severity'),
                             this.severity
                           ]);
        appendChildNodes(s, severitySelect);

        this.systemPaths= SELECT({'size':'5', 'multiple':'multiple'}, null);
        systemPathSelect = DIV({'class':'portlet-settings-control'}, [
                            DIV({'class':'control-label'}, 'Systems'),
                             this.systemPaths
                           ]);
        appendChildNodes(s, systemPathSelect);

        this.eventClasses = SELECT({'size':'5', 'multiple':'multiple'}, null);
        eventClassesSelect = DIV({'class':'portlet-settings-control'}, [
                            DIV({'class':'control-label'}, 'Event Classes'),
                             this.eventClasses
                           ]);
        appendChildNodes(s, eventClassesSelect);

        d = loadJSONDoc('/zport/dmd/getSeveritiesAndProdStates');
        d.addCallback(method(this, createOptions)); 

    },
    submitSettings: function(e, settings) {
        var postContent = settings?settings.postContent:
                          this.datasource.postContent;
        //prodState
        this.datasource.queryArguments['prodState'] = new Array();
        var i;
        for (i = 0; i < this.prodState.options.length; i++){ 
            if (this.prodState.options[ i ].selected){ 
                this.datasource.queryArguments['prodState'].push(this.prodState.options[ i ].value);
            }
        }
        //severity
        this.datasource.queryArguments['severity'] = this.severity.value;

        //systems
        this.datasource.queryArguments['systemPaths'] = new Array();
        for (i = 0; i < this.systemPaths.options.length; i++){
                if (this.systemPaths.options[ i ].selected){
                  this.datasource.queryArguments['systemPaths'].push(this.systemPaths.options[ i ].value);
                }
        }
        //eventClasses
        this.datasource.queryArguments['eventClasses'] = new Array();
        for (i = 0; i < this.eventClasses.options.length; i++){
                if (this.eventClasses.options[ i ].selected){
                  this.datasource.queryArguments['eventClasses'].push(this.eventClasses.options[ i ].value);
                }
        }
        this.superclass.submitSettings(e, { 
                queryArguments: this.datasource.queryArguments  
        }); 
    },
    fillTable: function(contents) {
        var columnDefs = contents.columnDefs;
        var dataSource = contents.dataSource;
        i=0;
        var oConfigs = {};
        addElementClass(this.body, 'yui-skin-sam');
        if (this.dataTable) {
            oRequest = {'results':dataSource.liveData};
            this.dataTable.onDataReturnInitializeTable(null, oRequest);
        } else {
            var myDataTable = new YAHOO.widget.DataTable(
                this.body.id, columnDefs, dataSource, oConfigs);
            this.dataTable = myDataTable;
        }
    }
};
YAHOO.zenoss.portlet.BBCDevicesPortlet = BBCDevicesPortlet;
