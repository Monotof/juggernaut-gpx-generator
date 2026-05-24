# %% code from makew0rld/geohashing

# Based on code from:
# https://github.com/makew0rld/geohashing
# License: CC0-1.0 license


import datetime
import requests
from hashlib import md5
import sys
import argparse

# Websites that return the Dow Jones index in plain text
# The date can be appended to the URL in this format: %Y/%m/%d
DOW_JONES_SOURCES = ["http://geo.crox.net/djia/", "http://www1.geo.crox.net/djia/",
                     "http://www2.geo.crox.net/djia/", "http://carabiner.peeron.com/xkcd/map/data/"]


def get_dow_jones(east=False, date=None):
    """
    The date will be derived from the computer clock, but if it is manually supplied,
    it must be in a datetime.date object.

    Set `east` to true if your current location is East of -30 longitude.
    """
    if date is None:
        date = datetime.date.today()
    if east:  # Subtract a day to make this 30W compliant
        date += datetime.timedelta(days=-1)
    
    date = date.strftime("%Y/%m/%d")
    for url in DOW_JONES_SOURCES:
        try:
            r = requests.get(url + date, timeout=5)
        except requests.exceptions.ReadTimeout:
            continue  # Try another source, this one is offline
        # Otherwise, check and return the result found
        if r.status_code == 200:
            return r.text.strip()

    # All URLs have been tried and failed
    raise Exception("None of the programmed Dow Jones sources are online, or no data exists for your date yet.\nTry providing one manually.")


def get_hash(east=False, date=None, dow_jones=None):
    """Get the md5 hash.

    dow_jones can be a string or number. If it is None, then the current value
    will be used.
    `date` will be derived from the computer clock, but if it is manually supplied,
    it must be in a datetime.date object.

    The hash will be returned as a hexadecimal string.
    """

    if date is None:
        date = datetime.date.today()
    if dow_jones is None:
        dow_jones = get_dow_jones(east, date)
    # Reformat
    dow_jones = str(dow_jones)
    date = date.strftime("%Y-%m-%d")

    return md5(date.encode() + b"-" + dow_jones.encode()).hexdigest()


def hash_to_location(u_lat, u_lon, md5_hash):
    """Returns (lat, lon) as floats."""

    h1 = md5_hash[:16]
    h2 = md5_hash[16:]
    # Append the base10 conversion as decimals
    lat = str(int(u_lat)) + str(float.fromhex("0." + h1))[1:]
    lon = str(int(u_lon)) + str(float.fromhex("0." + h2))[1:]
    return float(lat), float(lon)


def geohash(lat, lon, date=None, dow_jones=None, east=None):
    """Get an xkcd geohash for the supplied position.

    This function is 30W compliant. If `east` is specified than this functionality
    is overrided.
    """

    if east is None:
        east = False
        if lon > -30:
            east = True
    
    return hash_to_location(lat, lon, get_hash(east, date, dow_jones))