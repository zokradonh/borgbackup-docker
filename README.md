WIP
====

Backups all docker volumes while automatically detecting [mariadb](https://hub.docker.com/_/mariadb) data volumes
(targeting /var/lib/mysql) and using [mariabackup](https://mariadb.com/kb/en/library/mariabackup-options/) CLI with incremental functions.
Also backs up all compose projects if they are under git version control with `git bundle`.
This image uses [Borg](https://www.borgbackup.org/) to backup plain data volumes and mariabackup exports. A Borg backup server is
required.

Usage
===
Copy `docker-compose.yml` from repository and create `docker-compose.override.yml`:
```
version: '3'

services:
  cronservice:
    volumes:
      - /root/.ssh/backup_id_rsa:/root/.ssh/id_rsa
      - /etc/compose:/hostprojects
    environment:
      - TZ=Europe/Berlin
      - BORG_REPO=ssh://user@example.net:22/path/to/backups/ 
      - BORG_PASSPHRASE=<some-random-password>
      - BORG_PRUNE_RULES=--keep-daily 14 --keep-monthly 10
      - SSH_HOST_FINGERPRINT=[example.net]:22 ssh-ed25519 ABCDEFGHIJKLMNOPQRSTUVWXYZ
      - CRON_INTERVAL_INCREMENTAL=59 2 * * *
```

The host binds `backup_id_rsa`. This file should contain your private key for pubkey authentication to the borg backup
server via SSH, if using SSH. Furthermore you can mount a directory full of docker-compose git repositories (optional).
Those will be backuped too as git bundles.

You could also alter `docker-compose.yml` from repository and add all values from above instead of
creating `docker-compose.override.yml`.
SSH_HOST_FINGERPRINT should contain a line in the same format as in `.ssh/known_hosts`.

Create and start the container by `docker-compose up -d`.
Initiate the borg backup repository by `docker-compose exec cronservice backup-init`.
As mentioned in the warning you should backup the volume `config` of your docker compose project, otherwise all backups are lost,
due to encryption.
In default settings backups start at 2:59 AM daily. You can adjust with environment variable `CRON_INTERVAL_INCREMENTAL`.

How to exclude a volume from backup
====
Either set the a label `xyz.zok.borgbackup.ignore` for the volume (which is not possible if the volume is already created) or 
create an empty file called `.xyz.zok.borgbackup.ignore` in the parent directory of the volume.
```
/var/lib/docker/volumes/
  -- my_volume_to_ignore/
  ---- _data/
  ------ <all the data of the volume>
  ---- .xyz.zok.borgbackup.ignore
```

Volumes of this image
====
Volume | Description
--- | ---
backups | All incremental database backups are saved in this volume. Must be persistent due to incremental nature.
config | Configuration of borg itself including encryption keys. You cannot upload this to your backup server if you do not trust it. Save this somewhere else.
/hostprojects | (optional) Mount this to the directory that contains all the docker compose projects under git version control. E.g. /etc/compose:/hostprojects

Volume Labels
====

LabelName | Description
--- | ---
xyz.zok.borgbackup.ignore | This volume will not be included in any backup
xyz.zok.borgbackup.whitelist | This volume will be backed up if the Borg backup container is in whitelist-only mode (not implemented)


Environment Variables
====

EnvVar | Example | Description
--- | --- | ---
BORG_REPO | ssh://user@host:22/path/to/backups/ | (Original Borg variable) Connection URL accepted by Borg. ([Doc](https://borgbackup.readthedocs.io/en/stable/usage/general.html#repository-urls))
BORG_PASSPHRASE | random-string | (Original Borg variable) Passphrase that encrypts the encryption keys which encrypt the backups.
BORG_PRUNE_RULES | --keep-daily 14 --keep-monthly 10 | Borg prune rules. See `borg prune` [arguments](https://borgbackup.readthedocs.io/en/stable/usage/prune.html).
SSH_HOST_FINGERPRINT | [example.net]:22 pubkey | Format of `.ssh/known_hosts`.
CRON_INTERVAL_INCREMENTAL | 00 2 * * * | Interval format of [crontab](https://help.ubuntu.com/community/CronHowto)
TZ | Europe/Berlin | Your [time zone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

Every environment variable starting with `BORG_` will be passed to the Borg process.