#!/bin/sh -x

myerr() {
 echo $* 1>&2
 exit 1
}
PORTSDIR=/usr/ports/security
PKG_PATH=/usr/ports/packages/i386/all/
export PKG_PATH
AH=abusehelper
AHPORTS=${PORTSDIR}/${AH}

revision=$(svn info|grep Revision|cut -d" " -f2)
version=1.r${revision}

mydir=$(dirname $0)

makefile=${mydir}/abusehelper/Makefile 

[ -f ${makefile}.in ] || myerr "Can not find ${makefile}.in"

cat ${makefile}.in | sed -e "s/REPLACEVERSIONNUMBER/${version}/g" > ${makefile} 


pkg_delete abusehelper
echo 'Running userdel & groupdel'
userdel _abusehe; groupdel _abusehe
rm -fr ${AHPORTS}
cp -r ${AH} ${PORTSDIR}/
cd ${AHPORTS}
make delete-package || myerr "Delete package failed." 
make makesum || myerr "Makesum failed."
make checksum || myerr "Checksum failed."
make plist || myerr "Creating plist failed."
make package || myerr "Creating package failed."
pkg_add abusehelper-${version}



