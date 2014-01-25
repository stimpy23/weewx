# $Id: xively.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# Xively
#==============================================================================
# Upload data to Xively (aka COSM, aka Pachube)
# https://xively.com/
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[Xively]]
#     token = TOKEN
#     feed = FEED_ID
#     station = station_name

import httplib
import socket
import syslog
import time
import urllib
import urllib2

import weewx
import weewx.restx
from weeutil.weeutil import to_bool

try:
    import cjson as json
    # XXX: maintain compatibility w/ json module
    setattr(json, 'dumps', json.encode)
    setattr(json, 'loads', json.decode)
except Exception, e:
    try:
        import simplejson as json
    except Exception, e:
        import json

def logmsg(level, msg):
    syslog.syslog(level, 'xively: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'Xively'

class Xively(weewx.restx.StdRESTbase):
    """Upload to a xively server."""

    _VERSION = 0.3
    _SERVER_URL = 'http://api.cosm.com/v2/feeds'

    # Types and formats of the data to be published:
    _FORMATS = {'barometer'   : 'barometer %.3f',        # inHg
                'outTemp'     : 'temperature_out %.1f',  # F
                'outHumidity' : 'humidity_out %03.0f',   # %
#                'inTemp'      : 'temperature_in %.1f',  # F
#                'inHumidity'  : 'humidity_in %03.0f',   # %
                'windSpeed'   : 'windSpeed %.2f',        # mph
                'windDir'     : 'windDir %03.0f',        # compass degree
                'windGust'    : 'windGust %.2f',         # mph
                'dewpoint'    : 'dewpoint %.1f',         # F
                'rain24'      : 'rain24 %.2f',           # in
                'hourRain'    : 'hourRain %.2f',         # in
                'dayRain'     : 'dayRain %.2f',          # in
                'radiation'   : 'radiation %.2f',        # W/m^2
                'UV'          : 'UV %.2f'}               # number

    def __init__(self, engine, config_dict):
        """Initialize for uploading to Xively.

        token: unique token
        [Required]

        feed: the feed name
        [Required]

        station: station identifier
        [Optional. Default is None]

        url: URL of the server
        [Optional. Default is the xively site]
        """
        super(Xively, self).__init__(engine, config_dict)
        try:
            site_dict = config_dict[_SERVICE_NAME]
            self.feed  = site_dict['feed']
            self.token = site_dict['token']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = site_dict.get('url', self._SERVER_URL)
        self.station = site_dict.get('station', None)

        self.archive_queue = Queue.Queue()
        self.archive_thread = XivelyThread(self.archive_queue, site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to Xively")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class XivelyThread(weewx.restx.RESTThread):
    def __init__(self, queue, site_dict):
        super(XivelyThread, self).__init__(_SERVICE_NAME, queue, site_dict)
        self.skip_upload = to_bool(site_dict.get('skip_upload', False))

    def process_record(self, record, archive):
        r = self.augment_record(record, archvie)
        url = self.get_url()
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url, data)
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        req.add_header("X-PachubeApiKey", self.token)
        req.get_method = lambda: 'PUT'
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if txt != '':
            raise weewx.restx.FailedPost(txt)

    def get_url(self):
        url = '%s/%s' % (self.server_url, self.feed)
        logdbg('url: %s' % url)
        return url
        
    def get_data(self, record):
        station = urllib.quote_plus(self.station) \
            if self.station is not None else None
        tstr = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time_ts))
        streams = {}
        for k in Xively._FORMATS:
            v = record[k]
            if v is not None:
                dskey = '%s_%s' % (station, k) if station is not None else k
                if not dskey in streams:
                    streams[dskey] = {'id':dskey, 'datapoints':[]}
                dp = {'at':tstr, 'value':v}
                streams[dskey]['datapoints'].append(dp)
        if len(streams.keys()) == 0:
            return None
        data = {
            'version':'1.0.0',
            'datastreams':[]
            }
        for k in streams.keys():
            data['datastreams'].append(streams[k])
        data = json.dumps(data)
        logdbg('data: %s' % data)
        return data
