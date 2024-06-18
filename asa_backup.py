#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------
# Backup of Cisco ASA firewalls with multiple contexts.
# ----------------------------------------------------------------------------
#
# Requires a backup user with the following minimal privileges on the 
# firewall admin and system contexts:
#
#     changeto context admin
#     enable password ********** level 6
#     username backup privilege 6
#     username backup attributes
#      ssh authentication publickey ThEeNcRyPtEdSsHpUbLiCkEy==
# 
#     changeto admin
#     privilege show level 6 command mode 
#     privilege show level 6 command version
#     privilege show level 6 command context
#     privilege show level 6 command interface
#     privilege cmd level 6 command changeto
# 
#     changeto system
#     privilege show level 6 mode exec command tech-support
#     privilege cmd level 6 command backup
#     privilege cmd level 6 command delete
#     privilege cmd level 6 mode exec command copy
#
# The SSH authentication public key is from the backup user on backup host.
# Before running the backup command on the firewall, first run a a normal
# copy command to the scp destination to add the SSH public host key. 
#
# Open Issues
# -----------
# - Use public key authentication for backup to scp destination, so no pass-
#   words need to be hardcoded in this script. Not supported by Cisco.
# - Netmiko doesn't know the "enable <level>" command yet. Defaults to enable
#   level 15. 



# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

CONFIG_FILE = "~/.asa_backup.yaml"
CONFIG_DEFAULT = """---
# CISCO ASA FIREWALLS BACKUP CONFIGURATION
#
# Use yamllint <thisfile> for syntax checking after editing this file.
# Defaults to be used for all the firewalls defined further below. They can
# be overwritten when needed. The device type is from Python netmiko library
# See https://github.com/ktbyers/netmiko for more.

defaults:
  device-type: cisco_asa
  conn-timeout: 30
  read-timeout: 1800
  username: asa-username
  password: YoUr.AsApAsSwOrD.HeRe
  ssh-key: ~/.ssh/id_rsa
  backup-host: 10.0.x.y
  backup-username: backup-username
  backup-password: YoUr.BaCkUpSerVeRpAsSwOrD.HeRe
  backup-dir: /mnt/backup/cisco/asa

firewalls:
  asa1:
    hostname: asa1-admin.example.com
    enable-secret: YoUr.EnAbLeSeCrEt.HeRe
  asa2:
    hostname: asa2-admin.example.com
    enable-secret: YoUr.EnAbLeSeCrEt.HeRe
"""



# ----------------------------------------------------------------------------
# Import Libraries
# ----------------------------------------------------------------------------
# Netmiko: https://github.com/ktbyers/netmiko

import argparse
import yaml
import os
import re
import socket
import subprocess
import sys
import difflib

from datetime import datetime
from netmiko import ConnectHandler
from pprint import pprint



# ----------------------------------------------------------------------------
# is_resolvable
# ----------------------------------------------------------------------------
# Returns True if the hostname is resolvable via DNS. False otherwise.
#
def is_resolvable(host):
    try:
        socket.gethostbyname(host)
        return(True)
    except socket.error:
        return(False)



# ----------------------------------------------------------------------------
# is_host_reachable 
# ----------------------------------------------------------------------------
# Check if a host is reachable.
# Returns: True if the host is reachable, False otherwise
#
def is_host_reachable(host):
    result = subprocess.run(['ping', '-c', '1', host], 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return(result.returncode == 0)



# ----------------------------------------------------------------------------
# write_default_config_file
# ----------------------------------------------------------------------------
# Read configuration file in YAML format and set default values if not
# defined. Simplifies further code and error checking. :-)
# Returns a dict with the configuration parameters.
#
def write_default_config_file():
    try:
        file_path = os.path.expanduser(CONFIG_FILE)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                file.write(CONFIG_DEFAULT)
            os.chmod(file_path, 0o600)
    except Exception as e:
        sys.exit(f"ERROR: Writing default config failed: {e}")
    return



# ----------------------------------------------------------------------------
# read_configfile
# ----------------------------------------------------------------------------
# Read configuration file in YAML format and set default values if not
# defined. Simplifies further code and error checking. :-)
# Returns a dict with the configuration parameters.
#
def read_configfile(file_path):
    cfg = []
    try:
        if not file_path:
            file_path = os.path.expanduser(CONFIG_FILE)
        with open(file_path, 'r') as file:
            cfg = yaml.safe_load(file)
    except yaml.YAMLError as e:
        sys.exit(f"YAML format error: {e}")
    except Exception as e:
        sys.exit(f"ERROR: Reading config failed: {e}")
    else:
        # Add defaults to firewall specific config if not set.
        for fw in cfg["firewalls"]:
            for key in cfg["defaults"]:
                if key not in cfg["firewalls"][fw]:
                    cfg["firewalls"][fw][key] = cfg["defaults"][key]
    return(cfg)



# ----------------------------------------------------------------------------
# validate_firewalls 
# ----------------------------------------------------------------------------
# Validate commandline argument firewalls. If empty returns full list of
# firewalls defined in configuration file. Aborts if firewalls given are not
# listed in config file. Returns list of firewalls.
#
def validate_firewalls(cfg, args_firewalls):
    firewalls = []
    if not args_firewalls:
        firewalls = cfg["firewalls"].keys()
    elif set(args_firewalls).issubset(set(cfg["firewalls"].keys())):
        firewalls = args_firewalls
    elif len(args_firewalls) == 1 and args_firewalls[0] == "all":
        firewalls = cfg["firewalls"].keys()
    else:
        missing = set(args_firewalls) - set(cfg["firewalls"].keys())
        sys.exit(f"Firewalls not allowed: {missing}")
    return(list(set(firewalls)))



# ----------------------------------------------------------------------------
# get_retention_slot
# ----------------------------------------------------------------------------
# Define retention filename slot for simple retention algorithm:
# Daily up to 7 per week
# Monthly up to 12 per year on 1st day of month.
# Yearly up to forever on 1st of January
# Run script daily after midnight. Argument is datetime. Returns string.
#
def get_retention_slot(dt):
    if dt.day == 1 and dt.month == 1:
        slot = "yearly_{}".format(dt.year)
    elif dt.day == 1:
        slot = "monthly_{}".format(dt.month)
    else:
        slot = "daily_{}".format(dt.weekday())
    return(slot)



# ----------------------------------------------------------------------------
# get_version
# ----------------------------------------------------------------------------
# Returns the ASA software version as dict with major, minor, maintenance
# and interim.
# Example: Cisco Adaptive Security Appliance Software Version 9.16(3)23
# major = 9, minor = 16, maintenance = 3, interim = 23
#
def get_version(conn):
    output = conn.send_command("show version | include ^Cisco.*Appliance.*Version")
    digits = re.findall(r'\d+', output)
    version = {
        "major":       int(digits[0]),
        "minor":       int(digits[1]),
        "maintenance": int(digits[2]),
        "interim":     int(digits[3]) 
    }
    return(version)



# ----------------------------------------------------------------------------
# get_context_mode
# ----------------------------------------------------------------------------
# Queries context mode of the ASA firewall. Change to system context if ASA
# has multiple contexts. Returns context mode (single, multiple).
#
def get_context_mode(conn):
    pattern = re.compile(r'Security context mode: (single|multiple)')
    output = conn.send_command("show mode")
    match = pattern.search(output)
    return(match.group(1))



# ----------------------------------------------------------------------------
# get_failover_units
# ----------------------------------------------------------------------------
#
def get_failover_units(conn):
    units = [ "active" ]
    output = conn.send_command("show failover | include ^Failover (On|Off)")
    if re.match(r'^Failover On', output):
        units.append("standby")
    return(units)



# ----------------------------------------------------------------------------
# get_contexts
# ----------------------------------------------------------------------------
# Show contexts, parse output, append context names into list contexts.
# Returns list of context names, starting with system.
#
def get_contexts(conn):
    pattern = re.compile(r'^[ \*]([A-Za-z0-9\-]+)')
    contexts = []
    output = conn.send_command("show context")
    for line in output.split('\n'): 
        if match := pattern.search(line):
            contexts.append(match.group(1))
    return(contexts)



# ----------------------------------------------------------------------------
# get_interface_hack
# ----------------------------------------------------------------------------
# In single context mode, when accessing ASA through a VPN tunnel and doing a
# copy command, the ASA uses the public interface IP as source address. The
# copy command then fails because traffic is not encrypted through the VPN
# tunnel. Appending the option ";int=inside" is an undocumented hack to use
# the inside IP address instead. Works only for the copy command, not for
# the backup command.
#
def get_interface_hack(conn):
    ihack = ""
    output = conn.send_command("show interface inside | include ^Interface")
    if re.match(r'^Interface.*inside.*is up', output):
        ihack = ";int=inside"
    return(ihack)



# ----------------------------------------------------------------------------
# run_batch_commands
# ----------------------------------------------------------------------------
# Run array of commands on active ASA (default) or on standby unit.
#
def run_batch_commands(conn, commands, unit="active"):
    for command in commands:
        if unit == "standby":
            command = f"failover exec {unit} {command}"
        output = conn.send_command(command)
        #print(output)
    return



# ----------------------------------------------------------------------------
# copy_tech_support
# ----------------------------------------------------------------------------
# Sending tech-support directly to scp path fails. Copy first to flash disk,
# then copy, then delete.
#
def copy_tech_support(conn, unit, backup_url, ihack):
    print(f"Collecting tech-support on {unit} unit  ...")
    file = f"tech-support_{unit}.txt"
    commands = [
        f"show tech-support file flash:/{file}",
        f"copy /noconfirm flash:/{file} {backup_url}/{file}{ihack}",
        f"delete /noconfirm flash:/{file}"
    ]
    run_batch_commands(conn, commands, unit)
    return 



# ----------------------------------------------------------------------------
# copy_config
# ----------------------------------------------------------------------------
# Copy running-config and startup-config to backup_url. In single mode it is
# the entire configuration in multiple context mode it is only the system
# context.
#
def copy_config(conn, unit, backup_url, ihack, contexts):
    print(f"Collecting config on {unit} unit ...")
    pattern = re.compile(r'^\s*config-url\s+(\S+)')
    commands = [
      f"copy /noconfirm running-config {backup_url}/running-config_{unit}.cfg{ihack}",
      f"copy /noconfirm startup-config {backup_url}/startup-config_{unit}.cfg{ihack}"
    ]
    # We have contexts. Also backup the context configs individually.
    for context in contexts:
        output = conn.send_command(f"show run context {context} | include config-url")
        if match := pattern.search(output):
            srcfile = match.group(1)
            commands.append(f"copy /noconfirm {srcfile} {backup_url}/context_{context}_{unit}.cfg{ihack}")
    run_batch_commands(conn, commands, unit)
    return



# ----------------------------------------------------------------------------
# run_backup
# ----------------------------------------------------------------------------
# The backup command was added with ASA version 9.3(2).
# It contains the running-config, startup-config, certificates and if there
# was no bug with multiple contexts, also webvpn data such as anyconnect
# packages, but backup of WebVPN data fails in multiple contexts.
# First run a backup to flash disk and then copy it via scp due to Cisco bug
# CSCvh02142.
#
def run_backup(conn, unit, backup_url, ihack, contexts, passphrase):
    ver = get_version(conn)
    if not (ver["major"] >= 9 and ver["minor"] >= 3 and ver["maintenance"] >= 2):
        print("Backup command not invented yet.")
        return
    if not contexts:
        print(f"Backing up single context on {unit} unit ...")
        file = f"backup_{unit}.tar.gz"
        commands = [
            f"backup /noconfirm passphrase {passphrase} location flash:/{file}",
            f"copy /noconfirm flash:/{file} {backup_url}/{file}{ihack}",
            f"delete /noconfirm flash:/{file}"
        ]
        run_batch_commands(conn, commands, unit)
    else:
        # We have contexts. Also backup system context.
        for context in [ "system" ] + contexts:
            print(f"Backing up context {context} on {unit} unit ...")
            file = f"backup_{context}_{unit}.tar.gz"
            commands = [
                f"backup /noconfirm context {context} passphrase {passphrase} location flash:/{file}",
                f"copy /noconfirm flash:/{file} {backup_url}/{file}{ihack}",
                f"delete /noconfirm flash:/{file}"
            ]
            run_batch_commands(conn, commands, unit)
    return



# ----------------------------------------------------------------------------
# find_cryptochecksum 
# ----------------------------------------------------------------------------
def find_cryptochecksum(lines):
    pattern = re.compile(r'^Cryptochecksum:([0-9a-f]+)$')
    checksum = False
    for line in lines:
        if match := pattern.match(line.strip()):
            checksum = match.group(1)
    return(checksum)



# ----------------------------------------------------------------------------
# compare_files
# ----------------------------------------------------------------------------
def compare_files(dir, file1, file2):
    try:
        with open(dir + "/" + file1, 'r') as f1:
            file1_lines = f1.readlines()
        with open(dir + "/" + file2, 'r') as f2:
            file2_lines = f2.readlines()
    except Exception as e:
        print(f"ERROR: Reading files {file1}, {file2} failed: {e}")
    else:
        file1_cksum = find_cryptochecksum(file1_lines)
        file2_cksum = find_cryptochecksum(file2_lines)
        if file1_cksum != file2_cksum:
            print("-" * 80)
            print(f"Files {file1} and {file2} differ:")
            print("-" * 80)
            diff = difflib.unified_diff(file1_lines, file2_lines, fromfile=file1, tofile=file2)
            for line in diff:
                print(line, end='')
    return



# ----------------------------------------------------------------------------
# verify_backup
# ----------------------------------------------------------------------------
# Startup-config and running-config should be the same. Otherwise a write mem
# has been forgotten. Config on active and standby unit should also be the
# same or replication has failed.
# 
def verify_backup(destdir, failover_units, contexts):
    print(f"Verifying backup on {destdir}:")
    result = subprocess.run(['ls', '-al', destdir], check=True, capture_output=True, text=True)
    print(result.stdout)
    compare_files(destdir, "startup-config_active.cfg", "running-config_active.cfg")
    if "standby" in failover_units:
        compare_files(destdir, "startup-config_standby.cfg", "running-config_standby.cfg")
        for context in contexts:
            compare_files(destdir, f"context_{context}_active.cfg", f"context_{context}_standby.cfg")
    return



# ----------------------------------------------------------------------------
# backup_firewall
# ----------------------------------------------------------------------------
def backup_firewall(cfg, fw):
    hostname = cfg["firewalls"][fw]["hostname"]
    if not is_resolvable(hostname):
        print(f"ERROR: Host {hostname} is not resolvable!")
        return
    if not is_host_reachable(hostname):
        print(f"ERROR: Host {hostname} is not reachable!")
        return 

    dt = datetime.now()
    slot = get_retention_slot(dt)
    destdir = "/".join([cfg["firewalls"][fw]["backup-dir"], fw, slot])
    backup_url = "scp://{}:{}@{}/{}".format(
        cfg["firewalls"][fw]["backup-username"],
        cfg["firewalls"][fw]["backup-password"],
        cfg["firewalls"][fw]["backup-host"], destdir
    )
    cisco_asa = {
        "host":                  hostname,
        "device_type":           "cisco_asa",
        "username":              cfg["firewalls"][fw]["username"],
        "password":              cfg["firewalls"][fw]["password"],
        "secret":                cfg["firewalls"][fw]["enable-secret"],
        "read_timeout_override": cfg["firewalls"][fw]["read-timeout"],
        "conn_timeout":          cfg["firewalls"][fw]["conn-timeout"],
        "session_log":           destdir + "/" + "session.log",
        "use_keys":              True,
        "key_file":              cfg["firewalls"][fw]["ssh-key"],
        "disable_sha2_fix":      True,
        "verbose":               True,
    }

    print("")
    print("=" * 80)
    print("Firewall name   : {}".format(fw))
    print("Firewall host   : {}".format(hostname))
    print("Backup host     : {}".format(cfg["firewalls"][fw]["backup-host"]))
    print("Backup directory: {}".format(destdir))
    print("Backup date/time: {}".format(dt.strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 80)
    print("")

    try:
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        else:
            timestamp = dt.timestamp() 
            os.utime(destdir, (timestamp, timestamp))
    except Exception as e:
        sys.exit(f"ERROR: Creating directory {destdir} failed: {e}")

    try:
        with ConnectHandler(**cisco_asa) as conn:
            context_mode = get_context_mode(conn)
            failover_units = get_failover_units(conn)
            if context_mode == "multiple":
                ihack = ""
                conn.send_command("changeto system")
                contexts = get_contexts(conn)
            else:
                ihack = get_interface_hack(conn)
                contexts = []
            for unit in failover_units:
                copy_tech_support(conn, unit, backup_url, ihack)
                copy_config(conn, unit, backup_url, ihack, contexts)
                run_backup(conn, unit, backup_url, ihack, contexts, cfg["firewalls"][fw]["password"])
    except subprocess.CalledProcessError as e:
        print(f'ERROR: Subprocess call failed: {e}')
    except Exception as e:
        print(f"ERROR: Backing up {hostname} failed: {e}")

    verify_backup(destdir, failover_units, contexts)
    return



# -----------------------------------------------------------------------------
# get_arguments
# -----------------------------------------------------------------------------
# Read commandline arguments. Returns a Namespace object with all the given
# arguments.
#
def get_arguments():
    parser = argparse.ArgumentParser(
        description="Update object-groups on the Cisco firewalls.")
    parser.add_argument('-c', '--config', required=False, 
        metavar="FILENAME", help="Configuration file in YAML format.")
    parser.add_argument('-f', '--firewalls', required=True, nargs='+',
        metavar="NAME", help="""Select firewalls (HA pairs) to be updated as
        listed in the YAML config file. If not used or set to 'all', all 
        configured firewalls are backed up.""")
    args = parser.parse_args()
    return(args)



# ----------------------------------------------------------------------------
# MAIN 
# ----------------------------------------------------------------------------
# Read commandline arguments, configuration file and iterate over the fire-
# walls given as argument or in configuration file.
#
if __name__ == "__main__":
    write_default_config_file()
    args = get_arguments()
    cfg = read_configfile(args.config)    
    firewalls = validate_firewalls(cfg, args.firewalls)
    for fw in firewalls:
        backup_firewall(cfg, fw)
