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
    environment:
      - BORG_REMOTE_URL=ssh://user@host:22/path/to/backups/ 
      - BORG_PASSPHRASE=<some-random-password>
      - BORG_RSH=ssh -oStrictHostKeyChecking=no
      - BORG_PRUNE_RULES=--keep-daily 14 --keep-monthly 10
```

You can see the host bind `backup_id_rsa`. This file should contain your private key for pubkey authentication to the borg backup
server via SSH, if using SSH.

You could also alter `docker-compose.yml` from repository and add all values from above instead of
creating `docker-compose.override.yml`.

Create and start the container by `docker-compose up -d`.
Initiate the borg backup repository by `docker-compose exec cronservice backup-init`.
As mentioned in the warning you should backup the volume `config` of your docker compose project, otherwise all backups are lost,
due to encryption.
The backups starts 2:59 AM daily.

Volume Labels
====

LabelName | Description
--- | --- | ---
xyz.zok.borgbackup.ignore | This volume will not be included in any backup
xyz.zok.borgbackup.whitelist | This volume will be backed up if the Borg backup container is in whitelist-only mode (not implemented)



Environment Variables
====

EnvVar | Example | Description
--- | --- | ---
BORG_REMOTE_URL | ssh://user@host:22/path/to/backups/ | Connection URL accepted by Borg
BORG_PASSPHRASE | random-string | Passphrase that encrypts the encryption keys that encrypt the backups.
BORG_RSH | ssh -oStrictHostKeyChecking=no | SSH invoke. You should provide example value to accept the ssh fingerprint, if using ssh:// remote URL
BORG_PRUNE_RULES | --keep-daily 14 --keep-monthly 10 | Borg prune rules. See Borg doc.
