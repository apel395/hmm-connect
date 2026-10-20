"""Install the daily EC2 job. Run with sudo from the persistent backend worktree."""
import argparse
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    root=args.app_dir.resolve();python=Path(sys.executable).absolute()
    if os.geteuid()!=0:parser.error('Run this installer with sudo')
    if not (root/'scripts/run_purchasing_retention.py').is_file() or not (root/'.env').exists():
        parser.error('Choose a persistent backend worktree containing the script and .env')
    if str(root).startswith('/tmp/') or not re.fullmatch(r'/[A-Za-z0-9_./-]+',str(root)) or not re.fullmatch(r'/[A-Za-z0-9_./-]+',str(python)):
        parser.error('Use a persistent path without spaces or special characters')
    owner=pwd.getpwuid(root.stat().st_uid).pw_name
    service=f'''[Unit]
Description=MMH purchasing document age cleanup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={owner}
WorkingDirectory={root}
ExecStart={python} {root}/scripts/run_purchasing_retention.py --apply
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
PrivateTmp=true
TimeoutStartSec=1800
'''
    timer='''[Unit]
Description=MMH daily purchasing cleanup at 03:00 Jakarta

[Timer]
OnCalendar=*-*-* 03:00:00 Asia/Jakarta
Persistent=true
Unit=mmh-purchasing-retention.service

[Install]
WantedBy=timers.target
'''
    folder=Path('/etc/systemd/system')
    (folder/'mmh-purchasing-retention.service').write_text(service)
    (folder/'mmh-purchasing-retention.timer').write_text(timer)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','mmh-purchasing-retention.timer'],check=True)
    print('Installed: daily purchasing age cleanup at 03:00 Asia/Jakarta.')

if __name__=='__main__':main()
