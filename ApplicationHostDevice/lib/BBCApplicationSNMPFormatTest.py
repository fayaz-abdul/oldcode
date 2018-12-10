#!/usr/bin/env python

__doc__="""
This class consists of metods for the BBCApplication zenpack data format validation.
"""
import re

class BBCApplicationSNMPFormatTest:

    # Application - all keys
    allAppValues = ('appName', 'appMessage', 'value', 'testName', 'eventSubClass', 'appMessage', 'url', 'ttl')

    # Application - mandatory keys
    mandatoryAppValues = ('appName', 'appMessage', 'value', 'testName')

    # Application - string keys
    stringAppValues = ('appName', 'appMessage', 'testName', 'eventSubClass', 'appMessage', 'url')

    # Application - epoch time stamp keys
    epochTimeStampAppValues = ('ttl')

    # KPI - all keys
    allKPIValues = ('appName', 'value', 'kpiName', 'valueType', 'url', 'eventSubClass', 'minThreshD','maxThreshD',
                    'minThreshI','maxThreshI','minThreshW', 'maxThreshW','minThreshE','maxThreshE', 'minThreshC',
                    'maxThreshC', 'yTitle', 'ttl')

    # KPI - mandatory keys
    mandatoryKPIValues = ('appName', 'value', 'kpiName')

    # KPI - string values
    stringKPIValues = ('appName', 'kpiName', 'valueType', 'url', 'eventSubClass', 'yTitle')

    # KPI - number values (int, float, UNKNOWN)
    numberKPIValues = ('value', 'minThreshD','maxThreshD','minThreshI','maxThreshI','minThreshW', 'maxThreshW','minThreshE','maxThreshE' ,'minThreshC', 'maxThreshC', 'ttl')

    # KPI - epoch time stamp keys
    epochTimeStampKPIValues = ('ttl')

    def __init__(self):

        # if these are empty everything is fine :)
        self.output = []
        self.appValidationOutput = []
        self.kpiValidationOutput = []

    def validateAppRecord( self, originalOid, subOid, originalLine, parsedLine ):

        self.appValidationOutput = []

        # TEST-1: test mandatory values
        self.appValidationOutput += self.madatoryValuesTest(
            originalLine,
            originalOid,
            parsedLine,
            "Application",
            BBCApplicationSNMPFormatTest.mandatoryAppValues
        )

        if not self.appValidationOutput:

            # TEST-2: application value test
            self.appValidationOutput += self.severityAppTest( originalLine, originalOid, parsedLine )
            if not self.appValidationOutput:

                # TEST-3: max lenght of application name is 250
                #validationErrorOutput += self.validator.string250Test(value, oid, subOid, line['appName'] +  subOid, 'appName')
                self.appValidationOutput += self.string250Test( originalLine, originalOid, subOid, parsedLine['appName'], 'appName')
                if not self.appValidationOutput:

                    # TEST-4: test for allowed app oids range '.xxxxx.75025.<1-50>'
                    self.appValidationOutput += self.oidAppRangeTest( originalLine, originalOid, subOid )
                    if not self.appValidationOutput:

                        # TEST-5: epoch time stamp
                        self.appValidationOutput += self.unixEpochTimeStampTest(
                            originalLine,
                            originalOid,
                            parsedLine,
                            "APP",
                            BBCApplicationSNMPFormatTest.epochTimeStampAppValues
                        ) 
 
        return self.appValidationOutput

    def validateKpiRecord ( self, originalOid, subOid, originalLine, parsedLine ):

        self.kpiValidationOutput = []

        # TEST-1: test mandatory values
        self.kpiValidationOutput += self.madatoryValuesTest(
            originalLine,
            originalOid,
            parsedLine,
            "KPI",
            BBCApplicationSNMPFormatTest.mandatoryKPIValues
        )

        if not self.kpiValidationOutput:

            # TEST-2: test kpi value type
            self.kpiValidationOutput += self.valueTypeKpiTest( originalLine, originalOid, parsedLine )
            if not self.kpiValidationOutput:

                # TEST-3: number values test (float || UNKNOWN)
                self.kpiValidationOutput += self.numberValuesTest( 
                    originalLine,
                    originalOid,
                    parsedLine,
                    "KPI",
                    BBCApplicationSNMPFormatTest.numberKPIValues
                )

                if not self.kpiValidationOutput:

                    # TEST-4: max lenght of kpi name is 250
                    #self.kpiValidationOutput += self.string250Test(originalLine, originalOid, subOid, line['appName'] + '__' + line['kpiName'] +  subOid, 'kpiName')
                    self.kpiValidationOutput += self.string250Test( originalLine, originalOid, subOid, parsedLine['kpiName'], 'kpiName' )
                    if not self.kpiValidationOutput:

                        # TEST-5: epoch time stamp
                        self.kpiValidationOutput += self.unixEpochTimeStampTest(
                            originalLine,
                            originalOid,
                            parsedLine,
                            "KPI",
                            BBCApplicationSNMPFormatTest.epochTimeStampKPIValues
                        )

        return self.kpiValidationOutput
            
    def madatoryValuesTest(self, originalLine, oid, line, type, mandatoryValues):

        self.output = []
        missing = []
        for value in mandatoryValues:
            if not line.has_key(value): missing.append(value)

        if  len(missing) != 0:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("Missing obligatory key/keys:%s in %s record") % (', '.join(missing), type) ))

        return self.output

    def numberValuesTest(self, originalLine, oid, line, type, numberValues):

        self.output = []
        missing = []
        for value in numberValues:
            if line.has_key(value) and line[value].upper() != 'UNKNOWN':
                try:
                    oidValue = float(line[value])
                    if oidValue in [float('inf'), float('nan')]:
                        raise ValueError
                except Exception, e:
                    missing.append('value=' + line[value])
                    continue 

        if  len(missing) != 0:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("Value/values:%s in %s record are not number/numbers") % (', '.join(missing), type) ))

        return self.output


    def  unixEpochTimeStampTest(self, originalLine, oid, line, type, epochValues):

        self.output = []
        missing = []

        for value in epochValues:
            if line.has_key(value):
                try:
                    float(line[value])
                except Exception, e:
                    missing.append('value=' + line[value])
                    continue

        if  len(missing) != 0:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("Value/values:%s in %s record are not unix epoch timestamp/timestumps") % (', '.join(missing), type) ))

        return self.output

    def severityAppTest(self, originalLine, oid, line):

        self.output = []

        if  line.has_key('value'):
      
            # integer test
            try:
               int(line['value'])
            except Exception, e:
               self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
               self.output.append(str( ("Application value=%s is not an integer in range <0-5>") % (line['value']) ))
               return self.output
            
            # range test
            if not (int(line['value']) >= 0 and int(line['value']) <= 5):
               self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
               self.output.append(str( ("Application value=%s is not an integer in range <0-5>") % (line['value']) ))

        else:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("Missing obligatory key value in application record") ))

        return self.output

    def string250Test(self, originalLine, oid, subOid, stringValue, stringName ):
        
        self.output = []

        if len(stringValue) > 150:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("%s can be max 150 characters long. Actual %s=%s actualLenght:%s") % (stringName, stringName, stringValue, str(len(stringValue)) ) ))

        return self.output

    def oidAppRangeTest(self, originalLine, oid, subOid):

        self.output = []

        # expecting sth. like '.xxxxx.75025.<1-50>'
        compile = re.compile(r"^\.(?P<oid_0>\d+)\.(?P<oid_1>\d+)\.(?P<oid_2>\d+)$")
        match = compile.match(subOid)
        newoidspace = False
        #do a check for new oid space ie ., '.xxxxx.75025.500.<1-50>'
        if not match:
            compile = re.compile(r"^\.(?P<oid_0>\d+)\.(?P<oid_1>\d+)\.(?P<oid_2>\d+)\.(?P<oid_3>\d+)$")
            match = compile.match(subOid)
            newoidspace = True

        if match:
            if newoidspace:
                if not (int(match.group('oid_1')) == 75025 and int(match.group('oid_2')) == 500 and int(match.group('oid_3')) >0 and int(match.group('oid_3')) <= 50):
                    self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
                    self.output.append(str( ("%s is not allowed application oid") % (subOid) ))

            else:
                if not (int(match.group('oid_1')) == 75025 and int(match.group('oid_2')) >0 and int(match.group('oid_2')) <= 50):
                    self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
                    self.output.append(str( ("%s is not allowed application oid") % (subOid) ))
        else:
            self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
            self.output.append(str( ("%s is not allowed application oid") % (subOid) ))
            
        return self.output

    def valueTypeKpiTest(self, originalLine, oid, line):

        self.output = []
        allowed = ['COUNTER', 'DERIVE', 'GAUGE', 'ABSOLUTE']

        if  line.has_key('valueType'):
      
            # test allowed
            if  not ( line['valueType'].upper() in allowed ):
               self.output.append(str( ("OID:%s -> %s") % (oid, originalLine) ))
               self.output.append(str( ("Kpi valueType=%s is not allowed. Expecting %s") % (line['valueType'],' or '.join(allowed)) ))

        return self.output
