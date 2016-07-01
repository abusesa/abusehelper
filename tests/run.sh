#!/bin/sh

docker-compose up
docker-compose logs | egrep "FAIL|Error" && FAILURE=yes
docker-compose rm -fva

if [ "blah${FAILURE}" = "blahyes" ]; then
    exit 1
fi
