# $Id: seg.py 795 2014-01-24 17:05:54Z mwall $
# Copyright 2013 Matthew Wall

#==============================================================================
# SEG
#==============================================================================
# Upload data to Smart Energy Groups
# http://smartenergygroups.com/
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [[SmartEnergyGroups]]
#     token = TOKEN
#     station = station_name

import httplib
import socket
import syslog
import urllib
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'seg: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class SEG(weewx.restx.StdRESTbase):
    """Upload to a smart energy groups server."""

    _VERSION = 0.3
    _SERVER_URL = 'http://api.smartenergygroups.com/api_sites/stream'

    # Types and formats of the data to be published:        weewx  seg default
    _FORMATS = {'barometer'   : 'barometric_pressure %.3f', # inHg   mbar
                'outTemp'     : 'temperature %.1f',         # F      C
                'outHumidity' : 'relative_humidity %.0f',   # %      %
#                'inTemp'      : 'temperature_in %.1f',     # F      C
#                'inHumidity'  : 'humidity_in %03.0f',      # %      %
                'windSpeed'   : 'wind_speed %.2f',          # mph    m/s
                'windDir'     : 'wind_direction %03.0f',    # compass degree
                'windGust'    : 'wind_gust %.2f',           # mph    m/s
                'dewpoint'    : 'dewpoint %.1f',            # F      C
                'rain24'      : '24hr_rainfall %.2f',       # in     mm
                'hourRain'    : 'hour_rainfall %.2f',       # in     mm
                'dayRain'     : 'day_rainfall %.2f',        # in     mm
                'radiation'   : 'illuminance %.2f',         # W/m^2  W/m^2
                'UV'          : 'UV %.2f'}                  # number

    # unit conversions
    _UNITS = {'barometer' : ['group_pressure','inHg','mbar'],
              'outTemp'   : ['group_temperature','degree_F','degree_C'],
              'windSpeed' : ['group_speed','mile_per_hour','meter_per_second'],
              'windGust'  : ['group_speed','mile_per_hour','meter_per_second'],
              'dewpoint'  : ['group_temperature','degree_F','degree_C'],
              'rain24'    : ['group_rain','inch','mm'],
              'hourRain'  : ['group_rain','inch','mm'],
              'dayRain'   : ['group_rain','inch','mm'] }

    def __init__(self, engine, config_dict):
        """Initialize for upload to SEG.

        token: unique token
        [Required]
        
        station: station identifier - the seg node
        [Required]

        url: URL of the server
        [Optional. Default is the smart energy groups site]
        """
        super(SEG, self).__init__(engine, config_dict)
        try:
            site_dict = config_dict['SmartEnergyGroups']
            self.station = site_dict['station']
            self.token   = site_dict['token']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.server_url = site_dict.get('url', self._SERVER_URL)

        self.archive_queue = Queue.Queue()
        self.archive_thread = SEGThread(self.archive_queue, site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to SmartEnergyGroups")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class SEGThread(weewx.restx.RESTThread):
    def __init__(self, queue, site_dict):
        super(SEGThread, self).__init__('SEG', queue, site_dict)
        self.skip_upload = to_bool(site_dict.get('skip_upload', False))

    def process_record(self, record, archive):
        r = self.get_record(record, archvie)
        data = self.get_data(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(self.server_url, data)
        req.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        req.get_method = lambda: 'PUT'
        self.post_with_retries(req)

    def check_response(self, response):
        txt = response.read()
        if txt.find('(status ok)') < 0:
            raise weewx.restful.FailedPost("Server returned '%s'" % txt)

    def get_data(self, record):
        elements = []
        for k in SEG._FORMATS:
            v = record[k]
            if v is not None:
                if k in SEG._UNITS:
                    v = self._convert(v, SEG._UNITS[k][0],
                                      SEG._UNITS[k][1], SEG._UNITS[k][2])
                s = SEG._FORMATS[k] % v
                elements.append('(%s)' % s)
        if len(elements) == 0:
            return None
        node = urllib.quote_plus(self.station)
        elements.insert(0, '(node %s %s ' % (node, time_ts))
        elements.append(')')
        elements.insert(0, 'data_post=(site %s ' % self.token)
        elements.append(')')
        data = ''.join(elements)
        logdbg('data: %s' % data)
        return data

    def _convert(self, value, group, from_units, to_units):
        vt = (value, from_units, group)
        return weewx.units.convert(vt, to_units)[0]
