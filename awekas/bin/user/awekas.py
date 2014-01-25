# $Id: awekas.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# AWEKAS
#==============================================================================
# Upload data to AWEKAS - Automatisches WEtterKArten System
# http://www.awekas.at
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [AWEKAS]
#     username = AWEKAS_USERNAME
#     password = AWEKAS_PASSWORD

import hashlib
import httplib
import socket
import syslog
import time
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'awekas: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

_SERVICE_NAME = 'AWEKAS'

class AWEKAS(weewx.restx.StdRESTbase):
    """Upload using the AWEKAS protocol.

    The AWEKAS server expects a single string of values delimited by
    semicolons.  The position of each value matters, for example position 1
    is the awekas username and position 2 is the awekas password.

    Positions 1-25 are defined for the basic API:

    Pos1: user (awekas username)
    Pos2: password (awekas password MD5 Hash)
    Pos3: date (dd.mm.yyyy) (varchar)
    Pos4: time (hh:mm) (varchar)
    Pos5: temperature (C) (float)
    Pos6: humidity (%) (int)
    Pos7: air pressure (hPa) (float)
    Pos8: precipitation (rain at this day) (float)
    Pos9: wind speed (km/h) float)
    Pos10: wind direction (degree) (int)
    Pos11: weather condition (int)
            0=clear warning
            1=clear
            2=sunny sky
            3=partly cloudy
            4=cloudy
            5=heavy cloundy
            6=overcast sky
            7=fog
            8=rain showers
            9=heavy rain showers
           10=light rain
           11=rain
           12=heavy rain
           13=light snow
           14=snow
           15=light snow showers
           16=snow showers
           17=sleet
           18=hail
           19=thunderstorm
           20=storm
           21=freezing rain
           22=warning
           23=drizzle
           24=heavy snow
           25=heavy snow showers
    Pos12: warning text (varchar)
    Pos13: snow high (cm) (int) if no snow leave blank
    Pos14: language (varchar)
           de=german; en=english; it=italian; fr=french; nl=dutch
    Pos15: tendency (int)
           -2 = high falling
           -1 = falling
            0 = steady
            1 = rising
            2 = high rising
    Pos16. wind gust (km/h) (float)
    Pos17: solar radiation (W/m^2) (float) 
    Pos18: UV Index (float)
    Pos19: brightness (LUX) (int)
    Pos20: sunshine hours today (float)
    Pos21: soil temperature (degree C) (float)
    Pos22: rain rate (mm/h) (float)
    Pos23: software flag NNNN_X.Y, for example, WLIP_2.15
    Pos24: longitude (float)
    Pos25: latitude (float)

    positions 26-111 are defined for API2
        """

    _VERSION = 0.5
    _SERVER_URL = 'http://data.awekas.at/eingabe_pruefung.php'
    _FORMATS = {'barometer'   : '%.3f',
                'outTemp'     : '%.1f',
                'outHumidity' : '%.0f',
                'windSpeed'   : '%.1f',
                'windDir'     : '%.0f',
                'windGust'    : '%.1f',
                'dewpoint'    : '%.1f',
                'hourRain'    : '%.2f',
                'dayRain'     : '%.2f',
                'radiation'   : '%.2f',
                'UV'          : '%.2f',
                'rainRate'    : '%.2f'}

    def __init__(self, engine, config_dict):
        """Initialize for posting data to AWEKAS.

        username: AWEKAS user name
        [Required]

        password: AWEKAS password
        [Required]

        language: Possible values include de, en, it, fr, nl
        [Required.  Default is de]

        latitude: Station latitude
        [Required]

        longitude: Station longitude
        [Required]
        
        server_url: Base URL for the AWEKAS server
        [Required]

        interval: The interval in seconds between posts.
        AWEKAS requests that uploads happen no more often than 5 minutes, so
        this should be set to no less than 300.
        [Optional.  Default is 300]
        """
        super(AWEKAS, self).__init__(engine, config_dict)
        try:
            d = config_dict[_SERVICE_NAME]
            self.username = d['username']
            self.password = d['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = d.get('server_url', self._SERVER_URL)
        self.latitude = float(d.get('latitude', engine.stn_info.latitude_f))
        self.longitude = float(d.get('longitude', engine.stn_info.longitude_f))
        self.language = d.get('language', 'de')

        self.archive_queue = Queue.Queue()
        self.archive_thread = AWEKASThread(self.archive_queue, d)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to AWEKAS")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class AWEKASThread(weewx.restx.RESTThread):
    def __init__(self, queue, site_dict):
        super(AWEKASThread, self).__init__(_SERVICE_NAME, queue, site_dict)
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
        for line in response:
            if not line.startswith('OK'):
                raise weewx.restx.FailedPost("server returned '%s'" % line)

    def get_url(self, record):
        # put everything into the right units and scaling
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)
        if record.has_key('dayRain') and record['dayRain'] is not None:
            record['dayRain'] = record['dayRain'] * 10
        if record.has_key('rainRate') and record['rainRate'] is not None:
            record['rainRate'] = record['rainRate'] * 10

        # assemble an array of values in the proper order
        values = [self.username]
        m = hashlib.md5()
        m.update(self.password)
        values.append(m.hexdigest())
        time_tt = time.gmtime(record['dateTime'])
        values.append(time.strftime("%d.%m.%Y", time_tt))
        values.append(time.strftime("%H:%M", time_tt))
        values.append(self._format(record, 'outTemp')) # C
        values.append(self._format(record, 'outHumidity')) # %
        values.append(self._format(record, 'barometer')) # mbar
        values.append(self._format(record, 'dayRain')) # mm?
        values.append(self._format(record, 'windSpeed')) # km/h
        values.append(self._format(record, 'windDir'))
        values.append('') # weather condition
        values.append('') # warning text
        values.append('') # snow high
        values.append(self.language)
        values.append('') # tendency
        values.append(self._format(record, 'windGust')) # km/h
        values.append(self._format(record, 'radiation')) # W/m^2
        values.append(self._format(record, 'UV')) # uv index
        values.append('') # brightness in lux
        values.append('') # sunshine hours
        values.append('') # soil temperature
        values.append(self._format(record, 'rainRate')) # mm/h
        values.append('weewx_%s' % weewx.__version__)
        values.append(str(self.longitude))
        values.append(str(self.latitude))

        valstr = ';'.join(values)
        url = self.server_url + '?val=' + valstr
        logdbg('url: %s' % url)
        return url

    def _format(self, record, label):
        if record.has_key(label) and record[label] is not None:
            if AWEKAS._FORMATS.has_key(label):
                return AWEKAS._FORMATS[label] % record[label]
            return str(record[label])
        return ''
