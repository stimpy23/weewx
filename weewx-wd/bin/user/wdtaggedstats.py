##
##This program is free software; you can redistribute it and/or modify
##it under the terms of the GNU General Public License as published by
##the Free Software Foundation; either version 2 of the License, or
##(at your option) any later version.
##
##This program is distributed in the hope that it will be useful,
##but WITHOUT ANY WARRANTY; without even the implied warranty of
##MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##GNU General Public License for more details.
##
import datetime
import time
import syslog
import calendar
import weewx
import os.path
import weewx.almanac
import weewx.units
import weeutil.weeutil

from weewx.units import ValueHelper, getStandardUnitType
from weewx.stats import TimeSpanStats
from weewx.filegenerator import FileGenerator
from weeutil.weeutil import TimeSpan
from datetime import date, timedelta

#===============================================================================
#                    Class WDTaggedStats
#===============================================================================

class WDTaggedStats(object):
    """This class allows custom tagged stats drawn from the archive database in
    support of the Weewx-WD templates. This class along with the associated
    WDTimeSpanStats and WDStatsTypeHelper classes support the following custom
    tagged stats:
    - $weekdaily.xxxxxx.zzzzzz - week of stats aggregated by day
    - $monthdaily.xxxxxx.zzzzzz - month of stats aggregated by day
    - $yearmonthy.xxxxxx.zzzzzz - year of stats aggregated by month
    - where xxxxxx is a Weewx observation eg outTemp, wind (stats database),
      windSpeed (archive database) etc recorded in the relevant database. Note
      that WDATaggedStats uses the archive database and WDTaggedStats uses the
      stats database.
    - where zzzzzz is either:
        - maxQuery - returns maximums/highs over the aggregate period
        - minQuery - returns minimums/lows over the aggregate period
        - avgQuery - returns averages over the aggregate period
        - sumQuery - returns sum over the aggregate period
        - vecdirQuery - returns vector direction over the aggregate period

    In the Weewx-WD templates these tagged stats (eg $hour.outTemp.maxQuery)
    result in a list which is assigned to a variable and then each item in
    the list is reference using its index eg variable_name[0]

    This class sits on the top of chain of helper classes that enable
    syntax such as $hour.rain.sumQuery in the templates.

    When a time period is given as an attribute to it, such as obj.hour,
    the next item in the chain is returned, in this case an instance of
    WDTimeSpanStats, which binds the database with the
    time period.
    """

    def __init__(self, db, endtime_ts, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of WDTaggedStats.

        db: The database the stats are to be extracted from.

        endtime_ts: The time the stats are to be current to.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        self.db          = db
        self.endtime_ts  = endtime_ts
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    # What follows is the list of time period attributes:

    @property
    def weekdaily(self):
        return WDTimeSpanStats((self.endtime_ts - 604800, self.endtime_ts), self.db, weeutil.weeutil.genDaySpans, 'weekdaily',
                             self.formatter, self.converter, **self.option_dict)
    @property
    def monthdaily(self):
        return WDTimeSpanStats((self.endtime_ts - 2678400, self.endtime_ts), self.db, weeutil.weeutil.genDaySpans, 'monthdaily',
                             self.formatter, self.converter, **self.option_dict)
    @property
    def yearmonthly(self):
        _now_dt = datetime.datetime.fromtimestamp(self.endtime_ts)
        _start_dt = datetime.date(day=1, month=_now_dt.month, year=_now_dt.year-1)
        _start_ts = time.mktime(_start_dt.timetuple())
        return WDTimeSpanStats((_start_ts, self.endtime_ts), self.db, weeutil.weeutil.genMonthSpans, 'yearmonthly',
                             self.formatter, self.converter, **self.option_dict)

#===============================================================================
#                    Class WDTimeSpanStats
#===============================================================================

class WDTimeSpanStats(object):
    """Nearly stateless class that holds a binding to a stats database and a timespan.

    This class is the next class in the chain of helper classes.

    When a statistical type is given as an attribute to it (such as 'obj.outTemp'),
    the next item in the chain is returned, in this case an instance of
    WDStatsTypeHelper, which binds the stats database, the time period, and
    the statistical type all together.

    """
    def __init__(self, timespan, db, genspans, context='current', formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of WDTimeSpanStats.

        timespan: An instance of weeutil.Timespan with the time span
        over which the statistics are to be calculated.

        db: The database the stats are to be extracted from.

        context: A tag name for the timespan. This is something like 'monthdaily', 'weekdaily',
        or 'yearmonthly', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.timespan    = timespan
        self.db          = db
        self.genspans    = genspans
        self.context     = context
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    def __getattr__(self, stats_type):
        """Return a helper object that binds the stats database, a time period,
        and the given statistical type.

        stats_type: A statistical type, such as 'outTemp', or 'outHumidity'

        returns: An instance of class WDStatsTypeHelper."""

        # The following is so the Python version of Cheetah's NameMapper doesn't think
        # I'm a dictionary:
        if stats_type == 'has_key':
            raise AttributeError

        # Return the helper class, bound to the type:
        return WDStatsTypeHelper(stats_type, self.timespan, self.db, self.context, self.genspans, self.formatter, self.converter, **self.option_dict)

#===============================================================================
#                    Class WDStatsTypeHelper
#===============================================================================

class WDStatsTypeHelper(object):
    """This is the final class in the chain of helper classes. It binds the statistical
    database, a time period, and a statistical type all together.

    When an aggregation type (eg, 'maxQuery') is given as an attribute to it, it runs the
    query against the database, assembles the result, and returns it as a list of ValueHelpers.
    For example 'maxQuery' will return a list of ValueHelpers each with the 'max' value of the
    observation over the aggregateion period.
    Whilst the aggregation types are similar to those in the StatsTypeHelper class since we
    are seeking a list of aggregates over a number of periods the aggregate types are 'maxQuery',
    'minQuery' etc to distinguish them from the standard 'max, 'min' etc aggregagtes.
    """

    def __init__(self, stats_type, timespan, db, context, genspans, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """ Initialize an instance of WDStatsTypeHelper

        stats_type: A string with the stats type (e.g., 'outTemp') for which the query is
        to be done.

        timespan: An instance of TimeSpan holding the time period over which the query is
        to be run

        db: The database the stats are to be extracted from.

        context: A tag name for the timespan. This is something like 'current', 'day',
        'week', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.stats_type  = stats_type
        self.timespan    = timespan
        self.db          = db
        self.context     = context
        self.genspans    = genspans
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    def maxQuery(self):
        final=[]
        for tspan in self.genspans(self.timespan[0], self.timespan[1]):
            result = self.db.getAggregate(tspan, self.stats_type, 'max')
            final.append(weewx.units.ValueHelper(result, self.context, self.formatter, self.converter))
        return final

    def minQuery(self):
        final=[]
        for tspan in self.genspans(self.timespan[0], self.timespan[1]):
            result = self.db.getAggregate(tspan, self.stats_type, 'min')
            final.append(weewx.units.ValueHelper(result, self.context, self.formatter, self.converter))
        return final

    def avgQuery(self):
        final=[]
        for tspan in self.genspans(self.timespan[0], self.timespan[1]):
            result = self.db.getAggregate(tspan, self.stats_type, 'avg')
            final.append(weewx.units.ValueHelper(result, self.context, self.formatter, self.converter))
        return final

    def sumQuery(self):
        final=[]
        for tspan in self.genspans(self.timespan[0], self.timespan[1]):
            result = self.db.getAggregate(tspan, self.stats_type, 'sum')
            final.append(weewx.units.ValueHelper(result, self.context, self.formatter, self.converter))
        return final

    def vecdirQuery(self):
        final=[]
        for tspan in self.genspans(self.timespan[0], self.timespan[1]):
            result = self.db.getAggregate(tspan, self.stats_type, 'vecdir')
            final.append(weewx.units.ValueHelper(result, self.context, self.formatter, self.converter))
        return final

    def __getattr__(self, aggregateType):
        """Return statistical summary using a given aggregateType.

        aggregateType: The type of aggregation over which the summary is to be done.
        This is normally something like 'sum', 'min', 'mintime', 'count', etc.
        However, there are two special aggregation types that can be used to
        determine the existence of data:
          'exists':   Return True if the observation type exists in the database.
          'has_data': Return True if the type exists and there is a non-zero
                      number of entries over the aggregation period.

        returns: For special types 'exists' and 'has_data', returns a Boolean
        value. Otherwise, a ValueHelper containing the aggregation data."""

        if aggregateType == 'exists':
            return self.stats_type in self.db.sqlkeys
        elif aggregateType == 'has_data':
            return self.stats_type in self.db.sqlkeys and self.db.getAggregate(self.timespan, self.stats_type, 'count') != 0
        else:
            result = self.db.getAggregate(self.timespan, self.stats_type, aggregateType)
        # Wrap the result in a ValueHelper:
        return weewx.units.ValueHelper(result, self.context, self.formatter, self.converter)

#===============================================================================
#                    Class WDATaggedStats
#===============================================================================

class WDATaggedStats(object):
    """This class allows custom tagged stats drawn from the archive database in
    support of the Weewx-WD templates. This class along with the associated
    WDATimeSpanStats and WDAStatsTypeHelper classes support the following custom
    tagged stats:
    - $minute.xxxxxx.zzzzzz - hour of stats aggregated by minute
    - $fifteenminute.xxxxxx.zzzzzz - day of stats aggregated by 15 minutes
    - $hour.xxxxxx.zzzzzz - day of stats aggregated by hour
    - $sixhour.xxxxxx.zzzzzz - week of stats aggegated by 6 hours
    - where xxxxxx is a Weewx observation eg outTemp, wind (stats database),
      windSpeed (archive database) etc recorded in the relevant database. Note
      that WDATaggedStats uses the archive database and WDTaggedStats uses the
      stats database.
    - where zzzzzz is either:
        - maxQuery - returns maximums/highs over the aggregate period
        - minQuery - returns minimums/lows over the aggregate period
        - avgQuery - returns averages over the aggregate period
        - sumQuery - returns sum over the aggregate period
        - datetimeQuery - returns datetime over the aggregate period

    In the Weewx-WD templates these tagged stats (eg $hour.outTemp.maxQuery)
    result in a list which is assigned to a variable and then each item in
    the list is reference using its index eg variable_name[0]

    This class sits on the top of chain of helper classes that enable
    syntax such as $hour.rain.sumQuery in the templates.

    When a time period is given as an attribute to it, such as obj.hour,
    the next item in the chain is returned, in this case an instance of
    WDATimeSpanStats, which binds the database with the
    time period.
    """

    def __init__(self, db, endtime_ts, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of TaggedStats.
        db: The database the stats are to be extracted from.

        endtime_ts: The time the stats are to be current to.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """
        self.db          = db
        self.endtime_ts  = endtime_ts
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    # What follows is the list of time period attributes:

    @property
    def minute(self):
        return WDATimeSpanStats((self.endtime_ts - 3600, self.endtime_ts), self.db, 60, 'minute',
                             self.formatter, self.converter, **self.option_dict)

    @property
    def fifteenminute(self):
        return WDATimeSpanStats((self.endtime_ts - 86400, self.endtime_ts), self.db, 900, 'fifteenminute',
                             self.formatter, self.converter, **self.option_dict)
    @property
    def hour(self):
        return WDATimeSpanStats((self.endtime_ts - 86400, self.endtime_ts), self.db, 3600, 'hour',
                             self.formatter, self.converter, **self.option_dict)

    @property
    def sixhour(self):
        return WDATimeSpanStats((self.endtime_ts - 604800, self.endtime_ts), self.db, 21600, 'sixhour',
                             self.formatter, self.converter, **self.option_dict)

#===============================================================================
#                    Class WDATimeSpanStats
#===============================================================================

class WDATimeSpanStats(object):
    """Nearly stateless class that holds a binding to a stats database and a timespan.

    This class is the next class in the chain of helper classes.

    When a statistical type is given as an attribute to it (such as 'obj.outTemp'),
    the next item in the chain is returned, in this case an instance of
    StatsTypeHelper, which binds the stats database, the time period, and
    the statistical type all together.

    It also includes a few "special attributes" that allow iteration over certain
    time periods. Example:

       # Iterate by month:
       for monthStats in yearStats.months:
           # Print maximum temperature for each month in the year:
           print monthStats.outTemp.max
    """
    def __init__(self, timespan, db, agg_intvl, context='hour', formatter=weewx.units.Formatter(),
                 converter=weewx.units.Converter(), **option_dict):
        """Initialize an instance of WDATimeSpanStats.

        timespan: An instance of weeutil.Timespan with the time span
        over which the statistics are to be calculated.

        db: The database the stats are to be extracted from.

        context: A tag name for the timespan. This is something like 'minute', 'hour',
        'fifteenminute', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.timespan    = timespan
        self.db          = db
        self.context     = context
        self.agg_intvl   = agg_intvl
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict

    def __getattr__(self, stats_type):
        """Return a helper object that binds the database, a time period,
        and the given statistical type.

        stats_type: A statistical type, such as 'outTemp', or 'outHumidity'

        returns: An instance of class WDAStatsTypeHelper."""

        # The following is so the Python version of Cheetah's NameMapper doesn't think
        # I'm a dictionary:
        if stats_type == 'has_key':
            raise AttributeError

        # Return the helper class, bound to the type:
        return WDAStatsTypeHelper(stats_type, self.timespan, self.db, self.agg_intvl, self.context, self.formatter, self.converter, **self.option_dict)

#===============================================================================
#                    Class WDAStatsTypeHelper
#===============================================================================

class WDAStatsTypeHelper(object):
    """This is the final class in the chain of helper classes. It binds the statistical
    database, a time period, and a statistical type all together.

    When an aggregation type (eg, 'maxQuery') is given as an attribute to it, it runs the
    query against the database, assembles the result, and returns it as a list of ValueHelpers.
    For example 'maxQuery' will return a list of ValueHelpers each with the 'max' value of the
    observation over the aggregateion period.
    Whilst the aggregation types are similar to those in the WDAStatsTypeHelper class since we
    are seeking a list of aggregates over a number of periods the aggregate types are 'maxQuery',
    'minQuery' etc to distinguish them from the standard 'max, 'min' etc aggregagtes.
    """

    def __init__(self, stats_type, timespan, db, agg_intvl, context, formatter=weewx.units.Formatter(), converter=weewx.units.Converter(), **option_dict):
        """ Initialize an instance of WDAStatsTypeHelper.
        
        In cases where the aggregate interval is greater than the archive interval it
        is not possible to calculate accurate stats over the timespan concerned due 
        to the lack of granularity in the underlying archive data. In these cases the
        results of the query are padded with additional extrapoloated data points.

        stats_type: A string with the stats type (e.g., 'outTemp') for which the query is
        to be done.

        timespan: An instance of TimeSpan holding the time period over which the query is
        to be run

        db: The database the stats are to be extracted from.

        context: A tag name for the timespan. This is something like 'hour', 'fifteenminute',
        'sixhour', etc. This is used to find an appropriate label, if necessary.

        formatter: An instance of weewx.units.Formatter() holding the formatting
        information to be used. [Optional. If not given, the default
        Formatter will be used.]

        converter: An instance of weewx.units.Converter() holding the target unit
        information to be used. [Optional. If not given, the default
        Converter will be used.]

        option_dict: Other options which can be used to customize calculations.
        [Optional.]
        """

        self.stats_type  = stats_type
        self.timespan    = timespan
        self.db          = db
        self.context     = context
        self.agg_intvl   = agg_intvl
        self.formatter   = formatter
        self.converter   = converter
        self.option_dict = option_dict
        _current_rec = db.getRecord(timespan[1])
        self.interval = _current_rec['interval']*60

    def maxQuery(self):
        final = []
        if self.interval <= self.agg_intvl or self.context != 'minute':
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, 'max')
            for elm in result[1][0]:
                final.append(weewx.units.ValueHelper((elm,result[1][1],result[1][2]), self.context, self.formatter, self.converter))
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0]-self.interval, self.timespan[1], self.agg_intvl, 'max')
            vector_ts = self.timespan[0]+self.interval
            vec_counter=1
            for i in range(60):
                try:
                    curr_vector_ts = result[0][0][vec_counter]
                    min_time=int((self.timespan[0]+60)+i*60)
                    if min_time < curr_vector_ts:
                        try:
                            res=result[1][0][vec_counter] - (curr_vector_ts - min_time)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                    elif min_time == curr_vector_ts:
                        final.append(weewx.units.ValueHelper((result[1][0][vec_counter],result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                        vec_counter += 1
                    else:
                        vec_counter += 1
                        try:
                            res=result[1][0][vec_counter]+(min_time-curr_vector_ts)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                except:
                    final.append(weewx.units.ValueHelper((0,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
        return final

    def minQuery(self):
        final = []
        if self.interval <= self.agg_intvl or self.context != 'minute':
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, 'min')
            for elm in result[1][0]:
                final.append(weewx.units.ValueHelper((elm,result[1][1],result[1][2]), self.context, self.formatter, self.converter))
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0]-self.interval, self.timespan[1], self.agg_intvl, 'min')
            vector_ts = self.timespan[0]+self.interval
            vec_counter=1
            for i in range(60):
                try:
                    curr_vector_ts = result[0][0][vec_counter]
                    min_time=int((self.timespan[0]+60)+i*60)
                    if min_time < curr_vector_ts:
                        try:
                            res=result[1][0][vec_counter] - (curr_vector_ts - min_time)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                    elif min_time == curr_vector_ts:
                        final.append(weewx.units.ValueHelper((result[1][0][vec_counter],result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                        vec_counter += 1
                    else:
                        vec_counter += 1
                        try:
                            res=result[1][0][vec_counter]+(min_time-curr_vector_ts)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                except:
                    final.append(weewx.units.ValueHelper((0,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
        return final

    def avgQuery(self):
        final = []
        if self.interval <= self.agg_intvl or self.context != 'minute':
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, 'avg')
            for elm in result[1][0]:
                final.append(weewx.units.ValueHelper((elm,result[1][1],result[1][2]), self.context, self.formatter, self.converter))
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0]-self.interval, self.timespan[1], self.agg_intvl, 'avg')
            vector_ts = self.timespan[0]+self.interval
            vec_counter=1
            for i in range(60):
                try:
                    curr_vector_ts = result[0][0][vec_counter]
                    min_time=int((self.timespan[0]+60)+i*60)
                    if min_time < curr_vector_ts:
                        try:
                            res=result[1][0][vec_counter] - (curr_vector_ts - min_time)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                    elif min_time == curr_vector_ts:
                        final.append(weewx.units.ValueHelper((result[1][0][vec_counter],result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                        vec_counter += 1
                    else:
                        vec_counter += 1
                        try:
                            res=result[1][0][vec_counter]+(min_time-curr_vector_ts)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                except:
                    final.append(weewx.units.ValueHelper((0,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
        return final

    def sumQuery(self):
        final = []
        if self.interval <= self.agg_intvl or self.context != 'minute':
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, 'sum')
            for elm in result[1][0]:
                final.append(weewx.units.ValueHelper((elm,result[1][1],result[1][2]), self.context, self.formatter, self.converter))
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0]-self.interval, self.timespan[1], self.agg_intvl, 'sum')
            vector_ts = self.timespan[0]+self.interval
            vec_counter=1
            for i in range(60):
                try:
                    curr_vector_ts = result[0][0][vec_counter]
                    min_time=int((self.timespan[0]+60)+i*60)
                    if min_time < curr_vector_ts:
                        try:
                            res=result[1][0][vec_counter] - (curr_vector_ts - min_time)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                    elif min_time == curr_vector_ts:
                        final.append(weewx.units.ValueHelper((result[1][0][vec_counter],result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                        vec_counter += 1
                    else:
                        vec_counter += 1
                        try:
                            res=result[1][0][vec_counter]+(min_time-curr_vector_ts)/float(self.interval)*(result[1][0][vec_counter]-result[1][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
                except:
                    final.append(weewx.units.ValueHelper((0,result[1][1],result[1][2]), 'minute', self.formatter, self.converter))
        return final

    def datetimeQuery(self):
        final = []
        if self.interval <= self.agg_intvl or self.context != 'minute':
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, 'max')
            for elm in result[0][0]:
                final.append(weewx.units.ValueHelper((elm,result[0][1],result[0][2]), self.context, self.formatter, self.converter))
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0]-self.interval, self.timespan[1], self.agg_intvl, 'max')
            vector_ts = self.timespan[0]+self.interval
            vec_counter=1
            for i in range(60):
                try:
                    curr_vector_ts = result[0][0][vec_counter]
                    min_time=int((self.timespan[0]+60)+i*60)
                    if min_time < curr_vector_ts:
                        try:
                            res=result[0][0][vec_counter] - (curr_vector_ts - min_time)/float(self.interval)*(result[0][0][vec_counter]-result[0][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[0][1],result[0][2]), 'minute', self.formatter, self.converter))
                    elif min_time == curr_vector_ts:
                        final.append(weewx.units.ValueHelper((result[0][0][vec_counter],result[0][1],result[0][2]), 'minute', self.formatter, self.converter))
                        vec_counter += 1
                    else:
                        vec_counter += 1
                        try:
                            res=result[0][0][vec_counter]+(min_time-curr_vector_ts)/float(self.interval)*(result[0][0][vec_counter]-result[0][0][vec_counter-1])
                        except:
                            res=0
                        final.append(weewx.units.ValueHelper((res,result[0][1],result[0][2]), 'minute', self.formatter, self.converter))
                except:
                    final.append(weewx.units.ValueHelper((self.timespan[1],result[0][1],result[0][2]), 'minute', self.formatter, self.converter))
        return final

    def __getattr__(self, aggregateType):
        """Return statistical summary using a given aggregateType.

        aggregateType: The type of aggregation over which the summary is to be done.
        This is normally something like 'sum', 'min', 'mintime', 'count', etc.
        However, there are two special aggregation types that can be used to
        determine the existence of data:
          'exists':   Return True if the observation type exists in the database.
          'has_data': Return True if the type exists and there is a non-zero
                      number of entries over the aggregation period.

        returns: For special types 'exists' and 'has_data', returns a Boolean
        value. Otherwise, a ValueHelper containing the aggregation data."""

        if aggregateType == 'exists':
            return self.stats_type in self.db.sqlkeys
        elif aggregateType == 'has_data':
            return self.stats_type in self.db.sqlkeys and self.db.getSqlVectors(self.stats_type, self.timespan.start, self.timespan.stop , self.agg_intvl, 'count')[0] != 0
        else:
            result = self.db.getSqlVectors(self.stats_type, self.timespan[0], self.timespan[1], self.agg_intvl, aggregateType)
        # Wrap the result in a ValueHelper:
        return self.converter.convert(result[1])
