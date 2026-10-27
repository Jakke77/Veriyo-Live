"""Catalogue and precession model from Ajanlaskut ja Sää 1.12.3.

Yale BSC5: HR 4301, 4295, 4554, 4660, 4905, 5054, 5191.
Geometric sky: UTC approximates UT1; no refraction, nutation or aberration.
These are orientation illustrations, not an instrument pointing solution.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from functools import lru_cache
import math
from pymeeus.Epoch import Epoch
from pymeeus.Angle import Angle
from pymeeus.Coordinates import precession_equatorial

PROJECTION_SCALE = math.tan(math.radians(25))


def julian_day(moment):
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('Aikaleima tarvitsee aikavyöhykkeen.')
    return moment.timestamp() / 86400 + 2440587.5


def check_day(day):
    if not 1900 <= day.year <= 2100:
        raise ValueError('Tähtilaskenta on saatavilla vuosille 1900–2100.')


@dataclass(frozen=True)
class Star:
    name: str
    ra: float  # J2000 degrees
    dec: float  # J2000 degrees
    magnitude: float
    pm_ra: float = 0.0  # catalogue mu_alpha*cos(delta), arcseconds/year
    pm_dec: float = 0.0  # arcseconds/year


STARS = (
    Star('Dubhe', 165.93208333333334, 61.75083333333333, 1.79, -.119, -.067),
    Star('Merak', 165.4604166666667, 56.3825, 2.37, .082, .034),
    Star('Phecda', 178.4575, 53.69472222222222, 2.44, .095, .012),
    Star('Megrez', 183.85666666666668, 57.0325, 3.31, .104, .009),
    Star('Alioth', 193.50708333333336, 55.959722222222226, 1.77, .112, -.006),
    Star('Mizar', 200.98125, 54.92527777777777, 2.27, .122, -.020),
    Star('Alkaid', 206.885, 49.31333333333333, 1.86, -.122, -.011),
)
LINKS = ((0, 1), (1, 2), (2, 3), (3, 0), (3, 4), (4, 5), (5, 6))


@dataclass(frozen=True)
class StarPosition:
    name: str
    altitude: float  # degrees above geometric horizon
    azimuth: float  # degrees clockwise from true north, east=90
    x: float  # normalized screen coordinates: fixed NCP centre, radius one=50deg
    y: float
    magnitude: float


@lru_cache(maxsize=512)
def _equatorial(day_ordinal):
    """Day-level precession is ample for a minute-of-arc sky illustration."""
    day = date.fromordinal(day_ordinal)
    target = Epoch(julian_day(datetime.combine(day, time(12), timezone.utc)))
    result = []
    for star in STARS:
        # BSC mu_alpha is projected motion; PyMeeus expects d(alpha)/dt.
        pm_ra = star.pm_ra / (3600 * math.cos(math.radians(star.dec)))
        ra, dec = precession_equatorial(
            Epoch(2451545.0), target, Angle(star.ra), Angle(star.dec),
            pm_ra, star.pm_dec / 3600)
        result.append((float(ra), float(dec)))
    return tuple(result)


def sky_at(moment, latitude=65.071562, longitude=25.507046):
    """Seven real geometric positions, local latitude and east-positive longitude."""
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError('Leveysasteen pitää olla välillä −90…90.')
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError('Pituusasteen pitää olla välillä −180…180.')
    jd = julian_day(moment)  # Explicitly reject naive host-local timestamps.
    utc = moment.astimezone(timezone.utc)
    check_day(utc.date())
    sidereal = (Epoch(jd).mean_sidereal_time() * 360 + longitude) % 360
    latitude = math.radians(latitude)
    result = []
    for star, (ra, dec) in zip(STARS, _equatorial(utc.date().toordinal())):
        hour = math.radians(sidereal - ra)
        declination = math.radians(dec)
        east = -math.cos(declination) * math.sin(hour)
        north = (math.sin(declination) * math.cos(latitude)
                 - math.cos(declination) * math.cos(hour) * math.sin(latitude))
        up = (math.sin(declination) * math.sin(latitude)
              + math.cos(declination) * math.cos(hour) * math.cos(latitude))
        altitude = math.degrees(math.asin(max(-1, min(1, up))))
        azimuth = math.degrees(math.atan2(east, north)) % 360
        denominator = (1 + math.sin(declination)) * PROJECTION_SCALE
        x = east / denominator
        y = -math.cos(declination) * math.cos(hour) / denominator
        result.append(StarPosition(star.name, altitude, azimuth, x, y, star.magnitude))
    return tuple(result)
