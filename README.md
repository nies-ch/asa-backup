# Cisco ASA Multiple Context Firewall Backup

This expect script is executed on a backup host and connects to a Cisco ASA firewall using SSH. It detects whether the firewall is configured with multiple security contexts and whether the firewall supports the new backup command added with version 9.3. The backups are first written to the internal flash drive and then copied with scp to the backup server. It also works through a VPN tunnel by applying the undocumented hack ";int=inside" to the destination URL. Due to a bug on Cisco ASA the backup command does not backup webvpn data (profiles, anyconnect packages) when the firewall is in multiple context mode.

# Installation

On the Cisco ASA firewall a backup user with the following minimal privileges is required in the admin and system contexts. Replace password and public keys with the real ones. The SSH authentication key is from the user on the backup host under which this script is running.

```
changeto context admin
privilege cmd level 6 command changeto

enable password ********** level 6
username backup privilege 6
username backup attributes
  ssh authentication publickey ThEeNcRyPtEdSsHpUbLiCkEy==
 
changeto system
privilege cmd level 6 command backup
privilege cmd level 6 mode exec command copy
privilege show level 6 mode exec command tech-support
```

Unfortunately Cisco ASA does not support public key authentication for doing scp from the ASA to the backup host. Hence the password must be provided on the command line in clear text. What a shame for a company that sells security devices.

Copy Python script asa_backup.py to /usr/local/bin and run it once. It creates a template YAML formatted config file at ~/.asa_backup.yaml. Update the created YAML file according your environment with the firewalls, backup server and credentials. For example:

```
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
```

When running again, the script reads the config from the YAML file.
Create a crontab entry on the backup host and run this script daily after midnight:

```
# Backup Cisco ASA/Firepower firewalls.
05 00 * * *	/usr/local/bin/asa_backup.py -f asa1
06 00 * * *	/usr/local/bin/asa_backup.py -f asa2
```

# Retention Algorithm

The script uses a simple retention algorithm to keep daily versions for a week, monthly version on every first of the month and yearly version on every first January. Example shown for a firewall with contexts system, admin, web1, web2:

```
> tree -d asa1
asa1
├── daily_0
├── daily_1
├── daily_2
├── daily_3
├── daily_4
├── daily_5
├── daily_6
├── monthly_02
├── monthly_03
├── monthly_04
├── monthly_05
├── monthly_06
├── monthly_07
├── monthly_08
├── monthly_09
├── monthly_10
├── monthly_11
├── monthly_12
├── yearly_2021
├── yearly_2022
├── yearly_2023
└── yearly_2024

> tree asa1/daily_0
asa1/daily_0
├── backup_admin_active.tar.gz
├── backup_admin_standby.tar.gz
├── backup_system_active.tar.gz
├── backup_system_standby.tar.gz
├── backup_web1_active.tar.gz
├── backup_web1_standby.tar.gz
├── backup_web2_active.tar.gz
├── backup_web2_standby.tar.gz
├── context_admin_active.cfg
├── context_admin_standby.cfg
├── context_web1_active.cfg
├── context_web1_standby.cfg
├── context_web2_active.cfg
├── context_web2_standby.cfg
├── running-config_active.cfg
├── running-config_standby.cfg
├── session.log
├── startup-config_active.cfg
├── startup-config_standby.cfg
├── tech-support_active.txt
└── tech-support_standby.txt
```

# Changes

- 2024-06-18: Rewrote Expect/TCL to Python using Netmiko library. Also backing up configuration of standby device. Check if configs on active and standby do match.
- 2020-04-15: Published to github.
- 2020-05-06: Always flush buffer at end of proc. Config file suffix .cfg. Check for inside interface without errors. Check for software version and do backup only if version >= 9.3.
- 2020-05-05: Applied inside interface hack for VPN. Better error handling.
- 2020-05-04: Write backup file first to flash, then copy, then delete. Procedures for better readability. Procedures dong spawn must set global spawn_id.
- 2020-04-29: Use password as passphrase to encrypted pkcs12 exports.
- 2020-04-27: Function to generate filename suffix. Create destination directory if it not exists. Read password from file in user homedir instead in this code. Suppress send and receive data to stdout.
- 2020-04-23: Check if firewall has multiple contexts. Dynamically get all configured contexts. Little bit of error handling.
- 2020-04-22: First release.
