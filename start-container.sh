#!/bin/bash

# Run cron in daemon mode
cron

# Preserve environment variables for cron tasks
printenv | sed --regexp-extended 's/^([^=]*)=(.*)$/export \1="\2"/g' | grep -E "^export BORG" > /borg_env.sh
chmod a+x /borg_env.sh

# Redirect cron task output to stdout
exec tail -f /var/log/cron.fifo