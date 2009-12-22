#! /bin/sh
# abusehelperctl init wrapper.

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
ABUSEHELPER=/usr/bin/abusehelperctl
NAME=abusehelper
DESC=abusehelper

test -x $ABUSEHELPER || exit 0

ENABLED=""
if [ -f /etc/default/abusehelper ] ; then
	. /etc/default/abusehelper
fi

if [ "$ENABLED" = "1" ]; then
    :
else
    echo "$DESC: disabled, see /etc/default/abusehelper"
    exit 0
fi

set -e

case "$1" in
  start)
    echo -n "Starting $DESC: "
    $ABUSEHELPER start
    echo "done."
	;;
  stop)
    echo "Stopping $DESC: "
    $ABUSEHELPER stop
    echo "done."
	;;
  restart|force-reload)
    echo -n "Restarting $DESC: "
    $ABUSEHELPER restart
    echo "done."
    ;;
  status)
    $ABUSEHELPER status
    ;;
  *)
	N=/etc/init.d/$NAME
	echo "Usage: $N {start|stop|restart|force-reload}" >&2
	exit 1
	;;
esac

exit 0
