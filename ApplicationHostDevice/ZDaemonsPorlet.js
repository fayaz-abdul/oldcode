var ZDaemonsPorlet = YAHOO.zenoss.Subclass.create(YAHOO.zenoss.portlet.Portlet);

ZDaemonsPorlet.prototype = {
    __class__:"YAHOO.zenoss.portlet.ZDaemonsPorlet",
    __init__: function(args) {
        args = args || {};
        id = 'id' in args? args.id : getUID('watchlist');
        title = 'title' in args? args.title: "Zenoss Status ",
        datasource = 'datasource' in args? args.datasource :
            new YAHOO.zenoss.portlet.TableDatasource({
                url:'/zport/getZenossStatus',
                postContent: []});
        bodyHeight = 'bodyHeight' in args? args.bodyHeight:200;
        refreshTime = 'refreshTime' in args? args.refreshTime: 60;
        this.superclass.__init__(
            {id:id,
	     title: title, 
             datasource:datasource,
             refreshTime: refreshTime,
             bodyHeight: bodyHeight
            }
        );
    },
    fillTable: function(contents) {
        var columnDefs = contents.columnDefs;
        var dataSource = contents.dataSource;
        i=0;
        var oConfigs = {};
        addElementClass(this.body, 'yui-skin-sam');
        if (this.dataTable) {
            oRequest = {'results':dataSource.liveData}
            this.dataTable.onDataReturnInitializeTable(null, oRequest);
        } else {
            var myDataTable = new YAHOO.widget.DataTable(
                this.body.id, columnDefs, dataSource, oConfigs);
            this.dataTable = myDataTable;
        }
    }
}
YAHOO.zenoss.portlet.ZDaemonsPorlet = ZDaemonsPorlet;
