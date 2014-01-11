
# WEEWX-WD
  
**NOTE:** This is BETA Early Release Software so use it at your own risk.  
**NOTE:** To use Weewx-WD to its fullest extent requires additions to the Weewx archive and stats schemas.  
  
This Weewx skin (Weewx-WD) will generate the files required drive Weather Display Live (WDL), the Steel Series gauges and the Carter Lake/Saratoga HTML templates.

## Features
Weewx-WD produces the following files required by WDL, Steel Gauge and Carter Lake/Saratoga HTML templates:

WDL

* WD\Clientraw.txt
* WD\Clientrawextra.txt
* WD\Clientrawdaily.txt
* WD\Clientrawhour.txt

Steel Series Gauges

* WD\Customclientraw.txt

Carter Lake/Saratoga templates

* WD\testtags.php

## Limitations
Whilst Weewx-WD produces the necessary data files required by WDL, Steel Gauge and Carter Lake/Saratoga HTML templates these files are only updated at the end of every Weewx archive period. Therefore live updates from LOOP data are not possible at this time. The live update aspects of the WDL, Steel Gauge and Carter Lake/Saratoga HTML templates should still work, but the data will not change except at the end of every archive period.

Weewx has been extended through Weewx-WD to provide most of the tags provided by WD; however, at this time there are a number of tags that are not yet provided and there are likely a number of tags that never will be provided. A list of these outstanding tags are included on the Weewx-WD Wiki [Tags](https://bitbucket.org/ozgreg/weewx-wd/wiki/Tags "Tags") page.

## Prerequisites
Weewx-WD **requires** a fully functioning installation of **Weewx version 2.5.0 or greater**. The operation of Weewx-WD is unaffected by the database server used by Weewx, nor is it effected by the version of PHP installed or the presence or otherwise of a web server. However, in order to use the Weewx-WD generated files to drive WDL, the Steel Series gauges or the Carter Lake/Saratoga templates then these additional applications/templates must be installed and configured. The Carter Lake/Saratoga templates requires the WD plugin, a supporting icon set and a PHP GD capable web server if weather graphics such as the dashboard thermometer is to be displayed. Detailed instructions are available from the [Saratoga Weather](http://saratoga-weather.org/index.php "Saratoga Weather") site.

## Extra observations

Although Weewx has a substantial temperature measurement capability, Weather Display (WD) provides two calculated temperature related observations, Humidex and Apparent Temperature, that Weewx does not provide. To allow aggregate statistics and graphing of these additional observations they have been captured in extraTemp1 and extraTemp2 respectively in the Weewx archive and stats databases.


Whilst Weewx records both windSpeed and windGust data separately in the archive database, the stats database records a vector type wind which is a composite of windSpeed and windGust. Consequently, Weewx cannot provide aggregate statistics on windSpeed data alone. To provide aggregate statistics on windSpeed alone, an additional field, windAv, has been added to the Weewx statistics database. WindAv records data on the windSpeed observation only.

## File locations

Installation of Weewx-WD requires knowledge of the locations of certain portions of the Weewx installation. The following locations are used throughout this document and they refer to the locations listed in the [Weewx User's Guide](http://weewx.com/docs/usersguide.htm "Weewx User's Guide"):  

- $BIN\_ROOT (Executables)  
- $CONFIG\_ROOT (Configuration directory)  
- $SKIN\_ROOT (Skins and templates)  
- $SQLITE\_ROOT (Sqlite databases)  
- $HTML_ROOT (Web pages and images)  

## How to install this skin

**Note:** When installing Weewx-WD only download and install the 'master' branch. Download and installation of any other branch such as 'development' without specific instruction to do so may result in an dysfunctional installation.

1. Download and unzip the files

    * Copy the `Clientraw` and `Testtags` folders (located in the .zip `\skins` folder) and their contents to the Weewx `$SKIN_ROOT` folder.
    * Copy the contents of the `user` folder (located in the .zip `\bin` folder) to the Weewx `$BIN_ROOT` folder.

1. Edit `$CONFIG_ROOT/weewx.conf`.  
    * In the `[StdReport]` section add the following:  
   
			# Generate WD clientraw files  
			[[Clientraw]]  
				skin = Clientraw  
				HTML_ROOT = public_html/WD  
				
			# Generate WD testtags.php file  
			[[Testtags]]  
				skin = Testtags  
				HTML_ROOT = public_html/WD  
	
		Where `public_html` is either a relative path (relative to `$WEEWX_ROOT`) or an absolute path. Any name can be used in place of `WD`. The location of the clientraw and testtags.php files should be set appropriately in the WDL, Steel Series gauges and/or Carter Lake/Saratoga templates config files.

    * In the `[Engines], [[WxEngines]]` section add the following text to the `service_list` setting in place of `weewx.wxengine.StdArchive`:  

			user.wd.WD, user.wdarchive.WDArchive
		Check to ensure that each entry in the `service_list` setting is separated by a comma and space.  

1. In the `$SKIN_ROOT` folder edit the `Testtags/skin.conf` file as follows:
    * In the `[Units], [[Groups]]` section edit the units to suit your requirements. These settings must reflect the uom settings in the Saratoga templates `Settings.php` file or there will likely be incorrect observations displayed on your site.
    * In the `[Units], [[TimeFormats]]` section set the date/time format strings as required. These format strings set the format for date and time tags in the `testtags.php` file produced by Weewx-WD.  

            [[TimeFormats]]
               # Following format settings are used by the weewx-wd templates. They do not necessarily reflect
               # the format that will be displayed by your site, rather they reflect the formats produced in
               # the weewx-wd generated files. If used with the Saratoga templates there are separeate settings
               # within the Saratoga templates that determine the date and time formats displayed.
               # The formats use the standard Python strftime() date/time format strings as referenced in the
               # Weewx Customization Guide. Whilst any valid format can be used, correct operation of Saratoga
               # templates requires the use of a limited number of set formats. Some settings have only one
               # available format (eg Seconds - %S) other have more or are free form. Where a setting is limited
               # to a particular format or group of formats, the available formats are listed in the comments
               # against the setting.
               #
               time_f         = %H:%M                # Time. Must be %H:%M. Required for 24 hour clock.
               second_f       = %S                   # Second. Must be %S.
               minute_f       = %M                   # Minute. Must be %M.
               hour_f         = %H                   # Hour. Must be %H. Required for 24 hour clock.
               date_f         = %-d/%-m/%Y           # Date. %d/%m/%Y or %m/%d/%Y only. %-d or %-m may be used
                                                     # to remove day and/or month leading zero. Must agree
                                                     # with Saratoga $SITE['WDdateMDY'] setting.
               day_f          = %-d                  # Day of month. Must be %d or %-d (to remove 
                                                     # leading zero)
               day_name_f     = %A                   # Day name. %a (abbrev name) or %A (full name)
               day_of_week_f  = %w                   # Day of week. Must be %w
               day_of_year_f  = %j                   # Day of year. Must be %j
               month_f        = %-m                  # Month number. Must be %m or %-m (to remove
                                                     # leading zero)
               month_name_f   = %B                   # Month name. %b (abbreviated name) or %B (full name)
               year_f         = %Y                   # Year. %y (2 digit) or %Y (4 digit)
               date_time_f    = %-d/%-m/%Y %H:%M     # Date and time. May be any valid combination
               ephem_f        = %H:%M UTC %-d %B %Y  # Ephemeris date time. May be any valid combination.
               record_f       = %-d %b %Y            # Record date format. Must be %d %b %Y or %b %d %Y.
                                                     # Must agree with Saratoga $SITE['WDdateMDY'] setting.
               #
               # Following format settings are Weewx native date/time formats used as default formats for
               # $day, $week, $month, $year, $rainyear, $current and $almanac date/time tags. Refer to
               # Weewx documentation for their use. The formats may be changed but will normally have no
               # effect on the weewx-wd generated files. They have been retained for completeness.
               #
               day        = %H:%M
               week       = %H:%M on %A
               month      = %d-%b-%Y %H:%M
               year       = %d-%b-%Y %H:%M
               rainyear   = %d-%b-%Y %H:%M
               current    = %d-%b-%Y %H:%M
               ephem_day  = %H:%M
               ephem_year = %d-%b-%Y %H:%M

1. Edit the `$SKIN_ROOT/Clientraw/skin.conf` file and set the time format as per the `Testtags/skin.conf` file. These format strings set the format for date and time tags in the `clientraw` files produced by Weewx-WD.  

       **Note**: Do **NOT** edit the unit settings under `[Units], [[Groups]]` in `$SKIN_ROOT/Clientraw/skin.conf`. The clientraw family of files use fixed units and any changes to the default `$SKIN_ROOT/Clientraw/skin.conf` unit settings may have unintended consequences in the clientraw output.

1. Edit the file `$BIN_ROOT/user/schemas.py` as follows:  

    * locate the line starting with `stats_types =`. It should be similar to: 

            stats_types = ['barometer', 'inTemp', 'outTemp', 'inHumidity', 'outHumidity',  
                           'rainRate', 'rain', 'dewpoint', 'windchill', 'heatindex', 'ET',  
                           'radiation', 'UV', 'extraTemp1', 'rxCheckPercent', 'wind']  

    * add the following additional code before the closing square bracket:  

            , 'extraTemp2', 'windAv', 'outTempDay', 'outTempNight'

    * the resulting line should be similar to:  

            stats_types = ['barometer', 'inTemp', 'outTemp', 'inHumidity', 'outHumidity',  
                           'rainRate', 'rain', 'dewpoint', 'windchill', 'heatindex', 'ET',  
                           'radiation', 'UV', 'extraTemp1', 'rxCheckPercent', 'wind',  
                           'extraTemp2', 'windAv', 'outTempDay', 'outTempNight']  

    * locate the line starting with `defaultStatsSchema =`. It should be similar to: 

            defaultStatsSchema= [_tuple for _tuple in defaultArchiveSchema if _tuple[0] in stats_types] + [('wind', 'VECTOR')]

    * add the following additional code after the last closing square bracket:  

            + [('windAv', 'VECTOR')] + [('outTempDay', 'REAL')] + [('outTempNight', 'REAL')]

    * the resulting line should be similar to:  

            defaultStatsSchema= [_tuple for _tuple in defaultArchiveSchema if _tuple[0] in stats_types] + [('wind', 'VECTOR')] + [('windAv', 'VECTOR')] + [('outTempDay', 'REAL')] + [('outTempNight', 'REAL')]

1. Edit the file `$BIN_ROOT/user/extensions.py` and add the following code:
    * immediately before the line `import locale`:

            import weewx.units

    * at the end of the file:

            # 
            # This code sets units/groups to be used for custom stats/obs added to Weewx
            # 
            #extraTemp2 - apparent temperature
            weewx.units.obs_group_dict['extraTemp2'] = 'group_temperature'
            weewx.units.USUnits['extraTemp2'] = 'degree_F'
            weewx.units.MetricUnits['extraTemp2'] = 'degree_C'
            #windAv - average (over archive period) wind speed
            weewx.units.obs_group_dict['windAv'] = 'group_speed'
            weewx.units.USUnits['windAv'] = 'mile_per_hour'
            weewx.units.MetricUnits['windAv'] = 'km_per_hour'
            #outTempDay and outTempNight - day and night temps
            weewx.units.obs_group_dict['outTempDay'] = 'group_temperature'
            weewx.units.USUnits['outTempDay'] = 'degree_F'
            weewx.units.MetricUnits['outTempDay'] = 'degree_C'
            weewx.units.obs_group_dict['outTempNight'] = 'group_temperature'
            weewx.units.USUnits['outTempNight'] = 'degree_F'
            weewx.units.MetricUnits['outTempNight'] = 'degree_C'
            #
            #   End of code to code sets units/groups to be used for custom stats/obs added to Weewx
            #

1. Stop Weewx if it was running.
1. The stats database (located in the `$CONFIG_ROOT` folder) must be rebuilt to include the new statistics. This can be achieved by either:
    * deleting the stats database now for it to be rebuilt when Weewx is next started, or
    * rebuilding the stats database via the `wee_config_database --backfill-stats` utility.
1. Start Weewx.
1. If using the Saratoga templates:

    * Ensure that the Saratoga templates, WD plugin and a supporting icon set have been installed as per the Saratoga template instructions. **Note** that the Saratoga templates must be hosted on a PHP capable web server and that PHP GD package must be installed on the web server if weather graphics such as dashboard thermometer are to be displayed. Detailed instructions are available from the [Saratoga Weather](http://saratoga-weather.org/index.php "Saratoga Weather") site.

    * Edit `Settings.php` and set the following date/time settings. Note the php date/time format codes used for these settings are different to the Python format codes used in `skin.conf`:
        - $SITE['timeFormat']
        - $SITE['timeOnlyFormat']
        - $SITE['dateOnlyFormat']
        - $SITE['WDdateMDY']. Must be set to `true` if Weewx-WD is generating files using Month/Day/Year format or `false` if Weewx-WD is generating files using Day/Month/Year format.  

    * Edit `Settings-weather.php` and ensure the site is set to use WD:  

            $SITE['WXsoftware'] = 'WD'

    * Other settings in `Settings.php`, `Settings-weather.php` and `Settings-language.php` should be set to meet your local requirements.
