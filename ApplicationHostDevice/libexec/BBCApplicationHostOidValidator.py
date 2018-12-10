#!/usr/bin/env python

__doc__="""
This test was written to check the format of SNMP data produced by application developers on specific device.
The data format has to be compatibile with BBCApllication zenoss pack which is responsible for processing this
data on the zenoss side at the end.
"""
import Globals
import time
import sys
import re
import os
import ConfigParser

# This is very nasty bit for adding libraries which are in ../lib/ directory relative to the real path of this script.
# It fixes trables with symbolic links pointing to this script
actualScriptPath = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(actualScriptPath + '/../lib')

#print "Actual script directory:",actualScriptPath

from BBCApplicationSNMPFormatTest import BBCApplicationSNMPFormatTest

class BBCApplicationHostOidValidator:

    # global definitions
    snmpTime = 0
    oidsProcessingTime = 0

    # total oid counter (everything in snmpwalk)
    totalOidConter = 0

    # amount of BBC oids overall
    oidCounter = 0

    # amount of broken application BBC oids overall
    brokenAppOidCounter = 0

    # amount of broken KPI BBC oids overall
    brokenKpiOidCounter = 0

    def getOIDs(self, hostName = "", zSnmpVer = None, zSnmpCommunity = None, zSnmpProxy = None , zSnmpProxyContextName = None, 
                 oid = None, retries = None, timeout = None, zSnmpSecurityName = None , zSnmpAuthType = None,
                 zSnmpPrivType = None, zSnmpAuthPassword = None, zSnmpPrivPassword = None):

        """ Snmpwalk to get all device OIDs"""

        import subprocess

        cmd = ''
        snmpStartTime = time.time()

        zSnmpVer = zSnmpVer
        zSnmpCommunity = zSnmpCommunity
        retries = retries
        timeout = timeout
        zSnmpProxy = zSnmpProxy
        zSnmpProxyContextName = zSnmpProxyContextName

        if zSnmpVer in ['3','v3']:
            if zSnmpProxy and zSnmpProxyContextName:

                # snmp v3 - through proxy
                cmd = "snmpwalk -Onq -r %s -t %s -v %s -u %s -l authPriv -a %s -A %s -x %s -X %s -n %s %s %s" % (
                retries,
                timeout,
                '3',
                zSnmpSecurityName,
                zSnmpAuthType,
                zSnmpAuthPassword,
                zSnmpPrivType,
                zSnmpPrivPassword,
                zSnmpProxyContextName,
                zSnmpProxy,
                oid )
        
            else:

            # snmp v3 - no snmp proxy
                cmd = "snmpwalk -Onq -r %s -t %s -v %s -u %s -l authPriv -a %s -A %s -x %s -X %s %s %s" % (
                retries,
                timeout,
                '3',
                zSnmpSecurityName,
                zSnmpAuthType,
                zSnmpAuthPassword,
                zSnmpPrivType,
                zSnmpPrivPassword,
                hostName,
                oid )
        else:

            # snmp v2 and v1
            if zSnmpVer in ['2','2c','v2c']:
                cmd = "snmpwalk -Onq -r%s -t%s -v %s -c%s %s %s" % (retries, timeout, '2c', zSnmpCommunity, hostName, oid)

            # snmp v2 and v1
            if zSnmpVer in ['1','v1']:
                cmd = "snmpwalk -Onq -r%s -t%s -v %s -c%s %s %s" % (retries, timeout, '1', zSnmpCommunity, hostName, oid)

        # run snmpwalk command
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (stdOut, stdErr) = process.communicate()
            returnCode = process.returncode

        except Exception, e:
            print "Snmpwalk failed for host %s: \n%s" % (hostName, e)
            sys.exit(-1)

        if returnCode != 0:
            print "Snmpwalk failed for host %s: \n%s" % (hostName, stdErr)
            sys.exit(-1)

        self.snmpTime = time.time() - snmpStartTime

        return stdOut

    def processOIDs( self, OIDs, dataOID, onlyAppName ):
        """ To check if OID data has a proper format (Application Record  & KPI Record). """

        # create validator class
        validator = BBCApplicationSNMPFormatTest()

        for row in OIDs.split('\n'):

            self.totalOidConter += 1

            # print "Row:" + row;
            # do not process empty line
            if len(row) != 0:

                # get oid and value
                oid, value = row.split(' ',1)
                value = value.strip('"')

                # jump lines in format (integer|gauge|counter|timeticks|ipaddress|objectid)
                try:
                   float(value)
                   continue
                except Exception, e:
                   pass
                
                # parse oid value into pairs, so it is not any string type
                pairs = value.split('|')

                # there are minimaly two keys
                if len(pairs) > 2:

                    # get rid of base OID ( ie keep  44.1.2 out of .1.3.6.1.4.1.2333.3.2.44.1.2)
                    subOid = oid.replace(dataOID,'')

                    # parse pairs into key/value
                    line = {} 
                    for pair in pairs:
                        pair = pair.split('=', 1)
                        if len(pair) == 2:
                            line[pair[0]] = pair[1]

                    # process only lines where application name is "onlyAppName"
                    if onlyAppName and onlyAppName != line['appName']:
                        continue

                    if line.has_key('testName') or line.has_key('appMessage'):

                        self.oidCounter += 1

                        # App - validation test                                                    
                        output = validator.validateAppRecord ( oid, subOid, value, line )
 
                        # print test output
                        if output: 
                            self.brokenAppOidCounter += 1

                            for error in output:
                                print error
       
                            print"******"

                    elif line.has_key('kpiName') or line.has_key('valueType'):

                        self.oidCounter += 1

                        # KPI - validation test
                        output = validator.validateKpiRecord ( oid, subOid, value, line )

                        # print test output
                        if output: 
                            self.brokenKpiOidCounter += 1

                            for error in output:
                                print error
       
                            print "******"

def parseOptions():
    """To parse command line opptions."""

    from optparse import OptionParser
    argError = []
    optParser = OptionParser()

    # Device and SNMP parameters
    optParser.add_option('--appName', dest="appName", help="Application name to test (if not specified all applications validated)")
    optParser.add_option('--hostName', dest="hostName", help="Device host name")
    optParser.add_option('--snmpCommunity', dest="zSnmpCommunity", help="SNMP community")
    optParser.add_option('--snmpProxy', dest="zSnmpProxy", help="SNMP proxy")
    optParser.add_option('--snmpProxyContextName', dest="zSnmpProxyContextName", help="SNMP proxy context name")
    optParser.add_option('--snmpVersion', dest="zSnmpVer", help="SNMP version (1 || v1) ||  (2 || 2c || v2c) || (3 || v3)")
    optParser.add_option('--snmpSecurityName', dest="zSnmpSecurityName", help="SNMP security name")
    optParser.add_option('--snmpAuthType', dest="zSnmpAuthType", help="SNMP auth type ( MD5 || SHA )")
    optParser.add_option('--snmpPrivType', dest="zSnmpPrivType", help="SNMP priv type ( DES || AES ) ")
    optParser.add_option('--snmpAuthPassword', dest="zSnmpAuthPassword", help="SNMP auth password")
    optParser.add_option('--snmpPrivPassword', dest="zSnmpPrivPassword", help="SNMP priv password")
    optParser.add_option('--dataOID', default=".1.3.6.1.4.1.2333.3.2", dest="dataOID", help="SNMP base data OID (default .1.3.6.1.4.1.2333.3.2)")
    optParser.add_option('--timeOut', default="2", dest="timeOut", help="SNMP timeout (default 2 seconds)")
    optParser.add_option('--retries', default="2", dest="retries", help="SNMP retries (default 2 retries)")
    optParser.add_option('--hideCommandOnZenossUI', dest="hideCommandOnZenossUI", default=True, help="This is here just to fool zenoss UI, so it does not show passwords above") # !!! do not delete this line, patch in core is looking for this

    (options, args) = optParser.parse_args()

    # Minimal required arguments
    if not options.hostName:
        argError.append('hostName')

    if not options.dataOID:
        argError.append('dataOID')

    if argError:
        for required in argError:
            print "Parameter %s is required." % (required)
        sys.exit(-1)

    return(options)

# main code
if __name__ == "__main__":

    startTime = time.time()

    # read args
    options = parseOptions()

    # build BBCAppCollector object
    validator = BBCApplicationHostOidValidator()

    # get OIDs
    OIDs = validator.getOIDs( options.hostName, options.zSnmpVer, options.zSnmpCommunity, options.zSnmpProxy, options.zSnmpProxyContextName,
                    options.dataOID, options.retries, options.timeOut, options.zSnmpSecurityName, options.zSnmpAuthType, options.zSnmpPrivType,
                    options.zSnmpAuthPassword, options.zSnmpPrivPassword)

    # process OIDs
    oidsStartTime = time.time()
    validator.processOIDs( OIDs, options.dataOID, options.appName )
    oidsProcessingTime = time.time() - oidsStartTime

    runTime = time.time() - startTime

    print "STATS: totalTime=%s snmpWalkTime=%s oidsProcessingTime=%s totalOidCounter=%s testedOidCounter=%s brokenAppOidCounter=%s brokenKpiOidCounter=%s" % (runTime, validator.snmpTime, oidsProcessingTime, validator.totalOidConter, validator.oidCounter, validator.brokenAppOidCounter, validator.brokenKpiOidCounter)
    sys.exit(0)
