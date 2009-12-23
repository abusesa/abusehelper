#!/bin/sh -x

myerr() {
 echo $* 1>&2
 exit 1
}
PORTSDIR=/usr/ports/security
PKG_DIR=/usr/ports/packages/i386/all/
export PKG_DIR
AH=abusehelper
AHPORTS=${PORTSDIR}/${AH}

rm -fr ${AHPORTS}
cp -r ${AH} ${PORTSDIR}/
cd ${AHPORTS}
make delete-package || myerr "Delete package failed." 
make makesum || myerr "Makesum failed."
make checksum || myerr "Checksum failed."
make plist || myerr "Creating plist failed."
make package || myerr "Creating package failed."
pkg_add abusehelper-r243
pkg_delete abusehelper-r243
userdel _abusehe; groupdel _abusehe


