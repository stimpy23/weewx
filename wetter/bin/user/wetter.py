# $Id: wetter.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# wetter.com
#==============================================================================
# Upload data to wetter.com
#  http://wetter.com
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [Wetter]
#     username = USERNAME
#     password = PASSWORD

import httplib
import socket
import syslog
import time
import urllib
import urllib2

from weewx.restx import RESTThread, StdRESTbase, FailedPost
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'wetter: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'Wetter'

class Wetter(StdRESTbase):
    """Upload using the wetter.com protocol."""

    _VERSION = 0.3
    _SERVER_URL = 'http://www.wetterarchiv.de/interface/http/input.php'
    _DATA_MAP = {'windrichtung': ('windDir',     '%.0f', 1.0), # degrees
                 'windstaerke':  ('windSpeed',   '%.1f', 0.2777777777), # m/s
                 'temperatur':   ('outTemp',     '%.1f', 1.0), # C
                 'feuchtigkeit': ('outHumidity', '%.0f', 1.0), # percent
                 'luftdruck':    ('barometer',   '%.3f', 1.0), # mbar?
                 'niederschlagsmenge': ('hourRain',    '%.2f', 10.0), # mm
                 }

    def __init__(self, engine, config_dict):
        """Initialize for posting data to wetter.com.

        username: username
        [Required]

        password: password
        [Required]

        interval: The interval in seconds between posts.
        [Optional.  Default is 300]

        max_tries: Maximum number of tries before giving up
        [Optional.  Default is 3]
        
        server_url: Base URL for the server
        [Required]
        """
        super(Wetter, self).__init__(engine, config_dict)        
        try:
            d = config_dict[_SERVIC_NAME]
            self.username = d['username']
            self.password = d['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = d.get('server_url', self._SERVER_URL)

        self.archive_queue = Queue.Queue()
        self.archive_thread = WetterThread(self.archive_queue, d)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to wetter.com")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class WetterThread(RESTThread):
    def __init__(self, queue, site_dict):
        super(WetterThread, self).__init__(_SERVIC_NAME, queue, site_dict)
        self.skip_upload = tobool(kwargs.get('skip_upload', False))

    def process_record(self, record, archive):
        r = self.get_record(record, archvie)
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(self.server_url, urllib.urlencode(data))
        req.get_method = lambda: 'POST'
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if not txt.startswith('status=SUCCESS'):
            raise FailedPost("Server returned '%s'" % txt)

    def get_data(self, record):
        # put everything into the right units
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)

        # put data into expected scaling, structure, and format
        values = {}
        values['benutzername'] = self.username
        values['passwort'] = self.password
        values['niederschlagsmenge_zeit'] = 60
        values['datum'] = time.strftime('%Y%m%d%H%M',
                                        time.localtime(record['dateTime']))
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                v = record[rkey] * self._DATA_MAP[key][2]
                values[key] = self._DATA_MAP[key][1] % v

        logdbg('data: %s' % values)
        return values
