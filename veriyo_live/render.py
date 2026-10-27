"""Stateless offscreen rendering: landscape remains fixed, sky follows UTC."""
import math
from pathlib import Path
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QRadialGradient
from .calendar import date_block
from .sky import LINKS, sky_at

ASSETS = Path(__file__).resolve().parent / 'assets'


def project(altitude, azimuth):
    """Stereographic view facing true north: east right, zenith up.

    North horizon=(0,0), zenith=(0,-2), east=(2,0), west=(-2,0).
    NCP altitude is exactly the observer's latitude, not a decorative tilt.
    """
    alt, az = math.radians(altitude), math.radians(azimuth)
    east, north, up = math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)
    denominator = 1 + north
    if denominator <= 1e-8:
        raise ValueError('Suunta on projektion takana.')
    return 2 * east / denominator, -2 * up / denominator


def sky_points(moment, settings, width, height):
    stars = sky_at(moment, settings.latitude, settings.longitude)
    # Identical scale for x and y, independent of monitor aspect ratio.
    scale = min(width * .14, height * .235)
    origin = QPointF(width * .32, height * .70)
    points = []
    for star in stars:
        x, y = project(star.altitude, star.azimuth)
        points.append(QPointF(origin.x() + x * scale, origin.y() + y * scale))
    return stars, points, origin, scale


def text(painter, rect, content, size, color='#f0788b', align=Qt.AlignmentFlag.AlignLeft):
    painter.setFont(QFont('Segoe UI' if __import__('os').name == 'nt' else 'DejaVu Sans', max(7, round(size))))
    painter.setPen(QColor(color))
    painter.drawText(rect, align | Qt.AlignmentFlag.AlignVCenter, content)


def render(moment, settings, width=1920, height=1080, background=None):
    settings.validate()
    if type(width) is not int or type(height) is not int or not 320 <= width <= 7680 or not 240 <= height <= 4320:
        raise ValueError('Kuvan tarkkuus ei ole tuettu (320×240…7680×4320).')
    source = background if background is not None else QImage(str(ASSETS / (settings.theme + '.png')))
    if source.isNull():
        raise ValueError('Taustakuvan pohjaa ei löydy tai kuva on vioittunut.')
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor('#070508'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    # Cover the screen without distorting the landscape or the sky geometry.
    ratio = max(width / source.width(), height / source.height())
    sw, sh = source.width() * ratio, source.height() * ratio
    painter.drawImage(QRectF((width-sw)/2, (height-sh)/2, sw, sh), source)
    stars, points, origin, scale = sky_points(moment, settings, width, height)
    font_scale = min(width / 1920, height / 1080)
    pole_x, pole_y = project(settings.latitude, 0)
    pole = QPointF(origin.x() + pole_x * scale, origin.y() + pole_y * scale)
    if settings.guides:
        painter.setPen(QPen(QColor(240, 120, 139, 45), max(.6, font_scale)))
        painter.drawLine(QPointF(origin.x()-2*scale, origin.y()), QPointF(origin.x()+2*scale, origin.y()))
        painter.drawLine(QPointF(pole.x()-7*font_scale, pole.y()), QPointF(pole.x()+7*font_scale, pole.y()))
        painter.drawLine(QPointF(pole.x(), pole.y()-7*font_scale), QPointF(pole.x(), pole.y()+7*font_scale))
        for x, label, align in ((origin.x()-2*scale, 'LÄNSI', Qt.AlignmentFlag.AlignLeft),
                                (origin.x()-60*font_scale, 'POHJOINEN', Qt.AlignmentFlag.AlignHCenter),
                                (origin.x()+2*scale-130*font_scale, 'ITÄ', Qt.AlignmentFlag.AlignRight)):
            text(painter, QRectF(x, origin.y()+8*font_scale, 130*font_scale, 28*font_scale), label, 10*font_scale, '#b88490', align)
        text(painter, QRectF(pole.x()+13*font_scale, pole.y()-28*font_scale, 280*font_scale, 24*font_scale),
             f'Taivaannapa · {settings.latitude:.2f}°', 9*font_scale, '#b88490')
        text(painter, QRectF(origin.x()-90*font_scale, origin.y()-2*scale-30*font_scale, 180*font_scale, 26*font_scale),
             'ZENIITTI ↑', 9*font_scale, '#b88490', Qt.AlignmentFlag.AlignHCenter)
    # Fine luminous links, with a broader dim halo.
    for thickness, alpha in ((4.5, 22), (1, 170)):
        painter.setPen(QPen(QColor(240, 120, 139, alpha), max(.5, thickness*font_scale)))
        for a, b in LINKS:
            painter.drawLine(points[a], points[b])
    for star, point in zip(stars, points):
        radius = (2.6 + (3.4-star.magnitude)*.6) * max(.65, font_scale)
        glow = QRadialGradient(point, radius*7)
        glow.setColorAt(0, QColor(255, 168, 181, 180))
        glow.setColorAt(.24, QColor(240, 120, 139, 65))
        glow.setColorAt(1, QColor(240, 120, 139, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(point, radius*7, radius*7)
        painter.setBrush(QColor('#fff1ed'))
        painter.drawEllipse(point, radius, radius)
    tail, tail_point = stars[-1], points[-1]
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('#f0788b'), max(.8, font_scale)))
    painter.drawEllipse(tail_point, 8*max(.65, font_scale), 8*max(.65, font_scale))
    if settings.guides:
        text(painter, QRectF(tail_point.x()+12*font_scale, tail_point.y()-15*font_scale, 160*font_scale, 30*font_scale),
             'Alkaid', 11*font_scale, '#f5d5d9')
    # Dark right-hand space keeps text away from the moving constellation and desktop icons.
    left, top, box_w = width*.67, height*.69, width*.29
    title, lines = date_block(moment, settings.date_mode)
    if lines:
        text(painter, QRectF(left, top, box_w, height*.045), title, 16*font_scale)
        for index, line in enumerate(lines):
            text(painter, QRectF(left, top+(50+index*33)*font_scale, box_w, 30*font_scale), line, 12*font_scale, '#efd9df')
    footer = f'{settings.latitude:.6f}, {settings.longitude:.6f}'
    text(painter, QRectF(width*.04, height*.95, width*.92, height*.035), footer, 10*font_scale, '#bd959e')
    painter.end()
    return image
