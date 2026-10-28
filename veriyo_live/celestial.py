"""Offline sky and topocentric Moon. UTC≈UT1; no terrain or weather model."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from pymeeus.Angle import Angle
from pymeeus.Earth import Earth
from pymeeus.Epoch import Epoch
from pymeeus.Moon import Moon
from pymeeus.Sun import Sun
from .calendar import CUTOVER, EPOCH, ZONE
from .sky import check_day, julian_day


def sidereal(moment, longitude):
    check_day(moment.astimezone(timezone.utc).date())
    return (Epoch(julian_day(moment)).mean_sidereal_time() * 360 + longitude) % 360


def horizontal(ra, dec, latitude, lst):
    hour, dec, lat = map(math.radians, (lst-ra, dec, latitude))
    east = -math.cos(dec)*math.sin(hour)
    north = math.sin(dec)*math.cos(lat)-math.cos(dec)*math.cos(hour)*math.sin(lat)
    up = math.sin(dec)*math.sin(lat)+math.cos(dec)*math.cos(hour)*math.cos(lat)
    return math.degrees(math.asin(max(-1, min(1, up)))), math.degrees(math.atan2(east, north)) % 360


@lru_cache(maxsize=1)
def bright_catalog():
    return json.loads((Path(__file__).parent/'assets/bright-stars.json').read_text(encoding='utf-8'))['stars']


@lru_cache(maxsize=8)
def equatorial_stars(day):
    target = Epoch(julian_day(datetime.combine(day, time(12), timezone.utc)))
    t = (float(target)-2451545.0)/36525
    zeta = math.radians((2306.2181*t+.30188*t*t+.017998*t*t*t)/3600)
    z = math.radians((2306.2181*t+1.09468*t*t+.018203*t*t*t)/3600)
    theta = math.radians((2004.3109*t-.42665*t*t-.041833*t*t*t)/3600)
    result = []
    for star in bright_catalog():
        pm_ra = star['pmra']/(3600000*math.cos(math.radians(star['dec'])))
        ra = math.radians(star['ra']+pm_ra*t*100)
        dec = math.radians(star['dec']+star['pmdec']/3600000*t*100)
        # IAU 1976 precession. atan2 keeps declination stable at both poles.
        a = math.cos(dec)*math.sin(ra+zeta)
        b = math.cos(theta)*math.cos(dec)*math.cos(ra+zeta)-math.sin(theta)*math.sin(dec)
        c = math.sin(theta)*math.cos(dec)*math.cos(ra+zeta)+math.cos(theta)*math.sin(dec)
        ra = math.degrees(math.atan2(a,b)+z) % 360
        dec = math.degrees(math.atan2(c,math.hypot(a,b)))
        result.append((star['id'], star['name'], ra, dec, star['mag']))
    return tuple(result)


@lru_cache(maxsize=8)
def stars_at(second, latitude, longitude):
    moment = datetime.fromtimestamp(second, timezone.utc)
    lst = sidereal(moment, longitude)
    return tuple((hip, name, *horizontal(ra, dec, latitude, lst), mag)
                 for hip, name, ra, dec, mag in equatorial_stars(moment.date()))


@lru_cache(maxsize=4096)
def lunar_equatorial(minute):
    moment = datetime.fromtimestamp(minute*60, timezone.utc)
    check_day(moment.date())
    # Meeus lunar series expects TT, while Earth rotation uses UTC≈UT1.
    epoch = Epoch(julian_day(moment) + Epoch.tt2ut(moment.year, moment.month)/86400)
    ra, dec, distance, _ = Moon.apparent_equatorial_pos(epoch)
    return float(ra), float(dec), distance


@dataclass(frozen=True)
class LunarPosition:
    altitude: float
    azimuth: float
    distance: float
    illumination: float
    waxing: bool
    tilt: float


@lru_cache(maxsize=512)
def lunar_phase(minute):
    moment = datetime.fromtimestamp(minute*60, timezone.utc)
    epoch = Epoch(julian_day(moment) + Epoch.tt2ut(moment.year, moment.month)/86400)
    lon, _, _, _ = Moon.apparent_ecliptical_pos(epoch)
    sun_lon, _ = Sun.apparent_longitude_coarse(epoch)
    return Moon.illuminated_fraction_disk(epoch), (float(lon)-float(sun_lon)) % 360 < 180, float(Moon.position_bright_limb(epoch))


def moon_horizontal(moment, latitude, longitude):
    minute = math.floor(moment.timestamp()/60)
    ra, dec, distance = lunar_equatorial(minute)
    lst = sidereal(moment, longitude)
    top_ra, top_dec = Earth.parallax_correction(Angle(ra), Angle(dec), Angle(latitude),
                                              float(distance/149597870.7), Angle(lst-ra))
    altitude, azimuth = horizontal(float(top_ra), float(top_dec), latitude, lst)
    return altitude, azimuth, distance, lst-ra, dec


def moon_at(moment, latitude, longitude):
    altitude, azimuth, distance, hour, dec = moon_horizontal(moment, latitude, longitude)
    illumination, waxing, limb = lunar_phase(math.floor(moment.timestamp()/60))
    hour, lat, dec = map(math.radians, (hour, latitude, dec))
    q = math.degrees(math.atan2(math.sin(hour), math.tan(lat)*math.cos(dec)-math.sin(dec)*math.cos(hour)))
    return LunarPosition(altitude, azimuth, distance, illumination, waxing, limb-q-90)


def local_day_bounds(day, zone_name):
    zone = ZoneInfo(zone_name)
    return (datetime.combine(day, time(), zone).astimezone(timezone.utc),
            datetime.combine(day+timedelta(days=1), time(), zone).astimezone(timezone.utc))


@lru_cache(maxsize=32)
def moon_day(day, latitude, longitude, zone_name):
    """Today's path and approximate upper-limb rise/set over a flat horizon.

    Refraction + apparent lunar radius ≈ 0.833 degrees. Cached ephemeris at
    one-minute intervals is sufficient for minute-level decorative rise times.
    Search actual UTC duration, including 23/25-hour local DST days.
    """
    start, end = local_day_bounds(day, zone_name)
    duration = (end-start).total_seconds()
    count = math.ceil(duration/1200)
    samples = []
    events = []
    for i in range(count+1):
        moment = start+timedelta(seconds=min(duration, i*1200))
        alt, az, *_ = moon_horizontal(moment, latitude, longitude)
        samples.append((moment, alt, az))
        if i:
            previous, old_alt, _ = samples[-2]
            if (old_alt+.833)*(alt+.833) < 0:
                left, right = previous, moment
                rising = alt > old_alt
                while (right-left).total_seconds() > 2:
                    middle = left+(right-left)/2
                    value = moon_horizontal(middle, latitude, longitude)[0]+.833
                    if (value > 0) == rising:
                        right = middle
                    else:
                        left = middle
                events.append(('Nousu' if rising else 'Lasku', left+(right-left)/2))
    return tuple(samples), tuple(events)


def blood_progress(moment):
    local = moment.astimezone(ZONE)
    day = local.date()-timedelta(days=local.time() < CUTOVER)
    ordinal = (day-EPOCH).days
    start = datetime.combine(day, CUTOVER, ZONE).astimezone(timezone.utc)
    end = datetime.combine(day+timedelta(days=1), CUTOVER, ZONE).astimezone(timezone.utc)
    fraction = (moment.astimezone(timezone.utc)-start).total_seconds()/(end-start).total_seconds()
    return ordinal, fraction, ((ordinal % 777)+fraction)/777
