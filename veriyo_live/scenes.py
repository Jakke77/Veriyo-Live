"""Offline procedural scenes. Astronomy and decorative motion are separate."""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import lru_cache
import math
import os
from pathlib import Path
import random
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPainterPath,
                        QPen, QRadialGradient)
from .calendar import date_block
from .celestial import blood_progress, moon_at, moon_day, stars_at
from .ubuntu_pack import MotionEntry, load_frame, render_motion, write_gnome_slideshow

SCENES = {
    'polaris': ('Pohjantähden tähtitaivas', 'Oikeat kirkkaat tähdet sijaintisi ja ajan mukaan. Valokehät kiertävät hitaasti.'),
    'moon': ('Kuun kulkureitti', 'Todellinen kuunvaihe ja tämän päivän reitti. Reitin valopulssi on koristeellinen.'),
    'bloodwork': ('Veri Ajan taivaankoneisto', 'Seitsemän kehää, kiertävät sinetit ja 777 päivän mukana muuttuva hehku.'),
    'deep_space': ('Hiljainen avaruus', 'Leijuvia kivikappaleita, pehmeästi virtaavaa sumua ja kaukaisten maailmojen valoa.'),
    'stream': ('Metsien puro', 'Virtaavaa vettä, sumua ja metsäkasvillisuutta. Aamu-, päivä-, ilta- ja yövalaistus kellonajan mukaan.'),
    'rose_garden': ('Varjoruusujen puutarha', 'Goottilainen kasvihuone, elävät ruusut, leijuvat terälehdet ja sumussa häilyvä hahmo.'),
    'lighthouse': ('Viimeinen majakka', 'Kiertävä valokeila, vieraan maailman meri, rengasplaneetta ja kaukainen varjo.'),
}
PERIOD = 96


@dataclass(frozen=True)
class SceneEntry:
    settings: object


def circle_point(x, y, radius, angle):
    return QPointF(x+math.cos(angle)*radius, y+math.sin(angle)*radius)


def glow(p, x, y, radius, color, alpha=100):
    gradient = QRadialGradient(QPointF(x, y), radius)
    r, g, b = QColor(color).getRgb()[:3]
    gradient.setColorAt(0, QColor(r, g, b, alpha))
    gradient.setColorAt(.25, QColor(r, g, b, alpha//3))
    gradient.setColorAt(1, QColor(r, g, b, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(gradient)
    p.drawEllipse(QPointF(x, y), radius, radius)


def label(p, rect, value, size=12, color='#c5cee9'):
    from .render import text
    text(p, rect, value, size, color)


@lru_cache(maxsize=4)
def backdrop(theme, width, height):
    """The landscape stays fixed; cache expensive fog and scenery painting."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor('#03050d'))
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(width/1920, height/1080)
    palettes = {'polaris': ('#060d20', '#17203b', '#7598ce'),
                'moon': ('#060b1b', '#222748', '#b6a5d8'),
                'bloodwork': ('#10050e', '#270b20', '#bd375d'),
                'deep_space': ('#07091d', '#161a39', '#6a60d1')}
    top, bottom, accent = palettes[theme]
    gradient = QLinearGradient(0, 0, 0, 1080)
    gradient.setColorAt(0, QColor(top)); gradient.setColorAt(.72, QColor(bottom)); gradient.setColorAt(1, QColor('#02030a'))
    p.fillRect(QRectF(0, 0, 1920, 1080), gradient)
    rng = random.Random(771)
    for i in range(32):
        x = rng.uniform(-100, 1500); y = 250+130*math.sin(i*.18)+rng.uniform(-130, 130)
        glow(p, x, y, rng.uniform(130, 330), accent, rng.randrange(8, 24))
    if theme in ('bloodwork', 'deep_space'):
        for i in range(450):
            x, y = rng.uniform(0, 1920), rng.uniform(0, 1080)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(190, 203, 245, rng.randrange(30, 150)))
            p.drawEllipse(QPointF(x, y), .65, .65)
    else:
        # Still ridges, conifers, mist and a black lake. Original procedural art.
        for layer in range(3):
            path = QPainterPath(QPointF(-10, 1080))
            for x in range(-10, 1940, 12):
                y = 748+layer*45+35*math.sin(x/210+layer)+20*math.sin(x/69+layer)
                path.lineTo(x, y)
            path.lineTo(1940, 1080); path.closeSubpath()
            p.setBrush(QColor(5+layer*2, 10+layer*2, 20+layer*2)); p.setPen(Qt.PenStyle.NoPen); p.drawPath(path)
        for _ in range(100):
            x = rng.uniform(-20, 1960); y = 835+12*math.sin(x/190)
            size = rng.uniform(18, 90)*(1.7 if x < 220 else 1)
            path = QPainterPath(QPointF(x, y-size))
            for k in range(1, 5):
                path.lineTo(x+size*k/13, y-size+k*size/5)
                path.lineTo(x+size*(k-1)/20, y-size+k*size/5)
            path.lineTo(x+size*.4, y); path.lineTo(x-size*.4, y)
            for k in range(4, 0, -1):
                path.lineTo(x-size*(k-1)/20, y-size+k*size/5)
                path.lineTo(x-size*k/13, y-size+k*size/5)
            path.closeSubpath(); p.setBrush(QColor('#02060c')); p.drawPath(path)
        lake = QLinearGradient(0, 855, 0, 1080)
        lake.setColorAt(0, QColor('#111b2b')); lake.setColorAt(1, QColor('#02040b'))
        p.fillRect(QRectF(0, 855, 1920, 225), lake)
        for i in range(40):
            y = 862+i*5
            p.setPen(QPen(QColor(115, 137, 183, max(1, 19-i//2)), .8))
            p.drawLine(QPointF(110+i*11, y), QPointF(1130-i*8, y))
    p.end()
    return image


def sky_point(alt, az, cx, cy, radius):
    r = radius*(90-alt)/90
    angle = math.radians(az)
    return QPointF(cx+r*math.sin(angle), cy-r*math.cos(angle))


def chart(p, moment, settings, w, h, phase):
    cx, cy, radius = w*.35, h*.43, min(w*.29, h*.33)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for fraction in (.33, .66, 1):
        p.setPen(QPen(QColor(130, 159, 210, 36 if fraction < 1 else 95), .8))
        p.drawEllipse(QPointF(cx, cy), radius*fraction, radius*fraction)
    p.setPen(QPen(QColor(130, 159, 210, 22), .7))
    p.drawLine(QPointF(cx-radius, cy), QPointF(cx+radius, cy))
    p.drawLine(QPointF(cx, cy-radius), QPointF(cx, cy+radius))
    if settings.guides:
        for angle, name in ((0, 'POHJOINEN'), (90, 'ITÄ'), (180, 'ETELÄ'), (270, 'LÄNSI')):
            pt = sky_point(0, angle, cx, cy, radius+25)
            label(p, QRectF(pt.x()-58, pt.y()-12, 116, 25), name, 10, '#899cbf')
    points = {}
    for hip, name, alt, az, mag in stars_at(int(moment.timestamp()), settings.latitude, settings.longitude):
        if alt <= 0:
            continue
        pt = sky_point(alt, az, cx, cy, radius)
        points[hip] = pt
        size = max(.65, 2.5-mag*.43)
        brightness = .87+.13*math.sin(phase*2+hip*.17)
        if mag < 2.1:
            glow(p, pt.x(), pt.y(), size*8, '#9cc2ff', int(100*brightness))
        p.setBrush(QColor(203, 221, 255, int(230*brightness))); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(pt, size, size)
    # Ursa Major, Cassiopeia, Ursa Minor, Orion and Crux. HIP identifiers.
    links = ((54061, 53910), (53910, 58001), (58001, 59774), (59774, 54061),
             (59774, 62956), (62956, 65378), (65378, 67301),
             (3179, 746), (746, 4427), (4427, 6686), (6686, 8886),
             (11767, 85822), (85822, 82080), (82080, 77055), (77055, 79822),
             (79822, 75097), (75097, 72607), (72607, 77055),
             (27989, 26727), (26727, 26311), (26311, 25930), (25930, 24436),
             (24436, 27366), (27366, 26727), (25930, 25336), (25336, 27989),
             (61084, 60718), (62434, 59747))
    p.setPen(QPen(QColor(112, 157, 217, 90), .8))
    for a, b in links:
        if a in points and b in points:
            p.drawLine(points[a], points[b])
    if 11767 in points or settings.latitude <= 0:
        pole = points.get(11767) or sky_point(abs(settings.latitude), 180, cx, cy, radius)
        glow(p, pole.x(), pole.y(), 23, '#d0c7ff', 150)
        p.setBrush(QColor('#f5edff')); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(pole, 2.5, 2.5)
        if settings.guides:
            label(p, QRectF(pole.x()+12, pole.y()-25, 250, 24),
                  'POHJANTÄHTI' if 11767 in points else 'ETELÄINEN TAIVAANNAPA', 11, '#d2d6fa')
        # Decorative orbiting light, distinct from the actual catalogue positions.
        for i in range(2):
            r = 45+i*24
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(138, 160, 224, 32), .8))
            p.drawEllipse(pole, r, r)
            orb = circle_point(pole.x(), pole.y(), r, phase*(-1 if i else 1)+i*2)
            glow(p, orb.x(), orb.y(), 13, '#a4a7ff', 110)
            p.setBrush(QColor('#c5dcff')); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(orb, 1.8, 1.8)
    return cx, cy, radius


def lunar_disc(p, x, y, radius, illumination, tilt):
    glow(p, x, y, radius*2.8, '#c6c7ff', int(25+illumination*60))
    p.save(); p.translate(x, y); p.rotate(tilt)
    p.setPen(QPen(QColor('#75819c'), .8)); p.setBrush(QColor('#10172a'))
    p.drawEllipse(QPointF(0, 0), radius, radius)
    # Right limb minus the projected terminator gives exactly the lit area.
    shape = QPainterPath(QPointF(0, -radius))
    for i in range(1, 81):
        yy = -radius+2*radius*i/80
        shape.lineTo(math.sqrt(max(0, radius*radius-yy*yy)), yy)
    for i in range(80, -1, -1):
        yy = -radius+2*radius*i/80
        shape.lineTo((1-2*illumination)*math.sqrt(max(0, radius*radius-yy*yy)), yy)
    shape.closeSubpath()
    p.setClipPath(shape)
    texture = QRadialGradient(QPointF(radius*.35, -radius*.35), radius*1.7)
    texture.setColorAt(0, QColor('#f7f3e8')); texture.setColorAt(.62, QColor('#b7bdca')); texture.setColorAt(1, QColor('#68738d'))
    p.setBrush(texture); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(0, 0), radius, radius)
    rng = random.Random(26)
    for _ in range(35):
        xx, yy = rng.uniform(-.85, .85)*radius, rng.uniform(-.85, .85)*radius
        rr = rng.uniform(.025, .14)*radius
        p.setPen(QPen(QColor(65, 76, 99, 60), max(.4, radius*.008)))
        p.setBrush(QColor(80, 90, 110, 28)); p.drawEllipse(QPointF(xx, yy), rr, rr*.85)
    p.restore()


def moon_scene(p, moment, settings, w, h, phase):
    cx, cy, radius = chart(p, moment, settings, w, h, phase)
    moon = moon_at(moment, settings.latitude, settings.longitude)
    zone = ZoneInfo(settings.timezone)
    samples, events = moon_day(moment.astimezone(zone).date(), settings.latitude, settings.longitude, settings.timezone)
    path = QPainterPath(); visible = False; trail = []
    for _, alt, az in samples:
        if alt < 0:
            visible = False; continue
        point = sky_point(alt, az, cx, cy, radius); trail.append(point)
        if visible: path.lineTo(point)
        else: path.moveTo(point)
        visible = True
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(204, 189, 244, 130), 1.6, Qt.PenStyle.DashLine))
    p.drawPath(path)
    if trail:
        point = trail[int((phase/(2*math.pi) % 1)*len(trail)) % len(trail)]
        glow(p, point.x(), point.y(), 28, '#b3a2ff', 170)
    if moon.altitude >= 0:
        pos = sky_point(moon.altitude, moon.azimuth, cx, cy, radius)
        lunar_disc(p, pos.x(), pos.y(), 15, moon.illumination, moon.tilt)
    x = w*.77; y = h*.31
    lunar_disc(p, x, y, min(94, h*.105), moon.illumination, moon.tilt)
    label(p, QRectF(w*.66, h*.45, w*.31, 30), f'Valaistuna {moon.illumination:.0%}', 21, '#e5dcff')
    name = ('Uusikuu' if moon.illumination < .015 else 'Täysikuu' if moon.illumination > .985
            else 'Kasvava kuu' if moon.waxing else 'Vähenevä kuu')
    label(p, QRectF(w*.66, h*.49, w*.31, 30), name, 13)
    label(p, QRectF(w*.66, h*.54, w*.31, 28),
          f'Korkeus {moon.altitude:.1f}° · suunta {moon.azimuth:.1f}°', 11, '#a6b1cc')
    if moon.altitude < 0:
        label(p, QRectF(w*.66, h*.58, w*.31, 26), 'Kuu on horisontin alapuolella', 11, '#c4addb')
    for i, (name, when) in enumerate(events):
        label(p, QRectF(w*.66, h*.63+i*27, w*.31, 25), f'{name} noin {when.astimezone(zone):%H:%M}', 12)
    if not events:
        label(p, QRectF(w*.66, h*.63, w*.31, 25), 'Ei nousua tai laskua tämän päivän aikana', 10)
    label(p, QRectF(w*.66, h*.72, w*.31, 25), settings.timezone, 10, '#7888aa')


def blood_scene(p, moment, settings, w, h, phase):
    ordinal, fraction, year_phase = blood_progress(moment)
    cx, cy = w*.36, h*.47
    radius = min(w*.28, h*.34)
    accent = QColor.fromHsvF((.94+.085*math.sin(year_phase*math.tau)) % 1, .65, .85)
    glow(p, cx, cy, radius*1.6, accent, 65)
    for i in range(7):
        r = radius*(.34+i*.105)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 65), .9))
        p.drawEllipse(QPointF(cx, cy), r, r)
        rotation = phase*(1 if i % 2 else -1)+i*.84+year_phase*math.tau
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 190), 1.8))
        p.drawArc(QRectF(cx-r, cy-r, 2*r, 2*r), int(math.degrees(rotation)*16), 42*16)
        for tick in range(37):
            a = tick/37*math.tau+i*.11
            p.setPen(QPen(QColor(173, 98, 132, 65), .7))
            p.drawLine(circle_point(cx, cy, r-3, a), circle_point(cx, cy, r+3, a))
        pt = circle_point(cx, cy, r, rotation)
        glow(p, pt.x(), pt.y(), 22, accent, 190)
        p.save(); p.translate(pt); p.rotate(math.degrees(rotation))
        p.setPen(QPen(QColor('#f0a6bc'), 1.1)); p.setBrush(QColor('#170916'))
        p.drawRect(QRectF(-5, -5, 10, 10)); p.drawLine(QPointF(-9, 0), QPointF(9, 0))
        p.restore()
    # 111 week ticks; the highlighted arc follows actual 777-day year progress.
    for i in range(111):
        angle = i/111*math.tau-math.pi/2
        color = accent if i/111 <= year_phase and ordinal >= 0 else QColor('#472239')
        p.setPen(QPen(color, 1.2))
        p.drawLine(circle_point(cx, cy, radius*1.04, angle), circle_point(cx, cy, radius*1.065, angle))
    inner = 35+3*math.sin(phase*2)
    glow(p, cx, cy, inner*3, accent, 150)
    path = QPainterPath()
    for i in range(15):
        a = -math.pi/2+(i % 14)*math.tau/14
        pt = circle_point(cx, cy, inner if i % 2 == 0 else inner*.49, a)
        if i: path.lineTo(pt)
        else: path.moveTo(pt)
    path.closeSubpath(); p.setBrush(QColor('#170b1a')); p.setPen(QPen(accent, 1.5)); p.drawPath(path)
    label(p, QRectF(w*.68, h*.30, w*.28, 40), 'SEITSEMÄN SINETTIÄ', 20, '#eba1b9')
    label(p, QRectF(w*.68, h*.36, w*.28, 25), '111 viikkoa · 777 päivää', 13, '#b6859b')
    label(p, QRectF(w*.68, h*.40, w*.28, 25), 'Kuvitteellinen taivaankoneisto', 11, '#8b6c84')
    if ordinal < 0:
        label(p, QRectF(w*.68, h*.45, w*.28, 25), 'Ennen Veri Ajan alkua', 11, '#b6859b')


def space_scene(p, w, h, phase):
    # Layered gas clouds drift, while the background's stars remain still.
    for i in range(9):
        x = w*(.18+i*.063)+55*math.sin(phase+i*.7)
        y = h*(.39+.12*math.sin(i)) + 24*math.cos(phase+i*.9)
        p.save(); p.translate(x, y); p.scale(2.5, .8)
        glow(p, 0, 0, 115, '#795acd' if i % 2 else '#3486a6', 27)
        p.restore()
    # A distant crescent world with a thin, luminous atmospheric rim.
    x, y, r = w*.29, h*.44, min(w*.16, h*.20)
    glow(p, x, y, r*1.9, '#5469c6', 45)
    gradient = QRadialGradient(QPointF(x-r*.55, y-r*.65), r*1.8)
    gradient.setColorAt(0, QColor('#4a668b')); gradient.setColorAt(.25, QColor('#192d48')); gradient.setColorAt(.62, QColor('#070c1c')); gradient.setColorAt(1, QColor('#03050e'))
    p.setBrush(gradient); p.setPen(QPen(QColor('#7a9abe'), 1)); p.drawEllipse(QPointF(x, y), r, r)
    rng = random.Random(777)
    for i in range(21):
        base_x, base_y = rng.uniform(.08, .84)*w, rng.uniform(.1, .84)*h
        xx = base_x+70*math.sin(phase+i*.57)
        yy = base_y+28*math.cos(phase+i*.71)
        size = rng.uniform(4, 19)
        p.save(); p.translate(xx, yy); p.rotate(9*math.sin(phase+i)+i*29)
        shard = QPainterPath(); shard.moveTo(-size, -size*.4)
        for a, b in ((-.2, -1), (1, -.3), (.6, .7), (-.5, .9)):
            shard.lineTo(size*a, size*b)
        shard.closeSubpath()
        shade = QLinearGradient(-size, -size, size, size)
        shade.setColorAt(0, QColor('#59758d')); shade.setColorAt(.48, QColor('#1b263a')); shade.setColorAt(1, QColor('#090e1a'))
        p.setBrush(shade); p.setPen(QPen(QColor('#62738d'), .6)); p.drawPath(shard)
        p.setPen(QPen(QColor(136, 161, 193, 80), .6))
        p.drawLine(QPointF(-size*.2, -size), QPointF(size*.2, size*.2))
        p.drawLine(QPointF(size*.2, size*.2), QPointF(size*.6, size*.7))
        p.restore()
    label(p, QRectF(w*.68, h*.29, w*.28, 40), 'HILJAINEN AVARUUS', 20, '#b8c6ef')
    label(p, QRectF(w*.68, h*.35, w*.28, 28), 'Kuvitteellinen näkymä', 11, '#8594b6')


def render_scene(moment, settings, width, height, animation_seconds=None):
    seconds = moment.timestamp() if animation_seconds is None else animation_seconds
    phase = (seconds % PERIOD)/PERIOD*math.tau
    landscape=settings.theme in ('stream','rose_garden','lighthouse')
    if landscape:
        from .landscapes import render_landscape
        image=render_landscape(moment,settings,width,height,phase)
    else:
        image = backdrop(settings.theme, min(width,1920), min(height,1080)).scaled(
            width,height,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = min(width/1920, height/1080)
    p.scale(scale, scale); w, h = width/scale, height/scale
    try:
        if landscape:
            pass  # The landscape has its own scenery and optional caption.
        elif settings.theme in ('polaris', 'moon'):
            if settings.theme == 'polaris':
                chart(p, moment, settings, w, h, phase)
                label(p, QRectF(w*.68, h*.28, w*.28, 40), 'POHJANTÄHDEN YÖ', 20, '#d5ddfa')
                label(p, QRectF(w*.68, h*.34, w*.28, 28), 'Tähtitaivas nykyhetkellä', 13)
                label(p, QRectF(w*.68, h*.39, w*.28, 28), f'{settings.latitude:.4f}°, {settings.longitude:.4f}°', 12, '#94a8ce')
                if settings.latitude <= 0:
                    label(p, QRectF(w*.68, h*.45, w*.28, 28), 'Pohjantähti jää täällä horisontin alle', 10, '#bba3cb')
            else:
                moon_scene(p, moment, settings, w, h, phase)
            if settings.guides:
                label(p, QRectF(w*.075, h*.82, w*.55, 28), 'TAIVASKARTTA · zeniitti keskellä · itä oikealla', 10, '#7f94b6')
        elif settings.theme == 'bloodwork':
            blood_scene(p, moment, settings, w, h, phase)
        else:
            space_scene(p, w, h, phase)
        if settings.theme != 'moon':
            title, lines = date_block(moment, settings.date_mode, ZoneInfo(settings.timezone))
            if lines:
                if landscape:
                    fade=QLinearGradient(w*.65,0,w*.99,0)
                    fade.setColorAt(0,QColor(3,7,15,0));fade.setColorAt(.25,QColor(3,7,15,150));fade.setColorAt(1,QColor(3,7,15,100))
                    p.fillRect(QRectF(w*.65,h*.57,w*.34,65+len(lines)*30),fade)
                label(p, QRectF(w*.68, h*.60, w*.29, 30), title, 13, '#b2a2ce')
                for i, line in enumerate(lines):
                    label(p, QRectF(w*.68, h*.65+i*30, w*.29, 28), line, 12)
        else:
            title, lines = date_block(moment, settings.date_mode, ZoneInfo(settings.timezone))
            if lines:
                label(p, QRectF(w*.075, h*.89, w*.56, 28), ' · '.join((title, *lines)), 10, '#b2b8d1')
    finally:
        p.end()
    return image


def render_entry(entry, seconds, width, height):
    if isinstance(entry, SceneEntry):
        # Match the GNOME quality cap; scale up for very large desktop surfaces.
        factor = min(1, 1920/width, 1080/height)
        return render_scene(datetime.fromtimestamp(seconds, timezone.utc), entry.settings,
                            max(320, round(width*factor)), max(240, round(height*factor)))
    return render_motion(entry, seconds, width, height)


def build_slideshow(moment, settings, width, height, directory, slot):
    """Two bounded slots, 16 native crossfades. Refresh astronomy at the interval.

    Decorative motion loops in 96 seconds; astronomical positions are held at
    this snapshot instead of being sped up or jumped at the end of each loop.
    """
    folder = Path(directory)/f'scene-{slot}'
    folder.mkdir(parents=True, exist_ok=True)
    factor = min(1, 1920/width, 1080/height)
    width, height = max(320, round(width*factor)), max(240, round(height*factor))
    paths = []
    for index in range(16):
        image = render_scene(moment, settings, width, height, index*PERIOD/16)
        path = folder/f'{index:02d}.jpg'; temporary = folder/f'.{index:02d}.jpg'
        if not image.save(str(temporary), 'JPEG', 94):
            raise RuntimeError('Teeman liikekuvan tallennus epäonnistui.')
        os.replace(temporary, path); paths.append(path)
    load_frame.cache_clear()
    entry = MotionEntry(settings.theme, SCENES[settings.theme][0], '', tuple(paths), PERIOD)
    return entry, write_gnome_slideshow(entry, Path(directory)/f'live-scene-{slot}.xml')
