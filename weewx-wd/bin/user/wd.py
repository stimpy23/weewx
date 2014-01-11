import weewx
import math
from weewx.wxengine import StdService
from weewx.accum import BaseAccum, WXAccum, VecStats, OutOfSpan
from datetime import datetime

class WD(StdService):
    
    def __init__(self, engine, config_dict):
        StdService.__init__(self, engine, config_dict)
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        try:
            if event.packet['windGustDir'] is None:
               event.packet['windGustDir'] = 0
            if event.packet['windDir'] is None:
               event.packet['windDir'] = 0
            if event.packet['usUnits'] is weewx.US:
                event.packet['extraTemp1'] = ((event.packet['outTemp']-32)*5/9+5/9*(6.112*10**(7.5*(event.packet['outTemp']-32)*5/9/(237.7+(event.packet['outTemp']-32)*5/9))*event.packet['outHumidity']/100-10))*9/5+32
                event.packet['extraTemp2'] = ((event.packet['outTemp']-32)*5/9+(0.33*event.packet['outHumidity']/100*6.105*math.exp(17.27*(event.packet['outTemp']-32)*5/9/(237.7+(event.packet['outTemp']-32)*5/9)))-(0.7*event.packet['windSpeed']*0.44704)-4)*9/5+32
            else:
                event.packet['extraTemp1'] = event.packet['outTemp']+5/9*(6.112*10**(7.5*event.packet['outTemp']/(237.7+event.packet['outTemp']))*event.packet['outHumidity']/100-10)
                event.packet['extraTemp2'] = event.packet['outTemp']+(0.33*event.packet['outHumidity']/100*6.105*math.exp(17.27*event.packet['outTemp']/(237.7+event.packet['outTemp'])))-(0.7*event.packet['windSpeed']*5/18)-4
        except:
            pass
            
    def new_archive_record(self, event):
        try:
            if event.record['windGustDir'] is None:
               event.record['windGustDir'] = 0
            if event.record['windDir'] is None:
               event.record['windDir'] = 0
            if event.record['usUnits'] is weewx.US:
                event.record['extraTemp1'] = ((event.record['outTemp']-32)*5/9+5/9*(6.112*10**(7.5*(event.record['outTemp']-32)*5/9/(237.7+(event.record['outTemp']-32)*5/9))*event.record['outHumidity']/100-10))*9/5+32
                event.record['extraTemp2'] = ((event.record['outTemp']-32)*5/9+(0.33*event.record['outHumidity']/100*6.105*math.exp(17.27*(event.record['outTemp']-32)*5/9/(237.7+(event.record['outTemp']-32)*5/9)))-(0.7*event.record['windSpeed']*0.44704)-4)*9/5+32
            else:
                event.record['extraTemp1'] = event.record['outTemp']+5/9*(6.112*10**(7.5*event.record['outTemp']/(237.7+event.record['outTemp']))*event.record['outHumidity']/100-10)
                event.record['extraTemp2'] = event.record['outTemp']+(0.33*event.record['outHumidity']/100*6.105*math.exp(17.27*event.record['outTemp']/(237.7+event.record['outTemp'])))-(0.7*event.record['windSpeed']*5/18)-4
        except:
            pass
            
class WDWXAccum(WXAccum):
    """Subclass of WXAccum to add custom stats to accumulator."""

    def addRecord(self, record, add_hilo=True):
        """Custom method to include 'windAv', 'outTempDay' and 'outTempNight' when adding
        a record to the accumulator. The record must have keys 'dateTime' and 'usUnits'.
        This is a weather-specific version."""
        
        # Check to see if the record is within my observation timespan 
        if not self.timespan.includesArchiveTime(record['dateTime']):
            raise OutOfSpan, "Attempt to add out-of-interval record"

        # This is pretty much like the loop in my superclass's version, except
        # that wind is treated as a vector.
        for obs_type in record:
            if obs_type in ['windDir', 'windGust', 'windGustDir']:
                continue
            elif obs_type == 'windSpeed':
                self._add_value((record['windSpeed'], record.get('windDir')), 'wind', record['dateTime'], add_hilo)
                if add_hilo:
                    self['wind'].addHiLo((record.get('windGust'), record.get('windGustDir')), record['dateTime'])
                # add windSpeed observation 'windAv' to accumulator
                if 'interval' in record:
                    self._add_value((record['windSpeed'], record.get('windDir')), 'windAv', record['dateTime'], add_hilo)
            elif obs_type == 'outTemp':
                # add 'outTemp' as normal
                self._add_value(record[obs_type], obs_type, record['dateTime'], add_hilo)
                # check if record covers daytime (6AM to 6PM) and if so add 'outTemp' to 'outTempDay'
                # remember record timestamped 6AM belongs in the night time
                if datetime.fromtimestamp(record['dateTime']-1).hour < 6 or datetime.fromtimestamp(record['dateTime']-1).hour > 17:
                    self._add_value(record['outTemp'], 'outTempNight', record['dateTime'], add_hilo)
                    self._add_value(None, 'outTempDay', record['dateTime'], add_hilo)
                else: # if its from the day time it must be night
                    self._add_value(record['outTemp'], 'outTempDay', record['dateTime'], add_hilo)
                    self._add_value(None, 'outTempNight', record['dateTime'], add_hilo)
            else:
                self._add_value(record[obs_type], obs_type, record['dateTime'], add_hilo)
                
    def _init_type(self, obs_type):
        """Custom method to initialise observation type."""

        # Do nothing if this type has already been initialized:
        if obs_type in self:
            return
        elif obs_type == 'wind':
            # Observation 'wind' requires a special vector accumulator
            self['wind'] = VecStats()
        elif obs_type == 'windAv': # Custom observation 'windAv'
            # Observation 'windAv' requires a special vector accumulator
            self['windAv'] = VecStats()
        else:
            # Otherwise, pass on to my base class
            return BaseAccum._init_type(self, obs_type)
