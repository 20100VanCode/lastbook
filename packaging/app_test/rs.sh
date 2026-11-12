#!/bin/sh
# rs.sh start RUN DATA [extra] | py FILE [ENV=VAL ...] | a OP JSON  -- run a step on the Alienware through vw.py
PY='C:/Users/you/app-test/python-pkg/tools/python.exe'
VW='C:/Users/you/app-test/app-build/verify/vw.py'
c=$1; shift
case "$c" in
 start) r=$1; d=$2; shift 2; ssh win-test "$PY -I -B -X utf8 $VW start $r --deadline 14000 --memguard 24000 --data '$d' $*" ;;
 py) f=$1; shift; ssh win-test "env $* $PY -I -B -X utf8 $VW py" < "$f" ;;
 a) o=$1; shift; ssh win-test "$PY -I -B -X utf8 $VW a $o '$1'" ;;
esac
