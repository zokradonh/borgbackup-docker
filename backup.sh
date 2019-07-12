#!/bin/bash

. /borg_env.sh

set -eu

VOLUME_PATH="/hostvolumes"
BACKUPPATH="/backups"

function find_data_volume {
    containerName=$1

    docker inspect -f "{{json .Mounts }}" "$containerName" | jq -r '.[] | select(.Destination == "/var/lib/mysql") | .Name'
}

docker ps -a --no-trunc --format "{{ .ID }}" | xargs -i docker inspect {}  > /tmp/allcontainer
databaseContainers=$( jq -r '.[] | . as $c | .Config.Image | select(test("^mariadb:?")) | $c | .Id' < /tmp/allcontainer )
databaseVolumes=$( jq -r '.[] | . as $c | .Config.Image | select(test("^mariadb:?")) | $c | .Mounts[].Name' < /tmp/allcontainer )

echo "Found the following database volumes: $databaseVolumes"

ignoredVolumes=$( docker volume ls --format "{{ .Name }}" --filter=label=xyz.zok.borgbackup.ignore )

for vol in $( docker volume ls --format "{{ .Name }}")
do
    if [ -f "$VOLUME_PATH/$vol/.xyz.zok.borgbackup.ignore" ]
    then
        ignoredVolumes+=$'\n'
        ignoredVolumes+="$vol"
    fi
done

# get data volumes folders
foldersToBackup=$( comm -3 <(docker volume ls --format "{{ .Name }}") <(sort <(echo "$databaseVolumes") <(echo "$ignoredVolumes") | uniq) | awk '{print "'$VOLUME_PATH'/" $0}' | tr '\n' ' ' )

# dump databases
for container in $databaseContainers
do
    containerName=$( docker inspect --format "{{ .Name }}" "$container" )

    # get host path of datafiles volume
    dataVolume=$( find_data_volume "$container" )

    if [ -z "$dataVolume" ]
    then
        echo "ERROR: Database container $containerName has no volume mount to '/var/lib/mysql'!"
        continue
    fi

    if [ ! -d "$BACKUPPATH/$dataVolume" ]
    then
        # first backup of this database
        mkdir -p "$BACKUPPATH/$dataVolume/inc.0"
        echo "Create first full database backup of $containerName..."
        docker exec "$container" sh -c \
            "mariabackup --backup --stream=xbstream --user=root --"'password=$MYSQL_ROOT_PASSWORD' \
            | mbstream -x -C "$BACKUPPATH/$dataVolume/inc.0"
    else
        # incremental backup of this database
        # find last incremental backup if any
        last=$( find "$BACKUPPATH/$dataVolume" -name 'inc.*' -printf '%f\n' | sort -V | tail -1 | cut -d . -f 2 )
        next=$((last + 1))
        lastToLsn=$( grep to_lsn "$BACKUPPATH/$dataVolume/inc.$last/xtrabackup_checkpoints" | cut -d = -f 2 | tr -d "[:blank:]" )
        # create incremental backup
        mkdir -p "$BACKUPPATH/$dataVolume/inc.$next"
        echo "Create incremental database backup number $next of $containerName..."
        docker exec "$container" sh -c \
            "mariabackup --backup --incremental-lsn=$lastToLsn --stream=xbstream --user=root --"'password=$MYSQL_ROOT_PASSWORD' \
            | mbstream -x -C "$BACKUPPATH/$dataVolume/inc.$next"
    fi
    # append database backup to folders list
    foldersToBackup="$foldersToBackup $BACKUPPATH/$dataVolume"
done

echo "Found folders to backup: $foldersToBackup"

set -x
# upload backups
# shellcheck disable=SC2086
borg create --stats "${BORG_REMOTE_URL}::'{now}'" $foldersToBackup
# shellcheck disable=SC2086
borg prune -v --list $BORG_PRUNE_RULES "${BORG_REMOTE_URL}"
set +x
