# $Id: owm.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# OpenWeatherMap.org
#==============================================================================
# Upload data to OpenWeatherMap
#  http://openweathermap.org
#
# Thanks to Antonio Burriel for the dewpoint, longitude, and radiation fixes.
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[OpenWeatherMap]]
#     username = OWM_USERNAME
#     password = OWM_PASSWORD
#     station_name = STATION_NAME

import base64
import httplib
import socket
import syslog
import time
import urllib
import urllib2

import weewx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'owm: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'OpenWeatherMap'

class OpenWeatherMap(weewx.restx.StdRESTbase):
    """Upload using the OpenWeatherMap protocol.

    The OpenWeatherMap api does not include timestamp, so we can only upload
    the latest observation.
    """

    _VERSION = 0.3
    _SERVER_URL = 'http://openweathermap.org/data/post'
    _DATA_MAP = {
        'wind_dir':   ('windDir',     '%.0f', 1.0, 0.0), # degrees
        'wind_speed': ('windSpeed',   '%.1f', 0.2777777777, 0.0), # m/s
        'wind_gust':  ('windGust',    '%.1f', 0.2777777777, 0.0), # m/s
        'temp':       ('outTemp',     '%.1f', 1.0, 0.0), # C
        'humidity':   ('outHumidity', '%.0f', 1.0, 0.0), # percent
        'pressure':   ('barometer',   '%.3f', 1.0, 0.0), # mbar?
        'rain_1h':    ('hourRain',    '%.2f', 10.0, 0.0), # mm
        'rain_24h':   ('rain24',      '%.2f', 10.0, 0.0), # mm
        'rain_today': ('dayRain',     '%.2f', 10.0, 0.0), # mm
        'snow':       ('snow',        '%.2f', 10.0, 0.0), # mm
        'lum':        ('radiation',   '%.2f', 1.0, 0.0), # W/m^2
        'dewpoint':   ('dewpoint',    '%.1f', 1.0, 273.15), # K
        'uv':         ('UV',          '%.2f', 1.0, 0.0),
        }
    
    def __init__(self, engine, config_dict):
        """Initialize for posting data.

        username: OpenWeatherMap username
        [Required]

        password: OpenWeatherMap password
        [Required]

        station_name: station name
        [Required]

        interval: The interval in seconds between posts.
        [Optional.  Default is 300]

        max_tries: Maximum number of tries before giving up
        [Optional.  Default is 3]

        latitude: Station latitude
        [Required]

        longitude: Station longitude
        [Required]

        altitude: Station altitude
        [Required]
        
        server_url: Base URL for the server
        [Required]
        """
        super(OpenWeatherMap, self).__init__(engine, config_dict)        
        try:
            d = config_dict[_SERVICE_NAME]
            self.username = d['username']
            self.password = d['password']
            self.station_name = d['station_name']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = d.get('server_url', self._SERVER_URL)
        self.latitude = float(d.get('latitude', engine.stn_info.latitude_f))
        self.longitude = float(d.get('longitude', engine.stn_info.longitude_f))
        self.altitude = float(d.get('altitude',engine.stn_info.altitude_vt[0]))

        self.archive_queue = Queue.Queue()
        self.archive_thread = OpenWeatherMapThread(self.archive_queue, d)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to OpenWeatherMap")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class OpenWeatherMapThread(weewx.restx.RESTThread):
    def __init__(self, queue, owm_dict):
        super(OpenWeatherMapThread, self).__init__(_SERVICE_NAME, queue, owm_dict)
        self.skip_upload = to_bool(d.get('skip_upload', False))

    def process_record(self, record, archive):
        r = self.get_record(record, archvie)
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(self.server_url, urllib.urlencode(data))
        req.get_method = lambda: 'POST'
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        b64s = base64.encodestring('%s:%s' % (self.username, self.password)).replace('\n', '')
        req.add_header("Authorization", "Basic %s" % b64s)
        self.post_with_retries(req)

    def get_data(self, record):
        # put everything into the right units
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)

        # put data into expected scaling, structure, and format
        values = {}
        values['name'] = self.station_name
        values['lat']  = str(self.latitude)
        values['long'] = str(self.longitude)
        values['alt']  = str(self.altitude) # meter
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                v = record[rkey] * self._DATA_MAP[key][2] + self._DATA_MAP[key][3]
                values[key] = self._DATA_MAP[key][1] % v

        logdbg('data: %s' % values)
        return values
