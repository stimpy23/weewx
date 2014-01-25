# $Id: emoncms.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# EmonCMS
#==============================================================================
# Upload data to EmonCMS
# http://emoncms.org
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[EmonCMS]]
#     token = TOKEN

import httplib
import socket
import syslog
import urllib
import urllib2

import weewx
import weewx.restx
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'emoncms: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'EmonCMS'

class EmonCMS(weewx.restx.StdRESTbase):
    """Upload to an emoncms server."""

    _VERSION = 0.4
    _SERVER_URL = 'http://emoncms.org/input/post'

    # Types and formats of the data to be published:
    _FORMATS = {'barometer'   : 'barometer_inHg:%.3f',
                'outTemp'     : 'outTemp_F:%.1f',
                'outHumidity' : 'outHumidity:%03.0f',
#                'inTemp'      : 'inTemp_F:%.1f',
#                'inHumidity'  : 'inHumidity:%03.0f',
                'windSpeed'   : 'windSpeed_mph:%.2f',
                'windDir'     : 'windDir:%03.0f',
                'windGust'    : 'windGust_mph:%.2f',
                'dewpoint'    : 'dewpoint_F:%.1f',
                'rain24'      : 'rain24_in:%.2f',
                'hourRain'    : 'hourRain_in:%.2f',
                'dayRain'     : 'dayRain_in:%.2f',
                'radiation'   : 'radiation:%.2f',
                'UV'          : 'UV:%.2f'}

    def __init__(self, engine, config_dict):
        """Initialize for posting to emoncms.

        token: unique token
        [Required]
        
        station: station identifier
        [Optional. Default is None]

        url: URL of the server
        [Optional. Default is the emoncms.org site]
        
        max_tries: maximum number of tries before giving up
        [Optional. Default is 3]

        timeout: timeout in seconds
        [Optional. Default is 60]

        skip_upload: debugging option to display data but do not upload
        [Optional. Default is False]
        """
        super(EmonCMS, self).__init__(engine, config_dict)        
        try:
            site_dict = config_dict[_SERVICE_NAME]
            self.token = site_dict['token']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = site_dict.get('url', self._SERVER_URL)
        self.station = site_dict.get('station', None)

        self.archive_queue = Queue.Queue()
        self.archive_thread = EmonCMSThread(self.archive_queue, site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to EmonCMS")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class EmonCMSThread(weewx.restx.RESTThread):
    def __init__(self, queue, site_dict):
        super(EmonCMSThread, self).__init__(_SERVICE_NAME, queue, site_dict)
        self.skip_upload= to_bool(site_dict.get('skip_upload', False))

    def process_record(self, record, archive):
        r = self.get_record(record, archvie)
        url = self.get_url(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url)
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if txt != 'ok' :
            raise weewx.restful.FailedPost(txt)

    def get_url(self, record):
        prefix = ''
        if self.station is not None:
            prefix = '%s_' % urllib.quote_plus(self.station)
        data = []
        for k in EmonCMS._FORMATS:
            v = record[k]
            if v is not None:
                s = EmonCMS._FORMATS[k] % v
                data.append('%s%s' % (prefix, s))
        url = '%s?apikey=%s&time=%s&json={%s}' % (
            self.server_url, self.token, time_ts, ','.join(data))
        logdbg('url: %s' % url)
        return url
