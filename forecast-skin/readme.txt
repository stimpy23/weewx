This is a sample forecasting template for the weewx weather system.
Copyright 2013 Matthew Wall

This package includes forecast.inc and icons.  forecast.inc is a cheetah
template file designed to be included in other templates.  At the beginning
of forecast.inc is a list of variables that determine which forecast data
will be displayed.  The icons directory contains images for cloud cover,
storms, etc.

Credits:

Icons were derived from Adam Whitcroft's climacons.

Installation instructions:

1) expand the tarball:

cd /var/tmp
tar xvfz /var/tmp/forecast-for-weewx.tgz

2) copy files to the skin:

cp forecast.inc /home/weewx/skins/Standard
cp -rp icons /home/weewx/skins/Standard

3) add the include and icons to the [CopyGenerator] section of skin.conf:

[CopyGenerator]
    copy_once = ..., icons/*

4) add this to a template file where the forecast table should be displayed:

#include '/home/weewx/skins/Standard/forecast.inc'

5) modify forecast.inc to indicate which data should be displayed

6) either restart weewx, or copy the icons directly

cp -rp icons /home/weewx/public_html
