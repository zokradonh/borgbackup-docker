WIP
====

Backups all docker volumes while automatically detecting [mariadb](https://hub.docker.com/_/mariadb) data volumes
(targeting /var/lib/mysql) and using [mariabackup](https://mariadb.com/kb/en/library/mariabackup-options/) CLI with incremental functions.
This image uses [Borg](https://www.borgbackup.org/) to backup plain data volumes and mariabackup exports. A Borg backup server is
required.

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
