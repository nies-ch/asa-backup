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

Create a crontab entry on the backup host and run this script daily after midnight:

```
# Backup Cisco ASA/Firepower firewalls.
05 00 * * *	/usr/local/bin/asa_backup.exp firewall1-admin.example.com /mnt/backup/cisco/firewall1
06 00 * * *	/usr/local/bin/asa_backup.exp firewall2-admin.example.com /mnt/backup/cisco/firewall2
07 00 * * *	/usr/local/bin/asa_backup.exp firewall3-admin.example.com /mnt/backup/cisco/firewall3
```

Save the password used for enable and the scp command into a file in the user's home directory and make it readable by the owner only.

```
echo -n "mysecretpassword" >~/.backuppw
chmod 400 ~/.backuppw
```

# Retention Algorithm

The script uses a simple retention algorithm to keep daily versions for a week, monthly version on every first of the month and yearly version on every first January. Example shown for a firewall with contexts system, admin and web:

```
ciscobackup@backuphost:~> ls -al firewall1
total 4736
drwx------  2 ciscobackup ciscobackup   4096 May 10 00:05 .
drwx------ 12 ciscobackup ciscobackup   4096 May  5 09:37 ..
-rw-r--r--  1 ciscobackup ciscobackup  49295 May 10 00:05 backup_admin_daily_0.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49292 May  4 09:57 backup_admin_daily_1.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49296 May 12 00:05 backup_admin_daily_2.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49285 May 13 00:05 backup_admin_daily_3.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49293 May 14 00:05 backup_admin_daily_4.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49290 May 15 00:05 backup_admin_daily_5.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49295 May  9 00:05 backup_admin_daily_6.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  49295 Feb  1 00:05 backup_admin_monthly_02.txt
-rw-r--r--  1 ciscobackup ciscobackup  49295 Mar  1 00:05 backup_admin_monthly_03.txt
-rw-r--r--  1 ciscobackup ciscobackup  49295 Apr  1 00:05 backup_admin_monthly_04.txt
-rw-r--r--  1 ciscobackup ciscobackup  49295 May  1 00:05 backup_admin_monthly_05.txt
-rw-r--r--  1 ciscobackup ciscobackup  49295 Jan  1 00:05 backup_admin_yearly_2020.txt
-rw-r--r--  1 ciscobackup ciscobackup  46494 May 10 00:05 backup_system_daily_0.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46490 May  4 09:57 backup_system_daily_1.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46498 May 12 00:05 backup_system_daily_2.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46490 May 13 00:05 backup_system_daily_3.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46492 May 14 00:05 backup_system_daily_4.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46498 May 15 00:05 backup_system_daily_5.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46493 May  9 00:05 backup_system_daily_6.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  46493 Feb  1 00:05 backup_system_monthly_02.txt
-rw-r--r--  1 ciscobackup ciscobackup  46493 Mar  1 00:05 backup_system_monthly_03.txt
-rw-r--r--  1 ciscobackup ciscobackup  46493 Apr  1 00:05 backup_system_monthly_04.txt
-rw-r--r--  1 ciscobackup ciscobackup  46493 May  1 00:05 backup_system_monthly_05.txt
-rw-r--r--  1 ciscobackup ciscobackup  46493 Jan  1 00:05 backup_system_yearly_2020.txt
-rw-r--r--  1 ciscobackup ciscobackup  85243 May 10 00:05 backup_web_daily_0.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85241 May  4 00:05 backup_web_daily_1.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85231 May 12 00:05 backup_web_daily_2.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85242 May 13 00:05 backup_web_daily_3.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85477 May 14 00:05 backup_web_daily_4.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85471 May 15 00:05 backup_web_daily_5.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85253 May  9 00:05 backup_web_daily_6.tar.gz
-rw-r--r--  1 ciscobackup ciscobackup  85253 Feb  1 00:05 backup_web_monthly_02.txt
-rw-r--r--  1 ciscobackup ciscobackup  85253 Mar  1 00:05 backup_web_monthly_03.txt
-rw-r--r--  1 ciscobackup ciscobackup  85253 Apr  1 00:05 backup_web_monthly_04.txt
-rw-r--r--  1 ciscobackup ciscobackup  85253 May  1 00:05 backup_web_monthly_05.txt
-rw-r--r--  1 ciscobackup ciscobackup  85253 Jan  1 00:05 backup_web_yearly_2020.txt
-rw-r--r--  1 ciscobackup ciscobackup 366798 May 10 00:05 tech-support_daily_0.txt
-rw-r--r--  1 ciscobackup ciscobackup 363849 May  4 09:57 tech-support_daily_1.txt
-rw-r--r--  1 ciscobackup ciscobackup 367125 May 12 00:05 tech-support_daily_2.txt
-rw-r--r--  1 ciscobackup ciscobackup 367974 May 13 00:05 tech-support_daily_3.txt
-rw-r--r--  1 ciscobackup ciscobackup 368130 May 14 00:05 tech-support_daily_4.txt
-rw-r--r--  1 ciscobackup ciscobackup 367974 May 15 00:05 tech-support_daily_5.txt
-rw-r--r--  1 ciscobackup ciscobackup 366656 May  9 00:05 tech-support_daily_6.txt
-rw-r--r--  1 ciscobackup ciscobackup 366054 May  1 00:05 tech-support_monthly_05.txt
-rw-r--r--  1 ciscobackup ciscobackup 366054 Jan  1 00:05 tech-support_yearly_2020.txt
```

# Open Issues

 - Use public key authentication for backup to scp destination, so no passwords need to be hardcoded in this script. How to? Can't find Cisco doc. Not supported by Cisco. Shame.
 - Better error handling.
 - Send mail alert on failures.

# Changes

- 2020-04-15: Published to github.
- 2020-05-06: Always flush buffer at end of proc. Config file suffix .cfg. Check for inside interface without errors. Check for software version and do backup only if version >= 9.3.
- 2020-05-05: Applied inside interface hack for VPN. Better error handling.
- 2020-05-04: Write backup file first to flash, then copy, then delete. Procedures for better readability. Procedures dong spawn must set global spawn_id.
- 2020-04-29: Use password as passphrase to encrypted pkcs12 exports.
- 2020-04-27: Function to generate filename suffix. Create destination directory if it not exists. Read password from file in user homedir instead in this code. Suppress send and receive data to stdout.
- 2020-04-23: Check if firewall has multiple contexts. Dynamically get all configured contexts. Little bit of error handling.
- 2020-04-22: First release.