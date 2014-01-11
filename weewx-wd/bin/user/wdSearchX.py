import datetime
import time
import user.wdtaggedstats
import weewx
import weeutil.weeutil
import user.wdtaggedstats
import weewx.almanac

from weewx.cheetahgenerator import SearchList
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan, archiveDaySpan, genMonthSpans
from weewx.units import ValueHelper, getStandardUnitType
from datetime import date

class wdMonthStats(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def getMonthAveragesHighs(self, valid_timespan, archivedb, statsdb):
        #######
        # Function to calculate alltime monthly:
        #  - average rainfall
        #  - record high temp
        #  - record low temp
        #  - average temp
        # Results are calculated using daily data from stats database. Average
        # rainfall is calculated by summing rainfall over each Jan, Feb...Dec
        # then averaging these totals over the number of Jans, Febs... Decs
        # in our data. Average temp
        # Record high and low temps are max and min over all of each month.
        # Partial months at start and end of our data are ignored. Assumes
        # rest of our data is contiguous.
        #
        # Returned values are lists of ValueHelpers representing results for
        # Jan, Feb thru Dec. Months that have no data are returned as None.
        #######

        def get_first_day(dt, d_years=0, d_months=0):
            #######
            # Function to return date object holding 1st of month containing dt
            # d_years, d_months are offsets that may be applied to dt
            #######

            # Get year number and month number applying offset as required
            _y, _m = dt.year + d_years, dt.month + d_months
            # Calculate actual month number taking into account EOY rollover
            _a, _m = divmod(_m-1, 12)
            # Calculate and return date object
            return date(_y+_a, _m+1, 1)

        # Get timestamp for our first (earliest) record
        _start_ts = archivedb.firstGoodStamp()
        # Get timestamp for our last (most recent) record
        _end_ts = archivedb.lastGoodStamp()
        # Get archive interval
        current_rec = archivedb.getRecord(valid_timespan.stop)
        _interval = current_rec['interval']
        # Get time object for midnight
        _mn_time = datetime.time(0)
        # Determine timestamp of first record we will use. Will be midnight on
        # first of a month. We are using stats data to calculate our results
        # and the stats datetime for each day is midnight. We have obtained our
        # starting time from archive data where the first obs of the day has a
        # datetime of (archive interval) minutes after midnight. Need to take
        # this into account when chosing our start time. Need to skip any
        # partial months data at the start of data.
        #
        # Get the datetime from our starting point timestamp
        _day_date = datetime.datetime.fromtimestamp(_start_ts)
        # If this is not the 1st of the month or if its after
        # (archive interval) after midnight on 1st then we have a partial
        # month and we need to skip to next month.
        if _day_date.day > 1 or _day_date.hour > 0 or _day_date.minute > (_interval):
            _start_ts = int(time.mktime(datetime.datetime.combine(get_first_day(_day_date,0,1),_mn_time).timetuple()))
        # If its midnight on the 1st of the month then leave it as is
        elif _day_date.day == 1 and _day_date.hour == 0 and _day_date.minute == 0:
            pass
        # Otherwise its (archive interval) past midnight on 1st so we have the
        # right day just need to set our timestamp to midnight.
        else:
            _start_ts = int(time.mktime((_day_date.year, _day_date.month,_day_date.day,0,0,0,0,0,0)))
        # Determine timestamp of last record we will use. Will be midnight on
        # last of a month. We are using stats data to calculate our average
        # and the stats datetime for each day is midnight. We have obtained our
        # starting time from archive data where the first obs of the day has a
        # datetime of (archive interval) minutes after midnight. Need to take
        # this into account when chosing our start time. Need to skip any
        # partial months data at the start of data.
        #
        # Get the datetime from our ending point timestamp
        _day_date = datetime.datetime.fromtimestamp(_end_ts)
        if _day_date.day == 1 and _day_date.hour == 0 and _day_date.minute == 0:
            pass
        else:
            _end_ts = int(time.mktime((_day_date.year, _day_date.month,1,0,0,0,0,0,0)))

        # Set up a 2D list to hold our month running total and number of months
        # so we can calculate an average
        monthRainBin = [[0 for x in range(2)] for x in range(12)]
        monthTempBin = [[0 for x in range(2)] for x in range(12)]
        # Set up lists to hold our max and min records
        monthTempMax = [None for x in range(12)]
        monthTempMin = [None for x in range(12)]
        # Loop through each month timespan between our start and end timestamps
        for month_timespan in genMonthSpans(_start_ts, _end_ts):
            # Get the total rain for the month concerned
            monthRain_tuple = statsdb.getAggregate(month_timespan, 'rain', 'sum', None)
            # Get the 'total' temp for the month concerned
            monthTemp_tuple = statsdb.getAggregate(month_timespan, 'outTemp', 'avg', None)
            # Get the max temp for the month concerend
            monthTempMax_tuple = statsdb.getAggregate(month_timespan, 'outTemp', 'max', None)
            # Get the min temp for the month concerend
            monthTempMin_tuple = statsdb.getAggregate(month_timespan, 'outTemp', 'min', None)
            # Update our total rain for that month
            monthRainBin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1][0] += monthRain_tuple[0]
            # Update our 'total' temp for that month
            monthTempBin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1][0] += monthTemp_tuple[0] * (get_first_day(datetime.datetime.fromtimestamp(month_timespan[0]).date(),0,1)-get_first_day(datetime.datetime.fromtimestamp(month_timespan[0]).date(),0,0)).days
            # If our record list holds None then the current value must be the new max
            if monthTempMax[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] == None:
                monthTempMax[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] = monthTempMax_tuple[0]
            # If the current value is greater than our record list then update the list
            elif monthTempMax_tuple[0] > monthTempMax[datetime.datetime.fromtimestamp(month_timespan[0]).month-1]:
                monthTempMax[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] = monthTempMax_tuple[0]
            # If our record list holds None then the current value must be the new min
            if monthTempMin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] == None:
                monthTempMin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] = monthTempMin_tuple[0]
            # If the current value is greater than our record list then update the list
            elif monthTempMin_tuple[0] < monthTempMin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1]:
                monthTempMin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1] = monthTempMin_tuple[0]
            # Increment our count
            monthRainBin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1][1] += 1
            # Increment our count, in this case by the number of days in the month
            monthTempBin[datetime.datetime.fromtimestamp(month_timespan[0]).month-1][1] += (get_first_day(datetime.datetime.fromtimestamp(month_timespan[0]).date(),0,1)-get_first_day(datetime.datetime.fromtimestamp(month_timespan[0]).date(),0,0)).days

        # Get our UoMs
        monthRainUnit = monthRain_tuple[1]
        monthTempUnit = monthTempMax_tuple[1]
        # Get our Groups
        monthRainGroup = monthRain_tuple[2]
        monthTempGroup = monthTempMax_tuple[2]
        # Set up a list to hold our average values
        monthRainAvg = [0 for x in range(12)]
        monthTempAvg = [0 for x in range(12)]
        # Set up lists to hold our results in ValueHelpers
        monthRainAvg_vh = [0 for x in range(12)]
        monthTempAvg_vh = [0 for x in range(12)]
        monthTempMax_vh = [0 for x in range(12)]
        monthTempMin_vh = [0 for x in range(12)]

        # Loop through each month:
        #  - calculating averages and saving as a ValueTuple
        #  - converting monthly averages, max and min ValueHelpers
        for monthNum in range (12):
            # If we have a total > 0 then calc a simple average
            if monthRainBin[monthNum][1] != 0:
                monthRainAvg[monthNum] = (monthRainBin[monthNum][0]/monthRainBin[monthNum][1], monthRainUnit, monthRainGroup)
            # If our sum == 0 and our count > 0 then set our average to 0
            elif monthRainBin[monthNum][1] > 0:
                monthRainAvg[monthNum] = (0, monthRainUnit, monthRainGroup)
            # Otherwise we must have no data for that month so set our average
            # to None
            else:
                monthRainAvg[monthNum] = (None, monthRainUnit, monthRainGroup)
            # If we have a total > 0 then calc a simple average
            if monthTempBin[monthNum][1] != 0:
                monthTempAvg[monthNum] = (monthTempBin[monthNum][0]/monthTempBin[monthNum][1], monthTempUnit, monthTempGroup)
            # If our sum == 0 and our count > 0 then set our average to 0
            elif monthTempBin[monthNum][1] > 0:
                monthTempAvg[monthNum] = (0, monthTempUnit, monthTempGroup)
            # Otherwise we must have no data for that month so set our average
            # to None
            else:
                monthTempAvg[monthNum] = (None, monthTempUnit, monthTempGroup)
            # Save our ValueTuple as a ValueHelper
            monthRainAvg_vh[monthNum] = ValueHelper(monthRainAvg[monthNum], formatter=self.generator.formatter, converter=self.generator.converter)
            monthTempAvg_vh[monthNum] = ValueHelper(monthTempAvg[monthNum], formatter=self.generator.formatter, converter=self.generator.converter)
            # Save our max/min results as ValueHelpers
            monthTempMax_vh[monthNum] = ValueHelper((monthTempMax[monthNum], monthTempUnit, monthTempGroup), formatter=self.generator.formatter, converter=self.generator.converter)
            monthTempMin_vh[monthNum] = ValueHelper((monthTempMin[monthNum], monthTempUnit, monthTempGroup), formatter=self.generator.formatter, converter=self.generator.converter)

        # Return our lists of ValueHelpers
        return monthRainAvg_vh, monthTempAvg_vh, monthTempMax_vh, monthTempMin_vh

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns month avg/max/min stats based upon archive data.

        Provides:
        - avg rain
        - avg temp
        - record high temp
        - record low temp

        for January, February,..., December

        based upon all archive data with the exception of any partial months data at
        the start and end of the database.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb
        """

        # Call getMonthAveragesHighs method to calculate average rain, temp
        # and max/min temps for each month
        monthRainAvg_vh, monthTempAvg_vh, monthTempMax_vh, monthTempMin_vh = self.getMonthAveragesHighs(valid_timespan, archivedb, statsdb)
        # Returned values are already ValueHelpers so can add each entry straight to the search list
        #month average rain tagsmonthTempAvg_vh
        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'avrainjan' : monthRainAvg_vh[0],
                                 'avrainfeb' : monthRainAvg_vh[1],
                                 'avrainmar' : monthRainAvg_vh[2],
                                 'avrainapr' : monthRainAvg_vh[3],
                                 'avrainmay' : monthRainAvg_vh[4],
                                 'avrainjun' : monthRainAvg_vh[5],
                                 'avrainjul' : monthRainAvg_vh[6],
                                 'avrainaug' : monthRainAvg_vh[7],
                                 'avrainsep' : monthRainAvg_vh[8],
                                 'avrainoct' : monthRainAvg_vh[9],
                                 'avrainnov' : monthRainAvg_vh[10],
                                 'avraindec' : monthRainAvg_vh[11],
                                 'avtempjan' : monthTempAvg_vh[0],
                                 'avtempfeb' : monthTempAvg_vh[1],
                                 'avtempmar' : monthTempAvg_vh[2],
                                 'avtempapr' : monthTempAvg_vh[3],
                                 'avtempmay' : monthTempAvg_vh[4],
                                 'avtempjun' : monthTempAvg_vh[5],
                                 'avtempjul' : monthTempAvg_vh[6],
                                 'avtempaug' : monthTempAvg_vh[7],
                                 'avtempsep' : monthTempAvg_vh[8],
                                 'avtempoct' : monthTempAvg_vh[9],
                                 'avtempnov' : monthTempAvg_vh[10],
                                 'avtempdec' : monthTempAvg_vh[11],
                                 'recordhightempjan' : monthTempMax_vh[0],
                                 'recordhightempfeb' : monthTempMax_vh[1],
                                 'recordhightempmar' : monthTempMax_vh[2],
                                 'recordhightempapr' : monthTempMax_vh[3],
                                 'recordhightempmay' : monthTempMax_vh[4],
                                 'recordhightempjun' : monthTempMax_vh[5],
                                 'recordhightempjul' : monthTempMax_vh[6],
                                 'recordhightempaug' : monthTempMax_vh[7],
                                 'recordhightempsep' : monthTempMax_vh[8],
                                 'recordhightempoct' : monthTempMax_vh[9],
                                 'recordhightempnov' : monthTempMax_vh[10],
                                 'recordhightempdec' : monthTempMax_vh[11],
                                 'recordlowtempjan' : monthTempMin_vh[0],
                                 'recordlowtempfeb' : monthTempMin_vh[1],
                                 'recordlowtempmar' : monthTempMin_vh[2],
                                 'recordlowtempapr' : monthTempMin_vh[3],
                                 'recordlowtempmay' : monthTempMin_vh[4],
                                 'recordlowtempjun' : monthTempMin_vh[5],
                                 'recordlowtempjul' : monthTempMin_vh[6],
                                 'recordlowtempaug' : monthTempMin_vh[7],
                                 'recordlowtempsep' : monthTempMin_vh[8],
                                 'recordlowtempoct' : monthTempMin_vh[9],
                                 'recordlowtempnov' : monthTempMin_vh[10],
                                 'recordlowtempdec' : monthTempMin_vh[11]}
        return search_list_extension

class Ago(object):
    """Helper class that takes a record from some time in the past and
    allows tags such as $ago15.barometer which provides the barometer
    obs 15 minutes ago. Modelled on the Weewx Trend class in filegenerator.py.
    Note that $agoxx.rain will provide the rainfall in the archive period
    ending xx minutes ag. To get the rainfall to date for the day use the tag
    $agoxxrain
    """

    def __init__(self, ago_rec_vtd, current_rec_vtd, time_delta, formatter, converter):
        """Initialize an Ago object
        ago_rec_vtd: A ValueDict containing records from the past.
        current_rec_vtd: A ValueDict containing current record.
        """
        self.ago_rec_vtd = ago_rec_vtd
        self.current_rec_vtd = current_rec_vtd
        self.formatter = formatter
        self.converter = converter
        self.time_delta = weewx.units.ValueHelper((time_delta, 'second', 'group_elapsed'),
                                                  'current',
                                                  formatter,
                                                  converter)

    def __getattr__(self, obs_type):
        """Return the past obs for the given observation type."""

        # The following is so the Python version of Cheetah's NameMapper doesn't think
        # I'm a dictionary:
        if obs_type == 'has_key':
            raise AttributeError
        # Get current value tuple of our obs in case our 'ago' does not exist.
        # At least then we have the group and units to use with
        # our ValueHelper when we set the result to 'None'
        # Wrap in a try block because the record might not exist or its
        # value might be None.
        try:
            current_val  = self.converter.convert(self.current_rec_vtd[obs_type])
            ago_val = self.converter.convert(self.ago_rec_vtd[obs_type])
        except TypeError:
            # We have a problem getting the ago obs so we'll set the value to
            # 'None' and use the group and units from the current record
            # observation
            ago_val = (None,) + current_val[1:3]

        # Return the results as a ValueHelper. Use the formatting and labeling
        # options from the record concerned. The user can always override these.
        return weewx.units.ValueHelper(ago_val, 'current',
                                       self.formatter,
                                       self.converter)

class wdClientrawAgoTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)
        try:
            self.time_grace = int(generator.skin_dict['Units']['Trend'].get('time_grace', 300))
        except KeyError:
            self.time_grace = 300    # 5 minutes

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with agoxxx.observations
           for Clientraw templates.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          agoxx ValuHelpers allowing access to observations xx minutes ago
          where xx is 6, 12, 18,24, 30, 36, 42, 48, 54 or 60
        """

        ##
        ## Provides $agoxxx.observation tags where xxx is the number of minutes
        ## ago and observation is the observation type concerend eg
        ##   $ago6.outTemp is the outside temperature 6 minutes ago
        ##   $ago54.barometer is the barometer reading 54 minutes ago
        ##
        ## As the results are returned as ValueHelpers standard Weewx
        ## formatting/unit conversion is available eg $ago30.outTemp.degree_F etc.
        ##
        ## Currently implemented 'ago' times are:
        ##   6, 12, 18, 24, 30, 36, 42, 48, 54 and 60 minutes
        ##
        ## To take into account systems which use an archive period greater
        ## than 2 minutes but is not 6 minutes, a max_delta setting of
        ## 180 (3 minutes) has been used. Systems that use an archive period of
        ## greater than 6 minutes will likely see erratic results due to the
        ## time between archive records.
        ##
        ## These times can be added to by adding additional queries and
        ## adding the Ago object to the search list.
        ##

        current_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 360, 
                                                 max_delta=180)
        ago6 = Ago(ago_rec_vtd, current_rec_vtd, 360,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 720, 
                                                 max_delta=180)
        ago12 = Ago(ago_rec_vtd, current_rec_vtd, 720,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 1080, 
                                                 max_delta=180)
        ago18 = Ago(ago_rec_vtd, current_rec_vtd, 1080,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 1440, 
                                                 max_delta=180)
        ago24 = Ago(ago_rec_vtd, current_rec_vtd, 1440,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 1800, 
                                                 max_delta=180)
        ago30 = Ago(ago_rec_vtd, current_rec_vtd, 1800,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 2160, 
                                                 max_delta=180)
        ago36 = Ago(ago_rec_vtd, current_rec_vtd, 2160,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 2520, 
                                                 max_delta=180)
        ago42 = Ago(ago_rec_vtd, current_rec_vtd, 2520,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 2880, 
                                                 max_delta=180)
        ago48 = Ago(ago_rec_vtd, current_rec_vtd, 2880,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 3240, 
                                                 max_delta=180)
        ago54 = Ago(ago_rec_vtd, current_rec_vtd, 3240,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 3600, 
                                                 max_delta=180)
        ago60 = Ago(ago_rec_vtd, current_rec_vtd, 3600,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)

        search_list_extension = {'ago6'      : ago6,
                                 'ago12'     : ago12,
                                 'ago18'     : ago18,
                                 'ago24'     : ago24,
                                 'ago30'     : ago30,
                                 'ago36'     : ago36,
                                 'ago42'     : ago42,
                                 'ago48'     : ago48,
                                 'ago54'     : ago54,
                                 'ago60'     : ago60}

        return search_list_extension

class wdTesttagsAgoTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)
        try:
            self.time_grace = int(generator.skin_dict['Units']['Trend'].get('time_grace', 300))
        except KeyError:
            self.time_grace = 300    # 5 minutes

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with agoxxx.observation.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          refer comments for each section
        """
        ##
        ## Get units for use later with ValueHelpers
        ##

        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        tempUnitType = getStandardUnitType(current_rec['usUnits'], 'outTemp')

        ##
        ## Generate various 'ago' tags to support WD wxtrends.php page
        ##
        ## Provides $agoxxx.observation tags where xxx is the number of minutes
        ## ago and observation is the observation type concerend eg
        ##   $ago5.outTemp is the outside temperature 5 minutes ago
        ##   $ago90barometer is the barometer reading 90 minutes ago
        ##
        ## As the results are returned as ValueHelpers standard Weewx
        ## formatting/unit conversion is available eg $ago5.outTemp.degree_F etc.
        ##
        ## Currently implemented 'ago' times are:
        ##   5, 10, 15, 20, 30, 45, 60, 90, 105 and 120 minutes
        ##
        ## These times can be added to by adding additional queries and
        ## adding the Ago object to the search list.
        ##

        current_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 300, 
                                                 max_delta=60)
        ago5 = Ago(ago_rec_vtd, current_rec_vtd, 300,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 600)
        ago10 = Ago(ago_rec_vtd, current_rec_vtd, 600,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 900)
        ago15 = Ago(ago_rec_vtd, current_rec_vtd, 900,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 1200)
        ago20 = Ago(ago_rec_vtd, current_rec_vtd, 1200,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 1800)
        ago30 = Ago(ago_rec_vtd, current_rec_vtd, 1800,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 2700)
        ago45 = Ago(ago_rec_vtd, current_rec_vtd, 2700,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 3600)
        ago60 = Ago(ago_rec_vtd, current_rec_vtd, 3600,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 4500)
        ago75 = Ago(ago_rec_vtd, current_rec_vtd, 4500,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 5400)
        ago90 = Ago(ago_rec_vtd, current_rec_vtd, 5400,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 6300)
        ago105 = Ago(ago_rec_vtd, current_rec_vtd, 6300,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)
        ago_rec_vtd  = self.generator._getRecord(archivedb, valid_timespan.stop - 7200)
        ago120 = Ago(ago_rec_vtd, current_rec_vtd, 7200,
                    formatter=self.generator.formatter,
                    converter=self.generator.converter)

        ##
        ## Generate tag for outTemp 24 hours ago
        ##
        ## As the result is returned as a ValueHelper standard Weewx
        ## formatting/unit conversion is available eg $ago24houtTemp.degree_F etc.
        ##

        # Get the archive record from 24 hours ago
        day_rec = archivedb.getRecord(valid_timespan.stop - 86400)
        # Get the outTemp value. Wrap in a try block in case the record does not exist
        # and it is None.
        try:
            day_temp = day_rec['outTemp']
        except:
            day_temp = 0
        # Wrap in a ValueHelper to provide formatting and unit info
        ago24htemp_vt = (day_temp, tempUnitType[0], tempUnitType[1])
        ago24htemp_vh = ValueHelper(ago24htemp_vt, formatter=self.generator.formatter, converter=self.generator.converter)

        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'ago5'      : ago5,
                                 'ago10'     : ago10,
                                 'ago15'     : ago15,
                                 'ago20'     : ago20,
                                 'ago30'     : ago30,
                                 'ago45'     : ago45,
                                 'ago60'     : ago60,
                                 'ago75'     : ago75,
                                 'ago90'     : ago90,
                                 'ago105'    : ago105,
                                 'ago120'    : ago120,
                                 'ago24houtTemp' : ago24htemp_vh}

        return search_list_extension

class wdClientrawAgoRainTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with agoxxxrain tags.
           Rainfall trend data on wxtrends.php page needs to be cumulative
           since the start of the day. $agoxx.rain only provides the
           rainfall over the archive period (eg 5 minutes) ending xx
           minutes ago. $agoxxrain tags have been implmented to work around
           this and provide correct cumulative rainfall.
           ago periods implmented are 6, 12, 18, 24, 30, 36, 42, 48, 54 and
           60 minutes. These can be extended by altering the list below.
           Result is a ValueHelper that is added to the search list so normal
           Weewx unit conversion and formatting is available

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          agoxrain: A list of ValueHelpers containing the days rain to the time
                    x minutes ago. Rain is calculated from midnight. x is 6, 12,
                    18, 24, 30, 36, 42, 48, 54 or 60.
        """

        ##
        ## Get units for use later with ValueHelpers
        ##

        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        rainUnitType = getStandardUnitType(current_rec['usUnits'], 'rain')

        search_list_extension={}
        # step through our 'ago' times. Additional times can be added to this
        # list (in minutes)
        for ago in (6, 12, 18, 24, 30, 36, 42, 48, 54, 60):
            # step back correct number of seconds from our end time
            rain_ts = valid_timespan.stop - ago*60
            # get our timespan
            rain_ts_TimeSpan = archiveDaySpan(rain_ts)
            # enclose our query in a try..except block in case the earlier records
            # do not exist
            try:
                (time_vt, rain_vt) = archivedb.getSqlVectors('rain', rain_ts_TimeSpan.start, rain_ts, rain_ts-rain_ts_TimeSpan.start, 'sum')
                rain_vh = ValueHelper((rain_vt[0][0], rain_vt[1], rain_vt[2]), formatter=self.generator.formatter, converter=self.generator.converter)
            except:
                rain_vh = ValueHelper((None, rainUnitType[0], rainUnitType[1]), formatter=self.generator.formatter, converter=self.generator.converter)
            search_list_extension['ago'+str(ago)+'rain'] = rain_vh

        return search_list_extension

class wdTesttagsAgoRainTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with agoxxxrain tags.
           Rainfall trend data on wxtrends.php page needs to be cumulative
           since the start of the day. $agoxx.rain only provides the
           rainfall over the archive period (eg 5 minutes) ending xx
           minutes ago. $agoxxrain tags have been implmented to work around
           this and provide correct cumulative rainfall.
           ago periods implmented are 5, 10, 15, 20, 30, 45, 60, 75, 90,
           105, 120 minutes. These can be extended by altering the list below.
           Result is a ValueHelper that is added to the search list so normal
           Weewx unit conversion and formatting is available

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          agoxrain: A list of ValueHelpers containing the days rain to the time
                    x minutes ago. Rain is calculated from midnight. x is 5, 10,
                    15, 20, 30, 45, 60, 75, 90, 105 or 120.
        """

        ##
        ## Get units for use later with ValueHelpers
        ##

        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        rainUnitType = getStandardUnitType(current_rec['usUnits'], 'rain')

        search_list_extension={}
        # step through our 'ago' times. Additional times can be added to this
        # list (in minutes)
        for ago in (5, 10, 15, 20, 30, 45, 60, 75, 90, 105, 120):
            # step back correct number of seconds from our end time
            rain_ts = valid_timespan.stop - ago*60
            # get our timespan
            rain_ts_TimeSpan = archiveDaySpan(rain_ts)
            # enclose our query in a try..except block in case the earlier records
            # do not exist
            try:
                (time_vt, rain_vt) = archivedb.getSqlVectors('rain', rain_ts_TimeSpan.start, rain_ts, rain_ts-rain_ts_TimeSpan.start, 'sum')
                rain_vh = ValueHelper((rain_vt[0][0], rain_vt[1], rain_vt[2]), formatter=self.generator.formatter, converter=self.generator.converter)
            except:
                rain_vh = ValueHelper((None, rainUnitType[0], rainUnitType[1]), formatter=self.generator.formatter, converter=self.generator.converter)
            search_list_extension['ago'+str(ago)+'rain'] = rain_vh

        return search_list_extension

class wdLastRainTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with datetime of last rain.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          last_rain: A ValueHelper containing the datetime of the last rain
        """

        ##
        ## Get units for use later with ValueHelpers
        ##

        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        baroUnitType = getStandardUnitType(current_rec['usUnits'], 'barometer')

        ##
        ## Generate 3 hour barometer trend
        ##
        ## Weewx allows the use of the $trend tag to give the trend of an ob
        ## over time. The trend period is 'trend_delta' as set in weewx.conf.
        ## Correect operation of weewx-WD relies on testtags skin.conf having
        ## 'trend_delta' set to '3600' (1 hour). Hence we have to calculate the
        ## 3 hour barometer trend.
        ## Note this is not the barometer reading 3 hours ago but rather the change
        ## in reading over the last 3 hours.
        ##
        ## As the result is returned as a ValueHelper standard Weewx
        ## formatting/unit conversion is available eg $trend180barometer.hPa etc.
        ##

        # Get archive record from 3 hours ago
        threehour_rec = archivedb.getRecord(valid_timespan.stop - 10800)
        # Calculate trend. Wrap in a try block in case 3 hour record does not exist
        # and it is None.
        try:
            threehour_trend_baro = current_rec['barometer'] - threehour_rec['barometer']
        except:
            threehour_trend_baro = 0
        # Wrap in a ValueHelper to provide formatting and unit info
        trend180barometer_vt = (threehour_trend_baro, baroUnitType[0], baroUnitType[1])
        trend180barometer_vh = ValueHelper(trend180barometer_vt, formatter=self.generator.formatter, converter=self.generator.converter)

        ##
        ## Get date and time of last rain
        ##
        ## Returns unix epoch of archive period of last rain
        ##
        ## Result is returned as a ValueHelper so standard Weewx formatting
        ## is available eg $last_rain.format("%d %m %Y")
        ##

        # Get ts for day of last rain from statsdb
        # Value returned is ts for midnight on the day the rain occurred
        _row = statsdb.xeqSql("SELECT MAX(dateTime) FROM rain WHERE sum > 0", {})
        lastrain_ts = _row[0]
        # Now use this ts to limit our search or the archivedb so we can find the
        # last archive record during which it rained. Wrap in a try statement
        # in case it does not exist
        try:
            _row = archivedb.getSql("SELECT MAX(dateTime) FROM archive WHERE rain > ? AND dateTime > ? AND dateTime <= ?", (0, lastrain_ts, lastrain_ts+86400))
            lastrain_ts = _row[0]
        except:
            lastrain_ts = None
        # Wrap in a ValueHelper
        lastrain_vt = (lastrain_ts, 'unix_epoch', 'group_time')
        lastrain_vh = ValueHelper(lastrain_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'last_rain' : lastrain_vh,
                                 'trend180barometer' : trend180barometer_vh}

        return search_list_extension

class wdTimeSpanTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with alltime and yesterdays stats.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          alltime: A TimeSpanStats object covering all time. Allows the use of
                   $alltime.outTemp.max for the all time high outside temp.
                   Standard Weewx unit conversion and formatting is available
          yesterday: A TimeSpanStats object covering yesterday. Allows the use
                     of $yesterday.outTemp.max for yesterdays high outside temp.
                     Standard Weewx unit conversion and formatting is available
        """

        #
        # alltime stats
        #
        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object valid_timespan already holds all valid times to be
        # used in the report.
        all_stats = TimeSpanStats(valid_timespan,
                                  statsdb,
                                  formatter=self.generator.formatter,
                                  converter=self.generator.converter)

        #
        # yesterday stats
        #
        # Get time obj for midnight
        midnight_t = datetime.time(0)
        # Get datetime obj for now
        today_dt = datetime.datetime.today()
        # Get datetime obj for midnight at start of today (our start time)
        midnight_dt = datetime.datetime.combine(today_dt, midnight_t)
        # Our start is 1 day earlier than current (midnight today)
        midnight_yest_dt = midnight_dt - datetime.timedelta(days=1)
        # Get it as a timestamp
        midnight_yest_ts = time.mktime(midnight_yest_dt.timetuple())
        # Get a TimeSpanStats obj for yesterday stats
        yesterday_stats = TimeSpanStats(TimeSpan(midnight_yest_ts,  midnight_yest_ts + 24 * 3600 ),
                          statsdb,
                          formatter=self.generator.formatter,
                          converter=self.generator.converter)

        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'alltime'   : all_stats,
                                 'yesterday' : yesterday_stats}

        return search_list_extension

class wdTesttagsTimeSpanTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with last seven days stats.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          seven_day: A TimeSpanStats object covering the last seven days. Time
                     covered is from midnight 7 days ago until current time
                     (ie actual period may be from 7 days to 8 days in length
                     depending on current itme of day). Allows the use of
                     $seven_day.outTemp.max for the high outside temp in the
                     last 7 days. Standard Weewx unit conversion and formatting
                     is available
        """

        # Now get a TimeSpanStats object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(valid_timespan.stop) - datetime.timedelta(weeks=1)
        # Now convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())
        # Now form a TimeSpanStats object, using the time span we just calculated:
        seven_day_stats = TimeSpanStats(TimeSpan(week_ts, valid_timespan.stop),
                                        statsdb,
                                        context='seven_day',
                                        formatter=self.generator.formatter,
                                        converter=self.generator.converter)

        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'seven_day' : seven_day_stats}

        return search_list_extension

class wdMaxAvgWindTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with max average wind speed stats.
           Due to Weewx combining windSpeed and windGust to create hybrid 'wind'
           stat, Weewx cannot natively provide windSpeed (only) stats such as
           $day.windSpeed.max etc. This code works around this issue to generate
           today's max and avg windSpeed along with associated directions and times.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          max_avg_wind: A ValueHelper containing today's max windSpeed
                        (ie max average archive period wind speed - not gust).
                        Standard Weewx unit conversion and formatting is
                        available.
          max_avg_wind_dir: A ValueHelper containing the direction of today's
                            max windSpeed. Standard Weewx unit conversion and
                            formatting is available.
          max_avg_wind_time: A ValueHelper containing the epoch time of today's
                            max windSpeed. Standard Weewx unit conversion and
                            formatting is available.
          yest_max_avg_wind: A ValueHelper containing yesterday's max windSpeed
                             (ie max average archive period wind speed - not
                             gust). Standard Weewx unit conversion and
                             formatting is available.
          yest_max_avg_wind_dir: A ValueHelper containing the direction of
                                 yesterday's max windSpeed. Standard Weewx unit
                                 conversion and formatting is available.
          yest_max_avg_wind_time: A ValueHelper containing the epoch time of
                                  yesterday's max windSpeed. Standard Weewx unit
                                  conversion and formatting is available.
        """

        ##
        ## Get units for use later with ValueHelpers
        ##
        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        windUnitType = getStandardUnitType(current_rec['usUnits'], 'windSpeed')
        dirUnitType = getStandardUnitType(current_rec['usUnits'], 'windDir')
        timeUnitType = getStandardUnitType(current_rec['usUnits'], 'dateTime')

        ##
        ## For Today and Yesterdays stats we need some midnight timestamps
        ##
        # Get time obj for midnight
        midnight_t = datetime.time(0)
        # Get datetime obj for now
        today_dt = datetime.datetime.today()
        # Get datetime obj for midnight at start of today (our start time)
        midnight_dt = datetime.datetime.combine(today_dt, midnight_t)
        # Get timestamp for midnight at start of today (our start time)
        midnight_ts = time.mktime(midnight_dt.timetuple())
        # Our start is 1 day earlier than current (midnight today)
        midnight_yest_dt = midnight_dt - datetime.timedelta(days=1)
        # Get it as a timestamp
        midnight_yest_ts = time.mktime(midnight_yest_dt.timetuple())

        ##
        ## Todays windSpeed stats
        ##
        # Get today's windSpeed obs as a ValueTuple and convert them
        (time_valuetuple, wind_speed_valuetuple) = archivedb.getSqlVectors('windSpeed', midnight_ts, valid_timespan.stop)
        wind_speed_valuetuple = self.generator.converter.convert(wind_speed_valuetuple)
        # Get today's windDir obs as a ValueTuple and convert them
        (time_valuetuple, wind_dir_valuetuple) = archivedb.getSqlVectors('windDir', midnight_ts, valid_timespan.stop)
        wind_dir_valuetuple = self.generator.converter.convert(wind_dir_valuetuple)
        # Convert the times
        wind_speed_time_valuetuple = self.generator.converter.convert(time_valuetuple)
        # Find the max windSpeed
        max_avg_wind = max(wind_speed_valuetuple[0])
        # Find its location in the list
        maxindex = wind_speed_valuetuple[0].index(max_avg_wind)
        # Get the corresponding direction
        max_avg_dir = wind_dir_valuetuple[0][maxindex]
        # Get the corresponding time
        max_avg_wind_time = wind_speed_time_valuetuple[0][maxindex]
        # Wrap results in a ValueHelper to provide formatting and unit info
        max_avg_wind_vt = (max_avg_wind, windUnitType[0], windUnitType[1])
        max_avg_wind_vh = ValueHelper(max_avg_wind_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        max_avg_wind_dir_vt = (max_avg_dir, dirUnitType[0], dirUnitType[1])
        max_avg_wind_dir_vh = ValueHelper(max_avg_wind_dir_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        max_avg_wind_time_vt = (max_avg_wind_time, timeUnitType[0], timeUnitType[1])
        max_avg_wind_time_vh = ValueHelper(max_avg_wind_time_vt, formatter=self.generator.formatter, converter=self.generator.converter)

        ##
        ## Yesterdays windSpeed stats
        ##
        # Get yesterday's windSpeed obs as a ValueTuple and convert them
        (time_valuetuple, wind_speed_valuetuple) = archivedb.getSqlVectors('windSpeed', midnight_yest_ts, midnight_ts)
        wind_speed_valuetuple = self.generator.converter.convert(wind_speed_valuetuple)
        # Get yesterday's windDir obs as a ValueTuple and convert them
        (time_valuetuple, wind_dir_valuetuple) = archivedb.getSqlVectors('windDir', midnight_yest_ts, midnight_ts)
        wind_dir_valuetuple = self.generator.converter.convert(wind_dir_valuetuple)
        # Convert the times
        wind_speed_time_valuetuple = self.generator.converter.convert(time_valuetuple)
        # Find the max windSpeed. Wrap in try statement in case it does not exist
        try:
            yest_max_avg_wind = max(wind_speed_valuetuple[0])
            # Find its location in the list
            maxindex = wind_speed_valuetuple[0].index(yest_max_avg_wind)
            # Get the corresponding direction
            yest_max_avg_dir = wind_dir_valuetuple[0][maxindex]
            # Get the corresponding time
            yest_max_avg_wind_time = wind_speed_time_valuetuple[0][maxindex]
        except:
            yest_max_avg_wind = None
            yest_max_avg_dir = None
            yest_max_avg_wind_time = None
        # Wrap results in a ValueHelper to provide formatting and unit info
        yest_max_avg_wind_vt = (yest_max_avg_wind, windUnitType[0], windUnitType[1])
        yest_max_avg_wind_vh = ValueHelper(yest_max_avg_wind_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        yest_max_avg_wind_dir_vt = (yest_max_avg_dir, dirUnitType[0], dirUnitType[1])
        yest_max_avg_wind_dir_vh = ValueHelper(yest_max_avg_wind_dir_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        yest_max_avg_wind_time_vt = (yest_max_avg_wind_time, timeUnitType[0], timeUnitType[1])
        yest_max_avg_wind_time_vh = ValueHelper(yest_max_avg_wind_time_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        
        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'max_avg_wind' : max_avg_wind_vh,
                                 'max_avg_wind_dir' : max_avg_wind_dir_vh,
                                 'max_avg_wind_time' : max_avg_wind_time_vh,
                                 'yest_max_avg_wind' : yest_max_avg_wind_vh,
                                 'yest_max_avg_wind_dir' : yest_max_avg_wind_dir_vh,
                                 'yest_max_avg_wind_time' : yest_max_avg_wind_time_vh}

        return search_list_extension

class wdMaxWindGustTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with various max wind gust tags.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          max_24h_gust_wind: A ValueHelper containing the max windGust over the
                             preceding 24 hours. Standard Weewx unit conversion
                             and formatting is available.
          max_24h_gust_wind_time: A ValueHelper containing the max windGust
                                  over the preceding 24 hours. Standard Weewx
                                  unit conversion and formatting is available.
                                  
          max_10_gust_wind: A ValueHelper containing the max windGust over the
                            preceding 10 minutes. Standard Weewx unit
                            conversion and formatting is available.
        """

        ##
        ## Get units for use later with ValueHelpers
        ##
        # Get current record from the archive
        if not self.generator.gen_ts:
            self.generator.gen_ts = archivedb.lastGoodStamp()
        current_rec = archivedb.getRecord(self.generator.gen_ts)
        # Get the unit in use for each group
        windUnitType = getStandardUnitType(current_rec['usUnits'], 'windSpeed')
        timeUnitType = getStandardUnitType(current_rec['usUnits'], 'dateTime')

        ##
        ## Last 24 hours windGust stats
        ##
        # Get last 24 hour's windGust obs as a ValueTuple and convert them
        (time_valuetuple, wind_gust_valuetuple) = archivedb.getSqlVectors('windGust', valid_timespan.stop-86400, valid_timespan.stop)
        wind_gust_valuetuple = self.generator.converter.convert(wind_gust_valuetuple)
        # Convert the times
        wind_gust_time_valuetuple = self.generator.converter.convert(time_valuetuple)
        # Find the max windGust
        max_gust_wind = max(wind_gust_valuetuple[0])
        # Find its location in the list
        maxindex = wind_gust_valuetuple[0].index(max_gust_wind)
        # Get the corresponding time
        max_gust_wind_time = wind_gust_time_valuetuple[0][maxindex]
        # Wrap results in a ValueHelper to provide formatting and unit info
        max_gust_wind_vt = (max_gust_wind, windUnitType[0], windUnitType[1])
        max_gust_wind_vh = ValueHelper(max_gust_wind_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        max_gust_wind_time_vt = (max_gust_wind_time, timeUnitType[0], timeUnitType[1])
        max_gust_wind_time_vh = ValueHelper(max_gust_wind_time_vt, formatter=self.generator.formatter, converter=self.generator.converter)

        ##
        ## Last 10 min windGust stats
        ##
        # Get last 10 minutes max windGust obs as a ValueTuple and convert them
        (time_valuetuple, wind_gust_valuetuple) = archivedb.getSqlVectors('windGust', valid_timespan.stop-600, valid_timespan.stop, 600, 'max')
        # Do any necessary conversion
        wind_gust_valuetuple = self.generator.converter.convert(wind_gust_valuetuple)
        # Wrap results in a ValueHelper to provide formatting and unit info
        max_10_gust_wind_vt = (wind_gust_valuetuple[0][0], windUnitType[0], windUnitType[1])
        max_10_gust_wind_vh = ValueHelper(max_10_gust_wind_vt, formatter=self.generator.formatter, converter=self.generator.converter)
        
        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'max_24h_gust_wind' : max_gust_wind_vh,
                                 'max_24h_gust_wind_time' : max_gust_wind_time_vh,
                                 'max_10_gust_wind' : max_10_gust_wind_vh}

        return search_list_extension

class wdSundryTags(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns various tags.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          forecast_text: Returns a string with weather forecast text from a
                         file specified in the relevant skin.conf.
          forecast_icon: Returns an integer specifying the weather forecast
                         icon from a file specified in the relevant skin.conf.
          start_time: A ValueHelper containing the epoch time that weewx was
                     started. Standard Weewx unit conversion and formatting is
                     available.
        """

        ##
        ## Add Forecast Data tag if forecast data exists
        ## Forecast_File_Location setting in clientraw skin.conf holds name
        ## and location of forecast data file
        ##

        # Get forecast file setting
        forecastfile = self.generator.skin_dict['Extras']['Forecast'].get('Forecast_File_Location')
        # If the file exists open it, get the data and close it
        if (forecastfile):
            f = open(forecastfile, "r")
            forecast_raw_text = f.readline()
            forecast_text = forecast_raw_text.strip(' \t\n\r')
            forecast_icon = f.readline()
            f.close()
        # Otherwise set the forecast data to empty strings
        else:
            forecast_text = ""
            forecast_icon = ""

        ##
        ## Get ts Weewx was launched
        ##
        try:
            starttime = weewx.launchtime_ts
        except ValueError:
            starttime = time.time()
        # Wrap in a ValueHelper
        starttime_vt = (starttime, 'unix_epoch', 'group_time')
        starttime_vh = ValueHelper(starttime_vt, formatter=self.generator.formatter, converter=self.generator.converter)

        # Create a small dictionary with the tag names (keys) we want to use
        search_list_extension = {'forecast_text': forecast_text,
                                 'forecast_icon': forecast_icon,
                                 'start_time' : starttime_vh}

        return search_list_extension

class wdTaggedStats(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with custom tagged stats
           drawn from stats database. Permits the syntax
           $stat_type.observation.agg_type where:
           stat_type is:
             weekdaily - week of stats aggregated by day
             monthdaily - month of stats aggregated by day
             yearmonthy - year of stats aggregated by month
           observation is any weewx observation recorded in the stats database
           eg outTemp or humidity
           agg_type is:
             maxQuery - returns maximums/highs over the aggregate period
             minQuery - returns minimums/lows over the aggregate period
             avgQuery - returns averages over the aggregate period
             sumQuery - returns sum over the aggregate period
             vecdirQuery - returns vector direction over the aggregate period

           Also supports the $stat_type.observation.exists and
           $stat_type.observation.has_data properties which are true if the
           relevant observation exists and has data respectively

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          A list of ValueHelpers for custom stat concerned as follows:
            weekdaily - list of 7 ValueHelpers. Item [0] is the earliest day,
                        item [6] is the current day
            monthdaily - list of 31 ValueHelpers. Item [0] is the day 31 days ago,
                         item [30] is the current day
            yearmonthy - list of 31 ValueHelpers. Item [0] is the month 12
                         months ago, item [11] is the current month

          So $weekdaily.outTemp.maxQuery.degree_F woudl return a list of the
          max temp in Fahrenheit for each day over the last 7 days.
          $weekdaily.outTemp.maxQuery[1].degree_C would return the max temp in
          Celcius of the day 6 days ago.
          """

        # Get a WDTaggedStats structure. This allows constructs such as
        # WDstats.monthdaily.outTemp.max
        WDstats = user.wdtaggedstats.WDTaggedStats(statsdb,
                                        valid_timespan.stop,
                                        formatter = self.generator.formatter,
                                        converter = self.generator.converter)
        return WDstats

class wdTaggedArchiveStats(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with custom tagged stats
           drawn from archive database. Permits the syntax
           $stat_type.observation.agg_type where:
           stat_type is:
             minute - hour of stats aggregated by minute
             fifteenminute - day of stats aggregated by 15 minutes
             hour - day of stats aggregated by hour
             sixhour - week of stats aggegated by 6 hours
           observation is any weewx observation recorded in the archive database
           eg outTemp or humidity
           agg_type is:
             maxQuery - returns maximums/highs over the aggregate period
             minQuery - returns minimums/lows over the aggregate period
             avgQuery - returns averages over the aggregate period
             sumQuery - returns sum over the aggregate period
             datetimeQuery - returns datetime over the aggregate period

           Also supports the $stat_type.observation.exists and
           $stat_type.observation.has_data properties which are true if the
           relevant observation exists and has data respectively

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          A list of ValueHelpers for custom stat concerned as follows:
            minute - list of 60 ValueHelpers. Item [0] is the minute commencing
                     60 minutes ago, item [59] is the minute immediately before
                     valid_timespan.stop. For archive periods greater than
                     60 seconds the intervening minutes between archive records
                     are extrapolated linearly.
            fifteenminute - list of 96 ValueHelpers. Item [0] is the 15 minute
                            period commencing 24 hours ago, item [95] is the
                            15 minute period ending at valid_timespan.stop.
            hour - list of 24 ValueHelpers. Item [0] is the hours commencing
                   24 hours ago, item [23] is the hour ending at
                   valid_timespan.stop.
            sixhour - list of 42 ValueHelpers. Item [0] is the 6 hour period
                      commencing 192 hours ago, item [41] is the 6 hour period
                      ending at valid_timespan.stop.

          So $fifteenminute.outTemp.maxQuery.degree_F would return a list of the
          max temp in Fahrenheit for each 15 minute period over the last 24 hours.
          $fifteenminute.outTemp.maxQuery[1].degree_C would return the max temp in
          Celcius of the 15 minute period commencing 23hr 45min ago.
          """

        # Get a WDTaggedStats structure. This allows constructs such as
        # WDstats.minute.outTemp.max
        WDarchivestats = user.wdtaggedstats.WDATaggedStats(archivedb,
                                        valid_timespan.stop,
                                        formatter = self.generator.formatter,
                                        converter = self.generator.converter)

        return WDarchivestats

class wdYestAlmanac(SearchList):
    """Class that implements the '$yestAlmanac' tag to support change of day
       length calcs.

    Parameters:
      valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                      hold the start and stop times of the domain of
                      valid times.
      archivedb: An instance of weewx.archive.Archive
      
      statsdb:   An instance of weewx.stats.StatsDb

    Returns:
      yestAlmanac: An instance of Almanac for yesterday. Almanac time is
                   set to 24 hours ago. All Almanac attributes are available
                   eg $yestAlmanac.sun.set or $yestAlmanac.mercury.rise
    """

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        celestial_ts = generator.gen_ts

        # For better accuracy, the almanac requires the current temperature
        # and barometric pressure, so retrieve them from the default archive,
        # using celestial_ts as the time

        temperature_C = pressure_mbar = None

        archivedb = generator._getArchive(generator.skin_dict['archive_database'])
        ## NEED TO FIX - what if there is no record 24 hours ago
        if not celestial_ts:
            celestial_ts = archivedb.lastGoodStamp() - 86400
        rec = archivedb.getRecord(celestial_ts, max_delta=3600)

        if rec is not None:
            # Wrap the record in a ValueTupleDict. This makes it easy to do
            # unit conversions.
            rec_vtd = weewx.units.ValueTupleDict(rec)
            
            if rec_vtd.has_key('outTemp'):
                temperature_C = weewx.units.convert(rec_vtd['outTemp'], 'degree_C')[0]

            if rec_vtd.has_key('barometer'):
                pressure_mbar = weewx.units.convert(rec_vtd['barometer'], 'mbar')[0]
        if temperature_C is None: temperature_C = 15.0
        if pressure_mbar is None: pressure_mbar = 1010.0

        self.moonphases = generator.skin_dict.get('Almanac', {}).get('moon_phases', weeutil.Moon.moon_phases)

        altitude_vt = weewx.units.convert(generator.stn_info.altitude_vt, "meter")

        self.yestAlmanac = weewx.almanac.Almanac(celestial_ts,
                                             generator.stn_info.latitude_f,
                                             generator.stn_info.longitude_f,
                                             altitude=altitude_vt[0],
                                             temperature=temperature_C,
                                             pressure=pressure_mbar,
                                             moon_phases=self.moonphases,
                                             formatter=generator.formatter)

class wdSkinDict(SearchList):
    """Class that makes skin settings available."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        ##
        ## Make skin dictionary settings available in the templates
        ##

        self.skin_dict = generator.skin_dict

class wdMonthlyReportStats(SearchList):

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension(self, valid_timespan, archivedb, statsdb):
        """Returns a search list extension with various date/time tags
           used in WD monthly report template.

        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of
                          valid times.
          archivedb: An instance of weewx.archive.Archive

          statsdb:   An instance of weewx.stats.StatsDb

        Returns:
          month_name - abbreviated month name eg Dec of start of timespan
          month_long_name - long month name eg December of start of timespan
          month_number - month number eg 12 for December of start of timespan
          year_name - 4 digit year eg 2013 of start of timespan
          curr_minute - current minute of time of last record
          curr_hour - current hour of time of last record
          curr_day - day of time of last archive record
          curr_month - month of time of last archive record
          curr_year - year of time of last archive record
        """

        # Get a required times and convert to time tuples
        timespan_start_tt = time.localtime(valid_timespan.start)
        stop_ts  = archivedb.lastGoodStamp()
        stop_tt = time.localtime(stop_ts)

        # Create a small dictionary with the tag names (keys) we want to use

        searchList = {'month_name' : time.strftime("%b", timespan_start_tt),
                      'month_long_name' : time.strftime("%B", timespan_start_tt),
                      'month_number' : timespan_start_tt[1],
                      'year_name'  : timespan_start_tt[0],
                      'curr_minute' : stop_tt[4],
                      'curr_hour' : stop_tt[3],
                      'curr_day' : stop_tt[2],
                      'curr_month' : stop_tt[1],
                      'curr_year' : stop_tt[0]}

        return searchList
