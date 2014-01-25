# $Id: wbug.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# WeatherBug
#==============================================================================
# Upload data to WeatherBug
# http://weather.weatherbug.com
#
# To enable this module, put this file in bin/user, add the following to
# weewx.conf, then restart weewx.
#
# [[WeatherBug]]
#     publisher_id = WEATHERBUG_ID
#     station_number = WEATHERBUG_STATION_NUMBER
#     password = WEATHERBUG_PASSWORD

import httplib
import socket
import syslog
import time
import urllib
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'wbug: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'WeatherBug'

class WeatherBug(weewx.restx.StdRESTbase):
    """Upload using the WeatherBug protocol."""

    _VERSION = 0.3
    _SERVER_URL = 'http://data.backyard2.weatherbug.com/data/livedata.aspx'
    _DATA_MAP = {'tempf':         ('outTemp',     '%.1f'), # F
                 'humidity':      ('outHumidity', '%.0f'), # percent
                 'winddir':       ('windDir',     '%.0f'), # degree
                 'windspeedmph':  ('windSpeed',   '%.1f'), # mph
                 'windgustmph':   ('windGust',    '%.1f'), # mph
                 'baromin':       ('barometer',   '%.3f'), # inHg
                 'rainin':        ('rain',        '%.2f'), # in
                 'dailyRainin':   ('dayRain',     '%.2f'), # in
                 'monthlyrainin': ('monthRain',   '%.2f'), # in
                 'tempfhi':       ('outTempMax',  '%.1f'), # F
                 'tempflo':       ('outTempMin',  '%.1f'), # F
                 'Yearlyrainin':  ('yearRain',    '%.2f'), # in
                 'dewptf':        ('dewpoint',    '%.1f')} # F

    def __init__(self, engine, config_dict):
        """Initialize for upload to WeatherBug.

        publisher_id: WeatherBug publisher identifier
        [Required]

        station_number: WeatherBug station number
        [Required]

        password: WeatherBug password
        [Required]

        latitude: Station latitude
        [Required]

        longitude: Station longitude
        [Required]
        
        server_url: Base URL for the server
        [Required]
        """
        super(WeatherBug, self).__init__(engine, config_dict)
        try:
            site_dict = config_dict[_SERVICE_NAME]
            self.latitude = float(site_dict['latitude'])
            self.longitude = float(site_dict['longitude'])
            self.publisher_id = site_dict['publisher_id']
            self.station_number = site_dict['station_number']
            self.password = site_dict['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = site_dict.get('url', self._SERVER_URL)

        self.archive_queue = Queue.Queue()
        self.archive_thread = WeatherBugThread(self.archive_queue, site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to WeatherBug")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class WeatherBugThread(weewx.restx.RESTThread):
    def __init__(self, queue, site_dict):
        super(WeatherBugThread, self).__init__(_SERVICE_NAME, queue, site_dict)
        self.skip_upload = to_bool(site_dict.get('skip_upload', False))

    def augment_record(self, record, archive):
        """Add rainRate to the record."""
        r = RESTThread.augment_record(record, archive)
        ts = r['dateTime']
        rr = archive.getSql('select rainRate from archive where dateTime=?', (ts,))
        r['rainRate'] = rr
        return r

    def process_record(self, record, archive):
        r = self.augment_record(record, archvie)
        url = self.get_url(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url)
        self.post_with_retries(req)

    def check_response(self, response):
        if not line.startswith('Successfully Received'):
            raise weewx.restx.FailedPost("Server response: %s" % line)

    def get_url(self, record):
        # put everything into the right units and scaling
        if record['usUnits'] != weewx.US:
            converter = weewx.units.StdUnitConverters[weewx.US]
            record = converter.convertDict(record)

        # put data into expected structure and format
        values = { 'action':'live' }
        values['softwaretype'] = 'weewx_%s' % weewx.__version__
        values['ID'] = self.publisher_id
        values['Num'] = self.station_number
        values['Key'] = self.password
        time_tt = time.gmtime(record['dateTime'])
        values['dateutc'] = time.strftime("%Y-%m-%d %H:%M:%S", time_tt)
        for key in self._DATA_MAP:
            rkey = self._DATA_MAP[key][0]
            if record.has_key(rkey) and record[rkey] is not None:
                values[key] = self._DATA_MAP[key][1] % record[rkey]
        url = self.server_url + '?' + urllib.urlencode(values)
        logdbg('url: %s' % url)
        return url
