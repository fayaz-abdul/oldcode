#!/usr/bin/env python

__doc__="""
This is a test for SNMP proxy and device behind the proxy.
SNMP v3 protocol is expected.
"""

import Globals
import sys
import os
import ConfigParser
import commands

class SnmpProxyTest:

    def zProperties_test( self, optionsHash ):
        """ Test availibily of device SNMP zProperties """

        # test properties        
        properties = [ 'zSnmpAuthPassword', 'zSnmpPrivPassword', 'zSnmpProxy', 'zSnmpSecurityName', 'zSnmpAuthType', 'zSnmpPrivType', 'zSnmpProxyContextName', 'zSnmpVer' ]

        for property in properties:
        
            if optionsHash.has_key( property ) and optionsHash[ property ]:

                if property == 'zSnmpVer' and not optionsHash[ 'zSnmpVer' ] in ['3','v3']:
                    print "zSnmpVer has to be version 3"
                    return False

            else:
                print "%s is not defined" % property
                return False

        return True

    def get_proxy_system ( self, optionsHash ):
        """ Get system data information from a SNMP proxy """

        cmd = "snmpwalk -Onq -r 2 -t 5 -v 3 -u %s -l authPriv -a %s -A %s -x %s -X %s %s %s" % (
                optionsHash [ 'zSnmpSecurityName' ],
                optionsHash [ 'zSnmpAuthType' ],
                optionsHash [ 'zSnmpAuthPassword' ],
                optionsHash [ 'zSnmpPrivType' ],
                optionsHash [ 'zSnmpPrivPassword' ],
                optionsHash [ 'zSnmpProxy' ],
                'system' ) 

        return self.run_command(cmd)

    def get_device_oids( self, oid, optionsHash ):
        """ Get specified SNMP OID/OIDs from device """

        cmd = "snmpwalk -Onq -r 2 -t 5 -v 3 -u %s -l authPriv -a %s -A %s -x %s -X %s -n %s %s %s" % (
                optionsHash [ 'zSnmpSecurityName' ],
                optionsHash [ 'zSnmpAuthType' ],
                optionsHash [ 'zSnmpAuthPassword' ],
                optionsHash [ 'zSnmpPrivType' ],
                optionsHash [ 'zSnmpPrivPassword' ],
                optionsHash [ 'zSnmpProxyContextName' ],
                optionsHash [ 'zSnmpProxy' ],
                oid )

        return self.run_command(cmd)

    def run_command(self, cmd):
        """ Run a command string """

        output = None
        status = 0

        try:
            (status, output) = commands.getstatusoutput(cmd)
        except Exception, e:
            print "Runnig of command failed: %s" % e

        return (status, output)

def parseOptions():
    """ To parse command line opptions """

    from optparse import OptionParser
    argError = []
    optParser = OptionParser()

    # Device and SNMP parameters
    optParser.add_option('--hostName', dest="hostName", help="device host name")
    optParser.add_option('--snmpCommunity', dest="zSnmpCommunity", help="SNMP community")
    optParser.add_option('--snmpProxy', dest="zSnmpProxy", help="SNMP proxy")
    optParser.add_option('--snmpProxyContextName', dest="zSnmpProxyContextName", help="SNMP proxy context name")
    optParser.add_option('--snmpVersion', dest="zSnmpVer", help="SNMP version (1 || v1) ||  (2 || 2c || v2c) || (3 || v3)")
    optParser.add_option('--snmpSecurityName', dest="zSnmpSecurityName", help="SNMP security name")
    optParser.add_option('--snmpAuthType', dest="zSnmpAuthType", help="SNMP auth type ( MD5 || SHA )")
    optParser.add_option('--snmpPrivType', dest="zSnmpPrivType", help="SNMP priv type ( DES || AES ) ")
    optParser.add_option('--snmpAuthPassword', dest="zSnmpAuthPassword", help="SNMP auth password")
    optParser.add_option('--snmpPrivPassword', dest="zSnmpPrivPassword", help="SNMP priv password")
    optParser.add_option('--hideCommandOnZenossUI', dest="hideCommandOnZenossUI", default=True, help="This is here just to fool zenoss UI, so it does not show passwords above") # !!! do not delete this line, patch in core is looking for this

    (options, args) = optParser.parse_args()
    optionsHash = {}

    if options.hostName:
        optionsHash [ "hostName" ] = options.hostName
    if options.zSnmpCommunity:
        optionsHash [ "zSnmpCommunity" ] = options.zSnmpCommunity
    if options.zSnmpProxyContextName:
        optionsHash [ "zSnmpProxyContextName" ] = options.zSnmpProxyContextName
    if options.zSnmpVer:
        optionsHash [ "zSnmpVer" ] = options.zSnmpVer
    if options.zSnmpSecurityName:
        optionsHash [ "zSnmpSecurityName" ] = options.zSnmpSecurityName
    if options.zSnmpProxy:
        optionsHash [ "zSnmpProxy" ] = options.zSnmpProxy
    if options.zSnmpAuthType:
        optionsHash [ "zSnmpAuthType" ] = options.zSnmpAuthType
    if options.zSnmpPrivType:
        optionsHash [ "zSnmpPrivType" ] = options.zSnmpPrivType
    if options.zSnmpAuthPassword:
        optionsHash [ "zSnmpAuthPassword" ] = options.zSnmpAuthPassword
    if options.zSnmpPrivPassword:
        optionsHash [ "zSnmpPrivPassword" ] = options.zSnmpPrivPassword

    # Minimal required arguments
    if not options.hostName:
        argError.append('hostName')

    # sth. missing
    if argError:
        for required in argError:
            print "Parameter %s is required." % (required)
        sys.exit(-1)

    return(options,optionsHash)

def print_test_report(status_output):
        """ To print status & output of the test. Expecting tuple ( status, output ) """

        if status_output[0] > 0:
            print "Result [%s] command return code [%s]\n" % ('FALIED', status_output[0])
        else:
            print "Result [%s] command return Code [%s]\n" % ('OK', status_output[0])

        print "Command output:\n%s" % status_output[1]

# main code
if __name__ == "__main__":

    BASE_BBC_OID = "1.3.6.1.4.1.2333.3.2"

    # read args
    options, optionsHash = parseOptions()

    # build SnmpProxyTest object
    test = SnmpProxyTest()

    # TESTS
    print "Tests preparation: loading %s SNMP zProperties" % options.hostName

    if not test.zProperties_test( optionsHash ):
        print "Device %s is not configured for usage through SNMP proxy" % options.hostName
        sys.exit(-1)

    else: 
        # proxy test
        status = 0
        output = None

        print "\n======= Beginning - Test 1 ======="
        print "SNMP Proxy Test -> Running snmpwalk against the proxy itself (%s). Asking for system data.\n" % optionsHash [ 'zSnmpProxy' ]
        print_test_report ( test.get_proxy_system( optionsHash ) )
        print "========== End - Test 1 ==========\n"

        # device system test
        print "======= Beginning - Test 2 ======="
        print "SNMP Device Test -> Running snmpwalk against device (%s) through the proxy (%s). Asking for system data.\n" % ( optionsHash [ 'hostName' ], optionsHash [ 'zSnmpProxy' ] )
        print_test_report ( test.get_device_oids( 'system', optionsHash ) )
        print "========== End - Test 2 ==========\n"

        # device BBC OID test
        print "======= Beginning - Test 3 ======="
        print "SNMP Device BBC OID Test -> Running snmpwalk against device (%s) through the proxy (%s). Asking for all data under BBC OID tree. BBC OID tree is %s \n" % ( optionsHash [ 'hostName' ], optionsHash [ 'zSnmpProxy' ], BASE_BBC_OID)
        print_test_report ( test.get_device_oids( BASE_BBC_OID, optionsHash ) )
        print "========== End - Test 3 ==========\n"

        sys.exit(0)
