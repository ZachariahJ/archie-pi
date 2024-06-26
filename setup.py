#!/usr/bin/python3
# Script to setup ARCHIE Pi (Another Remote Community Hotspot for Instruction and Education)
# on a Raspberry Pi (all versions) running Raspberry Pi OS Lite.
#
# (C) 2020 faculty and students from Calvin University
#
# License: GNU General Public License (GPL) v3
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import argparse
import os
import sys
import subprocess
import fileinput

# Helper functions

def do(cmd):
    ''' Show and execute system command and return result
    '''
    print(f'-> {cmd}')
    result = subprocess.run(cmd.split(), stderr=sys.stderr, stdout=sys.stdout)
    return (result.returncode == 0)

def append_file(file, line):
    ''' Append a line to a given file
    '''
    try:
        f = open(file, 'a')
        f.write(line + '\n')
        f.close()
    except:
        print(f'unable to append line to file {file}')
        return False
    return True

def replace_line(orig_line, new_line, infile):
    ''' Replace a line with matching text in a specified file
    '''
    found = False
    for line in fileinput.input(infile, inplace = True):
        if not found and orig_line in line:
            print(line.replace(orig_line, new_line), end='')
            found = True
        else:
            print(line, end='')
    return found

def uncomment_line(matching_text, infile):
    ''' Uncomment a line with matching text in a specified file
    '''
    found = False
    for line in fileinput.input(infile, inplace = True):
        if not found and matching_text in line:
            print(line.replace('#',''), end='')
            found = True
        else:
            print(line, end='')
    return found

def uncomment_line_after(matching_text, infile):
    ''' Uncomment line *after* a line with matching text in a specified file
    '''
    found = False
    lastline = ''
    for line in fileinput.input(infile, inplace = True):
        if not found and matching_text in lastline:
            print(line.replace('#',''), end='')
            found = True
        else:
            print(line, end='')
        lastline = line
    return found

def get_latest_kiwix_tools(filename_prefix, url):
    ''' The kiwix tools package is constantly being updated to more recent versions so
        this function determines the url for the most recent kiwix tools. Since files are normally
        listed by increasing date, the last matching file is assumed to be the latest.
    '''
    cmd = f'lynx -dump -listonly -nonumbers {url}'
    result = subprocess.run(cmd.split(), stdout=subprocess.PIPE)
    files = result.stdout.decode('utf-8')
    files_list = files.split('\n')
    matching_filenames = []   # list of matching filenames
    for file in files_list:
        if filename_prefix in file:
            matching_filenames.append(file)
    return matching_filenames[-1]  # the last matching file listed should be the most recent

# Begin setup program
print('Welcome to the ARCHIE Pi setup.')
print('Note that this setup program requires a fresh install of the Raspberry Pi OS.')

##########################################################
# Step 0: read comand line parameters and set home folder
##########################################################
parser = argparse.ArgumentParser()
parser.add_argument("--country", dest="country", help="Wi-Fi country code",
                    type=str, required=True)
parser.add_argument("--ssid", dest="ssid", help="Wi-Fi acces point station id",
                    type=str, required=False, default='ARCHIE-Pi')
args = parser.parse_args()

# Set home folder location (username may be different than the default pi)
HOME = f'/home/{os.getlogin()}'
print(f'Home folder set to: {HOME}')

#########################################################
# Step 1: Update and upgrade OS and install dependencies
#########################################################
print('Staring ARCHIE Pi setup...')
do('service console-setup restart')
do('apt update -y') or sys.exit('Error: Unable to update Raspberry Pi OS.')
do('apt dist-upgrade -y') or sys.exit('Error: Unable to dist-upgrade Raspberry Pi OS.')
do('apt -y install lynx') or sys.exit('Error: cannot install lynx dependency')
do('apt -y install python3-pip') or sys.exit('Error: cannot install pip3 dependency')
do('pip3 install psutil pycountry xmltodict --break-system-packages') or sys.exit('Error: cannot install pip3 dependencies')

# Set current data and time
do('apt -y install ntpdate') or sys.exit('Error: cannot install ntpdate')
do('ntpdate 0.pool.ntp.org')

###############################
# Step 2: Setup wifi hotspot
###############################
print('Setting up wifi hotspot...')

# install hostapd
do('apt-get -y install hostapd dnsmasq') or sys.exit('Unable to install hostapd.')
do('systemctl stop hostapd') or sys.exit('Error: unable to stop hostapd.')
do('systemctl stop dnsmasq') or sys.exit('Error: unable to stop dnsmasq.')

# update dhcpd.conf
do('apt install dhcpcd -y') or sys.exit('Error: unable to install dhcpcd.')
settings='interface wlan0\nstatic ip_address=10.10.10.10\nnohook wpa_supplicant\n'
append_file('/etc/dhcpcd.conf', settings)
do('systemctl restart dhcpcd') or sys.exit('Error: dhcpcd restart failed')

# adjust settings in hostapd config file
settings=f'interface=wlan0\ndriver=nl80211\nhw_mode=g\nchannel=4\nieee80211n=1\nwmm_enabled=0\nauth_algs=1\nssid={args.ssid}\nieee80211d=1\ncountry_code={args.country}\n'
append_file('/etc/hostapd/hostapd.conf', settings) or sys.exit('Error: hostapd.conf append failed')
replace_line('#DAEMON_CONF=""','DAEMON_CONF="/etc/hostapd/hostapd.conf"','/etc/default/hostapd') or sys.exit('Error: Line to replace not found in hostapd')

#Create and edit a new dnsmasq configuration file to set IP address and DNS lease time
do('mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig')
settings='interface=wlan0\ndhcp-range=10.10.10.11,10.10.10.111,12h\n'
append_file('/etc/dnsmasq.conf', settings) or sys.exit('Error adding lines to dnsmasq.conf file')

# Add the country code to wpa_supplicant.conf in case it is needed
append_file('/etc/wpa_supplicant/wpa_supplicant.conf',f'country={args.country}') or sys.exit('Error: adding wpa country code')

# update regulatory domain configuration file
# replace_line('REGDOMAIN=',f'REGDOMAIN={args.country}','/etc/default/crda') or sys.exit('Error: crda country update failed')
do(f'iw reg set {args.country}') or sys.exit('Error: crda country update failed')

# Disable Bluetooth and enable wifi
# NOTE: wifi should only be enabled when country code is set properly (which it should be here)
do('rfkill block bluetooth') or sys.exit('Error: bluetooth disable failed')
do('rfkill unblock wifi') or sys.exit('Error: wifi enable failed')

# Unmask, enable and start open wifi access point
do('systemctl unmask hostapd') or sys.exit('Error: unable to unmask hostapd')
do('systemctl enable hostapd') or sys.exit('Error: unable to enable hostapd')
do('systemctl start hostapd') or sys.exit('Error: unable to start hostapd')
do('service dnsmasq start') or sys.exit('Error: service dnsmasq failed to start')

####################################################
# Step 3: Setup web server and ARCHIE Pi index page
####################################################
print('Setting up web server...')
# Install nginx on Raspberry Pi:
do('apt install nginx -y') or sys.exit('Unable to install nginx')

# Install PHP and SQLite3:
do('apt install php php-fpm php-cli -y') or sys.exit('Error: unable to install php')
do('apt install php-sqlite3 -y') or sys.exit('Error: unable to install sqlite3')

# Enable PHP in nginx config file
conf_file = '/etc/nginx/sites-enabled/default'
replace_line('root /var/www/html;','root /var/www;',conf_file) or sys.exit('Error: nginx config update failed')
replace_line('index index.html index.htm index.nginx-debian.html;','index index.php index.html index.htm;', conf_file) or sys.exit('Error: nginx config update failed')
uncomment_line('location ~ \\.php$', conf_file) or sys.exit('Error: nginx config update failed')
uncomment_line('include snippets/fastcgi-php.conf', conf_file) or sys.exit('Error: nginx config update failed')
uncomment_line('fastcgi_pass unix', conf_file) or sys.exit('Error: nginx config update failed')
uncomment_line_after('fastcgi_pass 127.0.0.1',conf_file) or sys.exit('Error: nginx config update failed')

# Install ARCHIE Pi web front page:
print('Installing ARCHIE Pi web front end...')
do('cp -r www/. /var/www/') or sys.exit('Error copying www files to /var/www')
do('mkdir /var/www/modules') or sys.exit('modules mkdir failed')
do('chown -R www-data.www-data /var/www') or sys.exit('Error: unable tochange ownership of /var/www to www-data')

# Restart nginx service
do('service nginx restart') or sys.exit('Error: unable to restart nginx')

####################################################
# Step 4: Setup Kiwix server 
####################################################
print('Setting up kiwix server (requires a reboot to run)...')
filename = get_latest_kiwix_tools('kiwix-tools_linux-armhf','https://download.kiwix.org/release/kiwix-tools/')
print(f'Downloading {filename}...')
do(f'wget -nv --show-progress -O {HOME}/kiwix-tools.tgz {filename}') or sys.exit('kiwix download failed')
do(f'mkdir {HOME}/kiwix')
do(f'tar xzf {HOME}/kiwix-tools.tgz -C {HOME}/kiwix --strip-components=1')
do(f'rm {HOME}/kiwix-tools.tgz')
do(f'touch {HOME}/kiwix/library_zim.xml')
replace_line('fi',f'fi\n\n{HOME}/kiwix/kiwix-serve --library --port 81 --blockexternal --nolibrarybutton --daemon {HOME}/kiwix/library_zim.xml', '/etc/rc.local') or sys.exit('rc.local line not updated')

def read_only_filesystem():
    ###############################################################
    # Step 5: Harden the install 
    # Avoid possible SD card corruption that can occur when writing 
    # during a power failure by mounting SD card in read-only mode. 
    # Tweak various settings and use tmpfs folders where needed.
    ################################################################
    print('Begin hardening the installation...')

    # Disable swap to eliminate swap writes to SD card.
    # Note that this will limit running programs to the physcial memory space
    print('Disabling swap...')
    do('dphys-swapfile swapoff') or sys.exit('Error: swapoff failed!')
    do('dphys-swapfile uninstall') or sys.exit('Error: swap uninstall failed!')
    do('update-rc.d dphys-swapfile remove') or sys.exit('Error: swapfile remove failed!')
    do('apt -y purge dphys-swapfile') or sys.exit('Error: could not purge swapfile')

    # Disable periodic man page indexing
    print("Disabling periodic man page indexing...")
    do('chmod -x /etc/cron.daily/man-db') or sys.exit('Error: disable periodic man page indexing failed')
    do('chmod -x /etc/cron.weekly/man-db') or sys.exit('Error: disable periodic man page indexing failed')

    # Disable time sync (and associated SD card writes) since the access point typically has no internet
    print("Disabling time sync...")
    do('systemctl disable systemd-timesyncd.service') or sys.exit('Error: timesync diasable error')

    # Mount /boot and / partition in read-only mode to eliminate possiblitiy SD card writes
    replace_line('vfat    defaults','vfat    ro','/etc/fstab')
    replace_line('defaults,noatime','ro','/etc/fstab')

    # Move folders that require writing from the SD card to various tmpfs mounts
    append_file('/etc/fstab','tmpfs   /var/log    tmpfs     noatime,nosuid,mode=0755,size=50M  0 0') or sys.exit('fstab append error')
    append_file('/etc/fstab','tmpfs   /tmp        tmpfs     noatime,nosuid,mode=0755,size=20M  0 0') or sys.exit('fstab append error')
    append_file('/etc/fstab','tmpfs   /var/tmp    tmpfs     noatime,nosuid,mode=0755,size=64k  0 0') or sys.exit('fstab append error')
    append_file('/etc/fstab','tmpfs   /var/lib/dhcpcd       tmpfs   noatime,nosuid,mode=0755,size=64k  0 0') or sys.exit('fstab append error')
    append_file('/etc/fstab','tmpfs   /var/lib/logrotate    tmpfs   nodev,noatime,nosuid,mode=0755,size=16k  0 0') or sys.exit('fstab append error')
    append_file('/etc/fstab','tmpfs   /var/lib/php/sessions tmpfs   nodev,noatime,nosuid,mode=0777,size=64k  0 0') or sys.exit('fstab append error')

    # nginx requires the log folder be present; create folder in the tmpfs at each startup
    append_file('/var/spool/cron/crontabs/root','@reboot mkdir /var/log/nginx') or sys.exit('crontab append error')
    do('chmod 600 /var/spool/cron/crontabs/root') or sys.exit('Error: chmod failed')

    # Move dhcp-leasefile to a tmpfs folder
    append_file('/etc/dnsmasq.conf','dhcp-leasefile=/var/log/dnsmasq.leases') or sys.exit('Error updating dhcp-leasefile location')

    # Move hwclock to a tmpfs folder
    do('rm /etc/fake-hwclock.data') or sys.exit('Error removing existing hwclock file')
    do('ln -s /tmp/fake-hwclock.data /etc/fake-hwclock.data') or sys.exit('Error moving hwclock data file')

    # Move resolv.conf to a tmpfs folder
    do('systemctl stop dhcpcd') or sys.exit('Error: dhcpcd stop failed')
    do('rm /etc/resolv.conf')
    do('ln -s /tmp/resolv.conf /etc/resolv.conf') or sys.exit('Error creating link to resolv.conf')
    do('systemctl start dhcpcd') or sys.exit('Error: dhcpcd start failed')

############################
# Step 6: Clean up
############################
do('apt autoremove -y')
do('apt clean')

print('\nThe ARCHIE Pi access point has installed successfully!')
print('Note that this program cannot be rerun since it requires a fresh install of the OS.')
print(f'Connect a computer to the wifi access point named {args.ssid} and point a browser to: http://10.10.10.10.')
print('Note that these new settings will require a reboot to take effect\nand you will need to install some content modules next.')
print('Don\'t forget to change the default password for the user pi!')
