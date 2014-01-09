# installer for the computer monitor extension
# $Id$

from setup import Installer

def loader():
    return ComputerMonitorInstaller()

class ComputerMonitorInstaller(Installer):
    def __init__(self):
        super(Installer, self).__init__(
            version="0.3",
            name='cmon',
            description='An extension to monitor computer health.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'ComputerMonitor': {
                    'database': 'computer_sqlite',
                    'max_age': 2592000 },
                'Databases': {
                    'computer_sqlite' : {
                        'root': '%(WEEWX_ROOT)s',
                        'database': 'archive/computer.sdb',
                        'driver': 'weedb.sqlite' }},
                'Engines': {
                    'WxEngine': {
                        'service_list': 'user.cmon.ComputerMonitor' }}},
            data_files=[('bin/user',
                         ['bin/user/cmon.py'])]
            )
