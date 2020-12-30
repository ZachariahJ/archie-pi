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
import sys
import subprocess
import fileinput

# Helper functions

def do(cmd):
    ''' Execute system command and return result
    '''
    if args.verbose:
        print('-> {}'.format(cmd))
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
        return False
    return True

def replace_line(orig_line, new_line, infile):
    ''' Replace a matching line in a specified file
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
    ''' Uncomment a matching line in a specified file
    '''
    found = False
    for line in fileinput.input(infile, inplace = True):
        if not found and matching_text in line:
            print(line.replace('#',''), end='')
            found = True
        else:
            print(line, end='')
    return found

#########################################
# Step 0: read comand line parameters
#########################################
parser = argparse.ArgumentParser()
parser.add_argument("-v", action="store_true", default=False, required=False,
 			        dest="verbose", help="verbose output")
parser.add_argument("--country", dest="country", help="Wi-Fi country code",
                    type=str, required=True)
parser.add_argument("--ssid", dest="ssid", help="Wi-Fi acces point station id",
                    type=str, required=False, default='ARCHIE-Pi')
args = parser.parse_args()

#########################################
# Step 1: Update and upgrade OS
#########################################
if args.verbose:
    print('Staring ARCHIE Pi setup...')

do('apt update -y') or sys.exit('Error: Unable to update Raspberry Pi OS.')
do('apt dist-upgrade -y') or sys.exit('Error: Unable to dist-upgrade Raspberry Pi OS.')
do('apt autoremove -y') or sys.exit('Error: Unable to autoremove install files.')

#########################################
# Step 2: Setup wifi hotspot
#########################################
if args.verbose:
    print('Setting up wifi hotspot...')

# install hostapd
do('apt-get -y install hostapd dnsmasq') or sys.exit('Unable to install hostapd.')
do('systemctl stop hostapd') or sys.exit('Error: unable to stop hostapd.')
do('systemctl stop dnsmasq') or sys.exit('Error: unable to stop dnsmasq.')

# update dhcpd.conf file
settings='interface wlan0\nstatic ip_address=10.10.10.10\nnohook wpa_supplicant\n'
append_file('/etc/dhcpcd.conf', settings)
do('systemctl restart dhcpcd') or sys.exit('Error: dhcpcd restart failed')

# adjust settings in hostapd config file
settings='interface=wlan0\ndriver=nl80211\nhw_mode=g\nchannel=4\nieee80211n=1\nwmm_enabled=0\nauth_algs=1\nssid={}\nieee80211d=1\ncountry_code={}\n'.format(args.ssid,args.country)
append_file('/etc/hostapd/hostapd.conf', settings) or sys.exit('Error: hostapd.conf append failed')
replace_line('#DAEMON_CONF=""','DAEMON_CONF="/etc/hostapd/hostapd.conf"','/etc/default/hostapd') or sys.exit('Error: Line to replace not found in hostapd')

#Create and edit a new dnsmasq configuration file to set IP address and DNS lease time
do('mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig')
settings='interface=wlan0\ndhcp-range=10.10.10.11,10.10.10.61,12h\n'
append_file('/etc/dnsmasq.conf', settings) or sys.exit('Error adding lines to dnsmasq.conf file')

# Add the country code to wpa_supplicant.conf in case it is needed
append_file('/etc/wpa_supplicant/wpa_supplicant.conf','country={}'.format(args.country)) or sys.exit('Error adding country code')

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
if args.verbose:
    print('Setting up web server...')
#Install nginx on Raspberry Pi:
do('apt install nginx -y') or sys.exit('Unable to install nginx')

# #Install PHP FastCGI Process Manager:
do('apt install php php-fpm php-cli -y') or sys.exit('Error: unable to install php and libapache2-mod-php')

# Enable PHP in nginx config file
conf_file = '/etc/nginx/sites-enabled/default'
replace_line('root /var/www/html;','root /var/www;',conf_file) or sys.exit('')
replace_line('index index.html index.htm index.nginx-debian.html;','index index.php index.html index.htm index.nginx-debian.html;', conf_file) or sys.exit('line not found')
uncomment_line('location ~ \\.php$', conf_file) or sys.exit('')
uncomment_line('include snippets/fastcgi-php.conf', conf_file) or sys.exit('')
uncomment_line('fastcgi_pass unix', conf_file) or sys.exit('')
replace_line('fastcgi_pass unix:/run/php/php7.3-fpm.sock;','fastcgi_pass unix:/run/php/php7.3-fpm.sock; }',conf_file) or sys.exit('')

# Install ARCHIE Pi web front page:
if args.verbose:
    print('Installing ARCHIE Pi web front end...')
do('cp -r www/. /var/www/') or sys.exit('Error copying www files to /var/www')
do('mkdir /var/www/modules') or sys.exit('mkdir failed')
do('chown -R www-data.www-data /var/www') or sys.exit('Error: unable tochange ownership of /var/www to www-data')

# Restart nginx service
do('service nginx restart') or sys.exit('Error: unable to restart nginx')

if args.verbose:
    print('ARCHIE Pi installed successfully. It can be accessed using wi-fi at: http://10.10.10.10.')

########################################################
# Step 4: Harden the install 
# Purpose: lessen the likelihood of SD card corruption
# by reducing the frequency of SD card writes
#########################################################

# Disable swap to eliminate swap writes to SD card
if args.verbose:
    print("Disabling swap...")
do('dphys-swapfile swapoff') or sys.exit('Error: swapoff failed!')
do('dphys-swapfile uninstall') or sys.exit('Error: swap uninstall failed!')
do('update-rc.d dphys-swapfile remove') or sys.exit('Error: swapfile remove failed!')
do('apt -y purge dphys-swapfile') or sys.exit('Error: could not purge swapfile')

# Disable periodic man pages indexing
if args.verbose:
    print("Disabling periodic man page indexing...")
do('chmod -x /etc/cron.daily/man-db') or sys.exit('Error: disable periodic man page indexing failed')
do('chmod -x /etc/cron.weekly/man-db') or sys.exit('Error: disable periodic man page indexing failed')

# Disable time sync (and associated SD card writes) since our access point has no internet
if args.verbose:
    print("Disabling time sync...")
do('systemctl disable systemd-timesyncd.service') or sys.exit('Error: timesync diasable error')

# Mount /boot partition in read-only mode
replace_line('/boot           vfat    defaults','/boot           vfat    ro','/etc/fstab')

# Increase commit time on / partition to reduce frequency of SD card writes
replace_line('defaults,noatime','defaults,noatime,commit=60','/etc/fstab')

# Move log files from the SD card to a tmpfs to further reduce SD card writes
append_file('/etc/fstab','tmpfs   /var/log    tmpfs    noatime,nosuid,mode=0755,size=50M  0   0')
# nginx requires the log folder be present; create folder in the tmpfs at each startup
append_file('/var/spool/cron/crontabs/root','@reboot mkdir /var/log/nginx')
do('chmod 600 /var/spool/cron/crontabs/root') or sys.exit('Error: chmod failed')

print('DONE!')
print("Don't forget to change the default password for the user pi!")
