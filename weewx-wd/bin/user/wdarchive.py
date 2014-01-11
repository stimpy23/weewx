#
#
#    $Revision: 0002 $
#    $Author: gjroderick $
#    $Date: 22 August 2013 23:25 $
#
"""Subclasses to support custom stats in the Weewx stats database.

  Weewx records wind obs as a vactor type in the stats database as a combination
of windSpeed and windGust. Thus the stats database cannot provide aggregate statistics
for just windSpeed. Custom obs windAv has been added to the stats database to record windSpeed
only. windAV is a vector type and thus provides speed and direction info.

  Custom stat outTempDay and OutTempNight record outTemp for Day (6AM to 6PM) and Night
(6PM-6AM) to enable production of aggregate statistics for daytime and nighttime temperatures.

  Service wxengine.StdArchive has been subclassed along with class accum.WXAccum
"""
import weewx
import weeutil.weeutil
import user.wdarchive
import weedb 
import weewx.stats
import time
import sys
import syslog

from weewx.wxengine import StdArchive
from weewx.accum import BaseAccum, WXAccum, VecStats, OutOfSpan
from weewx.stats import StatsDb, _sql_create_string_factory, meta_create_str, meta_replace_str
from datetime import datetime

class WDArchive(StdArchive):
    """Subclass of StdArchive to facilitate subclassing of WXAccum and StatsDb in
    support of custom stats in stats database.
    """
    def _new_accumulator(self, timestamp):
        start_archive_ts = weeutil.weeutil.startOfInterval(timestamp,
                                                           self.archive_interval)
        end_archive_ts = start_archive_ts + self.archive_interval
        
        # Call subclass WDWXAccum in lieu of WXAccum to get a new accumulator
        new_accumulator =  user.wd.WDWXAccum(weeutil.weeutil.TimeSpan(start_archive_ts, end_archive_ts))
        return new_accumulator

    def setupStatsDatabase(self, config_dict):
        """Setup the stats database using subclass WDStatsDb"""
        
        stats_schema_str = config_dict['StdArchive'].get('stats_schema', 'user.schemas.defaultStatsSchema')
        stats_schema = weeutil.weeutil._get_object(stats_schema_str)
        stats_db = config_dict['StdArchive']['stats_database']
        # This will create the database if it doesn't exist, then return an
        # opened stats database object:
        self.statsDb = user.wdarchive.WDStatsDb.open_with_create(config_dict['Databases'][stats_db], stats_schema)
        # Backfill it with data from the archive. This will do nothing if the
        # stats database is already up-to-date.
        self.statsDb.backfillFrom(self.archive)

        syslog.syslog(syslog.LOG_INFO, "wxengine: Using stats database: %s" % (config_dict['StdArchive']['stats_database'],))
        
class WDStatsDb(StatsDb):
    """Subclass of StatsDb to facilitate custom statistic in stats database.
    Manage reading from the sqlite3 statistical database. Further detail as per
    superclass weewx.stats.StatsDb."""
    
    def __init__(self, connection):
        """Create an instance of StatsDb to manage a database.
        If the database is uninitialized, an exception of type weewx.UninitializedDatabase
        will be raised.
        Subclassed to use WDWXAccum as accumulator in lieu of WXAccum.
        connection: A weedb connection to the stats database. """
        
        self.connection = connection
        try:
            self.std_unit_system = self._getStdUnitSystem()
        except weedb.OperationalError, e:
            self.close()
            raise weewx.UninitializedDatabase(e)
        self.schema = self._getSchema()
        self.statsTypes = self.schema.keys()
        # The class to be used as an accumulator. This can be changed by the
        # calling program.
        self.AccumClass = user.wd.WDWXAccum
        
    @staticmethod
    def open(stats_db_dict):
        """Helper function to return an opened StatsDb object.
        Subclassed to utilise WDStatsDb in lieu of StatsDb.
        stats_db_dict: A dictionary passed on to weedb. It should hold
        the keywords necessary to open the database."""
        connection = weedb.connect(stats_db_dict)
        return WDStatsDb(connection)

    @staticmethod
    def open_with_create(stats_db_dict, stats_schema):
        """Open a StatsDb database, creating and initializing it if necessary.
        Subclassed to utilise WDStatsDb in lieu of StatsDb.
        
        stats_db_dict: A dictionary passed on to weedb. It should hold
        the keywords necessary to open the database.

        stats_schema: an iterable collection of schema-tuples. The first member of the
        tuple is the observation type, the second is either the string 'REAL' (scalar value), 
        or 'VECTOR' (vector value). The database will be initialized to collect stats
        for only the given types.
        
        Returns:
        An instance of StatsDb"""

        # If the database exists and has been initialized, then
        # this will be successful. If not, an exception will be thrown.
        try:
            stats = WDStatsDb.open(stats_db_dict)
            # The database exists and has been initialized. Return it.
            return stats
        except (weedb.OperationalError, weewx.UninitializedDatabase):
            pass
        
        # The database does not exist. Initialize and return it.
        _connect = WDStatsDb._init_db(stats_db_dict, stats_schema)
        
        return WDStatsDb(_connect)

    @staticmethod
    def _init_db(stats_db_dict, stats_schema):
        """Create and initialize a database.
        Subclassed to utilise WDStatsDb in lieu of StatsDb."""
        
        # First, create the database if necessary. If it already exists, an
        # exception will be thrown.
        try:
            weedb.create(stats_db_dict)
        except weedb.DatabaseExists:
            pass

        # Get a connection
        _connect = weedb.connect(stats_db_dict)
        
        try:
            # Now create all the necessary tables as one transaction:
            with weedb.Transaction(_connect) as _cursor:
                for _stats_tuple in stats_schema:
                    # Get the SQL string necessary to create the type:
                    _sql_create_str = _sql_create_string_factory(_stats_tuple)
                    _cursor.execute(_sql_create_str)
                # Now create the meta table:
                _cursor.execute(meta_create_str)
                # Set the unit system to 'None' (Unknown) for now
                _cursor.execute(meta_replace_str, ('unit_system', 'None'))
                # Finally, save the stats schema:
                WDStatsDb._save_schema(_cursor, stats_schema)
        except Exception, e:
            _connect.close()
            syslog.syslog(syslog.LOG_ERR, "stats: Unable to create stats database.")
            syslog.syslog(syslog.LOG_ERR, "****   %s" % (e,))
            raise
    
        syslog.syslog(syslog.LOG_NOTICE, "stats: Created schema for statistical database")

        return _connect
        
    def addRecord(self, record):
        """Using an archive record, update the high/lows and count of a stats database."""
        
        # Get the start-of-day for the record:
        _sod_ts = weeutil.weeutil.startOfArchiveDay(record['dateTime'])
        # Get the stats seen so far:
        _stats_dict = self._getDayStats(_sod_ts)
        # Update them with the contents of the record:
        _stats_dict.addRecord(record)
        # Then save the results:
        self._setDayStats(_stats_dict, record['dateTime'])
        
    def backfillFrom(self, archiveDb, start_ts = None, stop_ts = None):
        """Fill the statistical database from an archive database.
        
        Normally, the stats database if filled by LOOP packets (to get maximum time
        resolution), but if the database gets corrupted, or if a new user is
        starting up with imported wview data, it's necessary to recreate it from
        straight archive data. The Hi/Lows will all be there, but the times won't be
        any more accurate than the archive period.
        
        archiveDb: An instance of weewx.archive.Archive
        
        start_ts: Archive data with a timestamp greater than this will be
        used. [Optional. Default is to start with the first datum in the archive.]
        
        stop_ts: Archive data with a timestamp less than or equal to this will be
        used. [Optional. Default is to end with the last datum in the archive.]
        
        returns: The number of records backfilled."""
        
        syslog.syslog(syslog.LOG_DEBUG, "stats: Backfilling stats database.")
        t1 = time.time()
        nrecs = 0
        ndays = 0
        
        _statsDict = None
        _lastTime  = None
        
        # If a start time for the backfill wasn't given, then start with the time of
        # the last statistics recorded:
        if start_ts is None:
            start_ts = self._getLastUpdate()
        
        # Go through all the archiveDb records in the time span, adding them to the
        # database
        for _rec in archiveDb.genBatchRecords(start_ts, stop_ts):
    
            # Get the start-of-day for the record:
            _sod_ts = weeutil.weeutil.startOfArchiveDay(_rec['dateTime'])
            # If this is the very first record, fetch a new accumulator
            if not _statsDict:
                _statsDict = self._getDayStats(_sod_ts)
            # Try updating. If the time is out of the accumulator's time span, an
            # exception will get thrown.
            try:
                _statsDict.addRecord(_rec)
            except weewx.accum.OutOfSpan:
                # The record is out of the time span.
                # Save the old accumulator:
                self._setDayStats(_statsDict, _rec['dateTime'])
                ndays += 1
                # Get a new accumulator:
                _statsDict = self._getDayStats(_sod_ts)
                # try again
                _statsDict.addRecord(_rec)
             
            # Remember the timestamp for this record.
            _lastTime = _rec['dateTime']
            nrecs += 1
            if nrecs%1000 == 0:
                print >>sys.stdout, "Records processed: %d; Last date: %s\r" % (nrecs, weeutil.weeutil.timestamp_to_string(_lastTime)),
                sys.stdout.flush()
    
        # We're done. Record the stats for the last day.
        if _statsDict:
            self._setDayStats(_statsDict, _lastTime)
            ndays += 1
        
        t2 = time.time()
        tdiff = t2 - t1
        if nrecs:
            syslog.syslog(syslog.LOG_NOTICE, 
                          "stats: backfilled %d days of statistics with %d records in %.2f seconds" % (ndays, nrecs, tdiff))
        else:
            syslog.syslog(syslog.LOG_INFO,
                          "stats: stats database up to date.")
    
        return nrecs
        