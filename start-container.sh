#!/bin/bash

# Run cron in daemon mode
cron

# Preserve environment variables for cron tasks
jq -n env > borg_parameters.json

# create project git repo export dir
mkdir -p /bundles

# write fingerprint
echo $SSH_HOST_FINGERPRINT > /root/.ssh/known_hosts

# Redirect cron task output to stdout
exec tail -f /var/log/cron.fifo