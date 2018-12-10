#!/usr/bin/env python

import os, re, subprocess, time, sys
import signal

cmd = 'ssh -q -o StrictHostKeyChecking=no -i %s %s@%s "grep -h \'|\' /usr/local/var/snmp/data/1.3.6.1.4.1*"' %(sys.argv[2], sys.argv[3], sys.argv[4])
process = subprocess.Popen( cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )

class TimeoutException(Exception):
    pass

def timeoutHandler(signum, frame):
    raise TimeoutException

#./sshWrapper.py 10 /etc/sshkeys/snmpfetch_id_rsa snmpfetch pal007.back.int.cwwtf.local

if __name__ == '__main__':
    ret = stErr = None
    status = 0#success
    timeout = int(sys.argv[1])
    signal.signal(signal.SIGALRM, timeoutHandler)
    signal.alarm(timeout)
    try:
        ( output, stErr ) = process.communicate()
        ret = process.returncode
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
    except TimeoutException, e:
        status = 1 # timeout exception
        try:
            os.kill(process.pid, 9)
            raise TimeoutException
        except OSError, e:
            raise TimeoutException
            
    # did it fail ?
    if ret != 0:
        status = 2 #process exceptuon
    if status == 0:
        sys.stdout.write(output)
