#!/usr/bin/python3

import docker
import os
import subprocess
import re
import datetime
import json

from subprocess import run, CalledProcessError

from pathlib import Path

host_volumes_path = Path("/hostvolumes")
database_output_path = Path("/backups")
projects_path = Path("/hostprojects")
projects_output_path = Path("/bundles")

client = docker.DockerClient(base_url='unix://var/run/docker.sock')

borg_parameters = json.loads(Path("/borg_parameters.json").read_text())

# code from borgbackup
def sizeof_fmt(num, suffix='B', units=None, power=None, sep='', precision=2, sign=False):
    sign = '+' if sign and num > 0 else ''
    fmt = '{0:{1}.{2}f}{3}{4}{5}'
    prec = 0
    for unit in units[:-1]:
        if abs(round(num, precision)) < power:
            break
        num /= float(power)
        prec = precision
    else:
        unit = units[-1]
    return fmt.format(num, sign, prec, sep, unit, suffix)

def sizeof_fmt_iec(num, suffix='B', sep='', precision=2, sign=False):
    return sizeof_fmt(num, suffix=suffix, sep=sep, precision=precision, sign=sign,
                      units=['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi'], power=1024)


def sizeof_fmt_decimal(num, suffix='B', sep='', precision=2, sign=False):
    return sizeof_fmt(num, suffix=suffix, sep=sep, precision=precision, sign=sign,
                      units=['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y'], power=1000)

def get_db_data_volume(container):
    volume_name = next((mount["Name"] for mount in container.attrs['Mounts'] if mount["Destination"] == "/var/lib/mysql"), None)
    return client.volumes.get(volume_name)


def create_git_bundle(git_directory, output_directory):
    """Creates a .gitbundle archive file by 'git bundle create'"""
    # check directory exists and if is a valid git directory
    if git_directory.exists() and run(["git", "-C", git_directory, "rev-parse", "--git-dir"], capture_output=True).returncode == 0:
        print(f"Creating git bundle for repository {git_directory.name}...")
        try:
            output_filename = output_directory / f"{git_directory.name}.gitbundle"
            run(["git", "-C", git_directory, "bundle", "create", output_filename, "master"], capture_output=True, check=True)
            print(f" Success, size: {sizeof_fmt_decimal(output_filename.stat().st_size)}")
        except CalledProcessError as ex:
            print(f" Failed to create git bundle of project '{git_directory.name}' (Returncode {ex.returncode}).")
            print(ex.cmd)
            print(ex.stdout)
            print(ex.stderr)
    else:
        print(f"Warning: Project {git_directory.name} is not a git repository.")


def get_ignored_volumes(all_volumes, volumes_path):
    ignored_volumes = set()

    for volume in all_volumes:
        if (volume.attrs["Labels"] and "xyz.zok.borgbackup.ignore" in volume.attrs["Labels"]) or (volumes_path / volume.name / ".xyz.zok.borgbackup.ignore").exists():
            ignored_volumes.add(volume)
    return ignored_volumes

def archive_all_compose_projects():
    for compose_dir in projects_path.glob("*"):
        if compose_dir.is_dir():
            create_git_bundle(compose_dir, projects_output_path)


def create_database_backup(db, outputpath, backup_number, incremental_lsn=0):
    exitcode, versionstring = db.exec_run("mariabackup --version")
    if exitcode != 0:
        print(f" ERROR: Database container {db.name} does not support 'mariabackup'!")
        return False

    versionstring = re.sub(r'\s*$', '', versionstring.decode('utf-8'))
    print(f" Using {versionstring}")

    cmd = f'sh -c "mariabackup --backup {f"--incremental-lsn={incremental_lsn}" if backup_number > 0 else ""} --stream=xbstream --user=root --password=$MYSQL_ROOT_PASSWORD"'

    result = db.exec_run(cmd, stream=True, demux=True)
    mbstream = subprocess.Popen(["mbstream", "-x", "-C", outputpath / f"inc.{backup_number}"],
                                stdin=subprocess.PIPE)
    
    # stream all data from mariabackup process to mbstream process
    # this creates a directory with all information of this backup
    backuplog = b""
    while True:
        try:
            out, debug = next(result.output)
            if debug: # save mariabackup stderr outputs to separate log
                backuplog += debug
            if out: # pipe mariabackup stdout to mbstream
                mbstream.stdin.write(out)
                mbstream.stdin.flush()
        except StopIteration:
            # save log file
            logfile = outputpath / f"inc.{backup_number}" / "error.log"
            logfile.write_bytes(backuplog)
            
            # check if the backup process created some data
            if not any((outputpath / f"inc.{backup_number}").iterdir()):
                (outputpath / f"inc.{backup_number}").rmdir() # existence of directory inc.0 is indicator whether we need to make an initial backup or incremental backup
                if incremental_lsn == 0:
                    print(f" Failed initial backup. Either container has no MYSQL_ROOT_PASSWORD or other error. (See errors above, if any or {logfile})")
                else:
                    print(f" Failed backup number {backup_number}. Either container has no MYSQL_ROOT_PASSWORD or other error. (See errors above, if any, or {logfile})")
                return False

            # check log file
            if b"completed OK!" not in backuplog:
                print(f" WARNING: Missing success message in mariabackup log. See {logfile}.")

            # print success message
            print(" Size: {}".format(sizeof_fmt_decimal(sum(f.stat().st_size for f in (outputpath / f"inc.{backup_number}").glob('**/*') if f.is_file()))))
            return True

def verify_database_container(db):
    for env in db.attrs["Config"]["Env"]:
        if env.startswith("MARIADB_MAJOR=") and db.status == "running":
            return True
    return False

database_containers = client.containers.list({"status": ["running"], "volume": ["/var/lib/mysql"]})
database_containers = set(db for db in database_containers if verify_database_container(db))
database_volumes = set(get_db_data_volume(db) for db in database_containers)
# TODO: support stopped databases
all_volumes = set(client.volumes.list())
ignored_volumes = get_ignored_volumes(all_volumes, host_volumes_path)

# create list of all volumes to backup except the ignored ones
folders_to_backup = [str(host_volumes_path / volume.name) for volume in all_volumes - database_volumes - ignored_volumes]

# create archive of all compose projects via git bundle
archive_all_compose_projects()

# add the compose projects backups to general backup list
folders_to_backup.append(str(projects_output_path))

# create incremental database backups
print("Found database containers:")
print(json.dumps(sorted([c.name for c in database_containers]), indent=4))

for db in database_containers:
    
    # get database volume
    if (dbvolume := get_db_data_volume(db)) is None:
        print(f"ERROR: Database container {db.name} has no volume mount to '/var/lib/mysql'!")
        continue
    volume_name = dbvolume.name

    dbpath = database_output_path / volume_name

    if not (dbpath / "inc.0").exists():
        # first backup of this database
        (dbpath / "inc.0").mkdir(parents=True)

        try:
            print(f"Create first full database backup of {db.name} (Volume: {volume_name})...")
            create_database_backup(db, dbpath, 0)
        except:
            (dbpath / "inc.0").rmdir()

    else:
        # incremental backup of this database
        # find last incremental backup if any
        last_incremental_number = max(int(re.search(r"(\d+)$", d.name).group(1)) for d in dbpath.glob("inc.*"))

        while True:
            try:
                """
                Example contents of inc.0 xtrabackup_checkpoints:
                    backup_type = full-backuped
                    from_lsn = 0
                    to_lsn = 9047889
                    last_lsn = 9047889
                Example contents of inc.1 xtrabackup_checkpoints:
                    backup_type = incremental
                    from_lsn = 9047889
                    to_lsn = 9224049
                    last_lsn = 9224049
                """
                checkpoints = (dbpath / f"inc.{last_incremental_number}" / "xtrabackup_checkpoints").read_text()
                last_to_lsn = int(re.search(r"to_lsn\s*=\s*(\d+)", checkpoints).group(1))
                break; # last backup looks good, continue making the incremental backup
            except:
                if last_incremental_number == 0:
                    print(f"ERROR: Unable to create incremental backup on failed initial backup of {db.name}!")
                    raise Exception
                    break
                else:
                    print(f"ERROR: Backup number {last_incremental_number} of {db.name} is invalid.")
                    print(f"Auto-Resolving by deactivating failed incremental backup {last_incremental_number}.") 
                    if not any((dbpath / f"inc.{last_incremental_number}").iterdir()):
                        (dbpath / f"inc.{last_incremental_number}").rmdir() # delete backup if there is no data
                    else:
                        (dbpath / f"inc.{last_incremental_number}").rename(dbpath / f"failed.{datetime.datetime.now().isoformat()}.{last_incremental_number}") # rename if not empty
                    print(f"Retrying by using previous backup {last_incremental_number-1}...")
                    last_incremental_number -= 1
                    continue

        next_incremental_number = last_incremental_number + 1

        (dbpath / f"inc.{next_incremental_number}").mkdir(parents=True)
        try:
            print(f"Create incremental database backup number {next_incremental_number} (from-LSN: {last_to_lsn}) of {db.name} (Volume: {volume_name})...")
            create_database_backup(db, dbpath, next_incremental_number, last_to_lsn)
        except Exception as e:
            print(f"Failed to backup {db.name}. Error:")
            #print(e)
            (dbpath / f"inc.{next_incremental_number}").rmdir()
            raise

    folders_to_backup.append(str(database_output_path / dbpath))

print(f"Found folders to backup:")
print(json.dumps(sorted(folders_to_backup), indent=4))
print(f"Number of folders: {len(folders_to_backup)}.")

# upload backups
creation = run(["borg", "create", "--stats", f"{borg_parameters['BORG_REMOTE_URL']}::{{now}}"] + folders_to_backup)
if creation.returncode > 0:
    print("NO BACKUP CREATED. BORG Collective failed to assimilate biological entity.")

# prune old backups
run(["borg", "prune", "-v", "--list"] + borg_parameters["BORG_PRUNE_RULES"].split(" ") + [borg_parameters['BORG_REMOTE_URL']])