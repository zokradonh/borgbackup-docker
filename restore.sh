#!/bin/bash

echo "Not implemented yet. Use borg commands via docker exec."

# TODO: reconstruct sql database by combining incremental data
# TODO: extract compose project
# TODO: extract volume


# ./restore.sh volume seafile_data [seafile_db [...]]
# ./restore.sh composeproject seafile
#? ./restore.sh database seafile_db

# mariabackup --prepare --target-dir=/pathtobasebackup --incremental-asdf --data-dir=/restoreDestination