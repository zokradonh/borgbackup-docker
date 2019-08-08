WIP
====

Backups all docker volumes while automatically detecting [mariadb](https://hub.docker.com/_/mariadb) data volumes
(targeting /var/lib/mysql) and using [mariabackup](https://mariadb.com/kb/en/library/mariabackup-options/) CLI with incremental functions.
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
      - BORG_REMOTE_URL=ssh://user@host:22/path/to/backups/ 
      - BORG_PASSPHRASE=<some-random-password>
      - BORG_RSH=ssh -oStrictHostKeyChecking=no
      - BORG_PRUNE_RULES=--keep-daily 14 --keep-monthly 10
```

You can see the host bind `backup_id_rsa`. This file should contain your private key for pubkey authentication to the borg backup
server via SSH, if using SSH. Furthermore you can mount a directory full of docker-compose git repositories (optional).
Those will be backuped too as git bundles.

You could also alter `docker-compose.yml` from repository and add all values from above instead of
creating `docker-compose.override.yml`.

Create and start the container by `docker-compose up -d`.
Initiate the borg backup repository by `docker-compose exec cronservice backup-init`.
As mentioned in the warning you should backup the volume `config` of your docker compose project, otherwise all backups are lost,
due to encryption.
The backups starts 2:59 AM daily.

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
backups | All the incremental database backups are saved in this volume. Must be persistent due to incremental nature.
config | Configuration of borg itself including encryption keys. You cannot upload this to your backup server if you do not trust it.
/hostprojects | (optional) Mount your directory that contains all the docker compose projects under git version control. E.g. /etc/compose:/hostprojects

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
BORG_REMOTE_URL | ssh://user@host:22/path/to/backups/ | Connection URL accepted by Borg
BORG_PASSPHRASE | random-string | Passphrase that encrypts the encryption keys which encrypt the backups.
BORG_RSH | ssh -oStrictHostKeyChecking=no | SSH invoke. You should provide example value to accept the ssh fingerprint, if using ssh:// remote URL
BORG_PRUNE_RULES | --keep-daily 14 --keep-monthly 10 | Borg prune rules. See Borg doc.
