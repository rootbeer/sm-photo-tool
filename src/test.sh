#!/bin/bash
#
# test sm_photo_tool.py
#

# This mostly tests error cases, since normal usage should exercise
# the 'correct' code paths.

# Used by pychecker, too
export PYTHONVER=2.5

SRCDIR=$(readlink -f $(dirname $0))
PYTHON=${PYTHON:-"python${PYTHONVER}"}
SMTOOL=${SMTOOL:-"${SRCDIR}/sm_photo_tool.py"}
TMPDIR="/tmp/smtooltest"

tct=0

# t <rc> [<options>]
# Expect test to return given RC when run with given OPTIONS
t() {
    LOG="${TMPDIR}/phototool.out"
    tct=$(( $tct + 1 ))

    expected="$1"
    shift

    echo -n "Testing sm_photo_tool.py $* ... "
    $PYTHON $SMTOOL "$@" > "$LOG" 2>&1
    rc=$?
    if [ "$rc" != "$expected" ]; then
	echo "FAILED. Returned $rc, expected $expected."
	cat "$LOG" | sed -e 's/^/ > /'
	exit 1
    else
	echo -n "passed"
	if [ "$rc" == 1 ]; then
	    echo -n " (Exception!)"
	elif [ "$rc" != 0 ]; then
	    echo -n " (error as expected)"
	fi
	echo ""
    fi
}

header() {
    echo ""
    echo "=== $* ==="
}


###
### Main -- actual tests
###

# XXX finds too much crap in optparse and xmlrpclib ...
#exec pychecker --limit 100 ${SRCDIR}/*.py

mkdir -p "${TMPDIR}"
cd "${TMPDIR}"

echo "XXX assumes .smphototool config file is working correctly."
echo "XXX assumes a working network connection."

header "help"
t  0
t  0 help
t  0 --help
t  0 -help
t  0 -h

header "invalid"
t 37 invalid
t 37 --invalid

header "list"
t 13 list
t 15 list invalid
t  2 list --invalid
t  0 list galleries
t  2 list --invalid galleries
t 14 list album
t  1 list album invalid-gallery-id # XXX ugly exception
t  1 list album 1234567_xxxxx # XXX ugly exception

t  0 list album 1258828 

t  1 list --login=NotAValidLogin album 1258828  # XXX ugly exception
t  1 list --password=BestBeIncorrectPassword album 1258828  # XXX ugly exception

header "create"
# XXX 'create' is hard to test...  We could create galleries with
# random names, but we might piss off smugmug?
t  0 create --help
t 87 create
t  2 create --invalid

header "update"
t  0 update --help
t  2 update --invalid
t 47 update # no existing gallery in directory, so does nothing

header "full_update"
t  0 full_update --help
t  2 full_update --invalid
t  2 full_update --invalid
# XXX full_update is also hard to test ...

header "upload"
t  0 upload --help
t  2 upload --invalid
t 31 upload invalid-and-no-files
t  0 upload invalid /dev/null        # XXX probably shouldn't succeed?
t  0 upload invalid /does/not/exist  # XXX probably shouldn't succeed?
t  0 upload invalid DoesNotExist     # XXX probably shouldn't succeed?

echo "All $tct tests passed!"

rm -rf "${TMPDIR}"

#eof
