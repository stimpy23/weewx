# installer for the weewx-wd extension
# $Id$

from setup import Installer

def loader():
    return WeewxWDInstaller()

class WeewxWDInstaller(Installer):
    def __init__(self):
        super(Installer, self).__init__(
            version="0.9",
            name='cmon',
            description='Extension to drive WDL and Saratoga templates.',
            author="ozgreg",
            author_email="ozgreg",
            config={
                'StdReport': {
                    'clientraw': {
                        'skin':'clientraw',
                        'HTML_ROOT':'wd' },
                    'testtags': {
                        'skin':'testtags',
                        'HTML_ROOT':'wd' }},
                'Engines': {
                    'WxEngine': {
                        'service_list': 'user.wd.WD, user.wdarchive.WDArchive' }}},
            data_files=[('bin/user',
                         ['bin/user/imageStackedWindRose.py',
                          'bin/user/wd.py',
                          'bin/user/wdSearchX.py',
                          'bin/user/wdarchive.py',
                          'bin/user/wdtaggedstats.py']),
                        ('skins/clientraw',
                         ['skins/clientraw/clientraw.txt.tmpl',
                          'skins/clinetraw/clientrawdaily.txt.tmpl',
                          'skins/clinetraw/clientrawextra.txt.tmpl',
                          'skins/clinetraw/clientrawhour.txt.tmpl',
                          'skins/clinetraw/customclientraw.txt.tmpl',
                          'skins/clientraw/skin.conf']),
                        ('skins/testtags',
                         ['skins/testtags/skin.conf',
                          'skins/testtags/testtags.php.tmpl']),
                        ('skins/wd',
                         ['skins/wd/skin.conf'])]
            )

# FIXME: merge service_list
# FIXME: modify schemas.py
# FIXME: modify extensions.py
