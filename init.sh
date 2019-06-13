#!/bin/bash

set -eu

if [ ! -d "/borgconfig" ]
then
    echo "You need to mount directory /borgconfig as volume! It will be filled with borg config files and encryption keys."
    exit 1
fi

borg init --encryption=keyfile-blake2 "${BORG_REMOTE_URL}"


echo "####################################################"
echo "IMPORTANT: Backup the encryption keys by backing"
echo "up your volume that has been mounted to /borgconfig!"
echo "####################################################"