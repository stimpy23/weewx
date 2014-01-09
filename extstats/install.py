# installer for the extended statistics
# $Id$

from setup import Installer

def loader():
    return ExtendedStatisticsInstaller()

class ComputerMonitorInstaller(Installer):
    def __init__(self):
        super(Installer, self).__init__(
            version="0.1",
            name='extstats',
            description='An extension for extended statistics.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'StdReport': {
                    'extstats': {
                        'skin':'extstats',
                        'HTML_ROOT':'extstats' }}},
            data_files=[('bin/user',
                         ['bin/user/extstats.py']),
                        ('skins/extstats',
                         ['skins/extstats/skin.conf',
                          'skins/extstats/index.html.tmpl'])]
            )
