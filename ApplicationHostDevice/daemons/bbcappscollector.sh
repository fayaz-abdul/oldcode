#! /usr/bin/env bash

. $ZENHOME/bin/zenfunctions

MYPATH=`python -c "import os.path; print os.path.realpath('$0')"`
THISDIR=`dirname $MYPATH`
PRGHOME=`dirname $THISDIR`
PRGNAME=bbcappscollector.py
CFGFILE=$CFGDIR/bbcappscollector.conf

generic "$@"

