import Globals
import time, re, sys, traceback
import logging
import ZenPacks.BBC.ApplicationHostDevice.lib.BBCCustomErrors
from ZenPacks.BBC.ApplicationHostDevice.lib.BBCApplicationSNMPFormatTest import BBCApplicationSNMPFormatTest
from Products.ZenUtils.Utils import prepId

class ConfigParser(object):
    
    def __init__( self, filename, log ):
        self.config = {}
        self.log = log
        self.getConfigFileDefaults ( filename ) 

    def getConfigFileDefaults( self, filename ):
        """
        Parse a config file which has key-value pairs delimited by white space,
        and update the parser's option defaults with these values.

        @parameter filename: name of configuration file
        @type filename: string
        """

        try:
            configFile = open(filename)
            lines = configFile.readlines()
            configFile.close()
        except Exception, e:
            self.log.warning( "Unable to read config file %s -- skipping\n%s" % ( filename, str(e) ) )
            return self.config

        lineno = 0
        for line in lines:

            lineno += 1
            if line.lstrip().startswith('#'): continue
            if line.strip() == '': continue

            try:
                key, value = line.strip().split(None, 1)
                self.config[ key ] = value        
            except ValueError:
                self.log.warning( "Missing value on line %d" % lineno )
                continue
            except Exception, e:
                self.log.warning( str( e ) )
                continue

    def get( self, key, default = None ):

        if self.config.has_key( key ):
            return self.config[ key ]
        else:
            return default

class OidParser(object):
    '''
      helper class to parse a BBCApplication oid
    '''
    def __init__(self, baseOid='.1.3.6.1.4.1.2333.3.2', oidData=[], log=None):
        self.baseOid         = baseOid 
        self.log             = log or logging.getLogger('zen.bbcappscollector')
        self.validatorErrors = []
        self._uniqPrefix     = '_+'

        # self.id = complete oid
        self.id, self.rawValue = oidData

        pairs = self.rawValue.split('|')
        # are there at least two  '|' (3 columns)? If not then skip this row 
        if len(pairs) < 3: raise ValueError( 'Not a BBCApplication oid: %s' % oidData ) 

        self.subOid = self.id.replace(self.baseOid,'')
        
        # parse all key/val for this snmp row
        self.data = {self._uniqPrefix + 'oid': self.id,
                     self._uniqPrefix + 'subOid': self.subOid,
                     self._uniqPrefix + 'eventSubClass':'',
                     self._uniqPrefix + 'url':None,
                     self._uniqPrefix + 'valueType':'GAUGE'}

        for pair in pairs:
            pair = pair.split('=', 1)
            if len(pair) == 2:
               self.data[ self._uniqPrefix +  pair[0] ] = pair[1]
        
        # remove / from columns used in event class paths
        for field in ['appName', 'testName', 'kpiName']:
            field = self._uniqPrefix + field
            if self.data.has_key(field):
               self.data[field] = prepId(self.data[field]).strip('/').replace(' ','_').replace(',', '_') 

        # validate oid
        self.validate()

    def __getattr__(self, name):
        return self.data[ self._uniqPrefix + name ]

    def __setattr__(self, name, value):
        if not self.__dict__.has_key('_attrExample__initialised'):
            return dict.__setattr__(self, name, value)
        elif self.__dict__.has_key(name):
           self.__setitem__(name, value)
        else:
           self.data[ self._uniqPrefix + name] = value
 
    def isKPI(self):
        return self.hasField('kpiName') or self.hasField('valueType')

    def isAppMessage(self):
        return self.hasField('testName') or self.hasField('appMessage')

    def fieldKey(self, name):
        return self._uniqPrefix + name

    def hasField(self, name):
        return self.data and self.data.has_key(self._uniqPrefix + name)
   
    def toFloat(self, name):
        if self.hasField(name):
            try:
                self.data[self._uniqPrefix + name] = float( self.data[self._uniqPrefix + name] )
            except:
                # could not convert to float so make it unkown
                self.data[self._uniqPrefix + name] = 'U'

    def deleteField(self, name):
        if self.hasField(name):
            del self.data[name]

    def validate(self):
        if len(self.validatorErrors) > 0: return 
        validator = BBCApplicationSNMPFormatTest()

        if self.isAppMessage():
            self.validatorErrors = validator.validateAppRecord( self.id,
                                                                self.subOid,
                                                                self.rawValue,
                                                                dict( zip ( [ x.replace(self._uniqPrefix,'',1) for x in self.data.keys() ], self.data.values() ) )
                                                                )
        elif self.isKPI():
            self.validatorErrors = validator.validateKpiRecord( self.id,
                                                                self.subOid,
                                                                self.rawValue,
                                                                dict( zip ( [x.replace(self._uniqPrefix,'',1) for x in self.data.keys()], self.data.values() ))
                                                                )
