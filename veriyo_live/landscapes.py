"""Original procedural scenery, civil-time lighting and calm 96-second motion."""
from dataclasses import dataclass
from functools import lru_cache
import math
import random
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPainterPath,
                        QPen, QRadialGradient)
from .scenes import glow, label

LANDSCAPES = ('stream', 'rose_garden', 'lighthouse')


@dataclass(frozen=True)
class Lighting:
    minute: int
    daylight: float
    top: str
    horizon: str
    water: str
    foliage: str
    name: str


def mix(a, b, amount):
    a, b = QColor(a), QColor(b)
    return QColor(*(round(x+(y-x)*amount) for x,y in zip(a.getRgb()[:3],b.getRgb()[:3]))).name()


@lru_cache(maxsize=1440)
def light_for_minute(minute):
    # Continuous colour ramps at civil clock times, not a solar ephemeris.
    knots = ((0, 0, '#040b1b', '#19263e'), (300, .03, '#171b39', '#6b495c'),
             (420, .62, '#466b7e', '#cfaa86'), (720, 1, '#275775', '#a5c7c4'),
             (1020, .62, '#443657', '#bb786a'), (1140, .12, '#161d3a', '#5e4860'),
             (1260, 0, '#040b1b', '#19263e'), (1440, 0, '#040b1b', '#19263e'))
    for a,b in zip(knots,knots[1:]):
        if a[0] <= minute <= b[0]:
            t=(minute-a[0])/(b[0]-a[0]); t=t*t*(3-2*t)
            day=a[1]+(b[1]-a[1])*t
            name='Aamu' if 300<=minute<600 else 'Päivä' if 600<=minute<1020 else 'Ilta' if 1020<=minute<1260 else 'Yö'
            return Lighting(minute,day,mix(a[2],b[2],t),mix(a[3],b[3],t),
                            mix('#081a2b','#477d86',day),mix('#040d13','#284b36',day),name)
    raise ValueError('Vuorokauden minuutti on virheellinen.')


def lighting_at(moment, zone_name):
    local=moment.astimezone(ZoneInfo(zone_name))
    return light_for_minute(local.hour*60+local.minute)


def polygon(points):
    path=QPainterPath(points[0])
    for point in points[1:]:path.lineTo(point)
    path.closeSubpath()
    return path


def pine(p,x,y,size,color):
    path=QPainterPath(QPointF(x,y-size))
    for i in range(1,6):
        path.lineTo(x+size*i*.065,y-size+i*size*.17)
        path.lineTo(x+size*(i-1)*.038,y-size+i*size*.17)
    path.lineTo(x+size*.4,y);path.lineTo(x-size*.4,y)
    for i in range(5,0,-1):
        path.lineTo(x-size*(i-1)*.038,y-size+i*size*.17)
        path.lineTo(x-size*i*.065,y-size+i*size*.17)
    path.closeSubpath();p.setBrush(QColor(color));p.setPen(Qt.PenStyle.NoPen);p.drawPath(path)


def rock(p,x,y,rx,ry,day,seed):
    rng=random.Random(seed)
    points=[]
    for i in range(10):
        angle=i/10*math.tau;scale=rng.uniform(.85,1.1)
        points.append(QPointF(x+math.cos(angle)*rx*scale,y+math.sin(angle)*ry*scale))
    shape=polygon(points)
    gradient=QLinearGradient(x-rx,y-ry,x+rx,y+ry)
    gradient.setColorAt(0,QColor(mix('#2c3a45','#8a9585',day)))
    gradient.setColorAt(.43,QColor(mix('#15232b','#4c6256',day)))
    gradient.setColorAt(1,QColor('#050e16'))
    p.setPen(QPen(QColor(mix('#304550','#809683',day)),.8));p.setBrush(gradient);p.drawPath(shape)
    p.save();p.setClipPath(shape)
    for i in range(9):
        xx=x+rng.uniform(-rx,rx);yy=y+rng.uniform(-ry,ry)
        p.setPen(QPen(QColor(174,189,167,15+int(day*25)),rng.uniform(.4,1.2)))
        p.drawLine(QPointF(xx,yy),QPointF(xx+rx*.5,yy-ry*.3))
    p.restore()


def river_point(t,w,h):
    return QPointF(w*(.50+.09*math.sin(t*5.2+.5)),h*(.59+.47*t))


def river_width(t,w):
    return w*(.004+.19*t**1.6)


@lru_cache(maxsize=16)
def river_shape(w,h):
    points=[]
    for i in range(81):
        t=i/80;pt=river_point(t,w,h);points.append(QPointF(pt.x()-river_width(t,w),pt.y()))
    for i in range(80,-1,-1):
        t=i/80;pt=river_point(t,w,h);points.append(QPointF(pt.x()+river_width(t,w),pt.y()))
    return polygon(points)


def sky(p,w,h,light,seed):
    gradient=QLinearGradient(0,0,0,h*.7)
    gradient.setColorAt(0,QColor(light.top));gradient.setColorAt(1,QColor(light.horizon))
    p.fillRect(QRectF(0,0,w,h),gradient)
    rng=random.Random(seed)
    alpha=round(150*(1-light.daylight)**2)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(150):
        p.setBrush(QColor(203,217,240,alpha));pt=QPointF(rng.uniform(0,w),rng.uniform(0,h*.61))
        r=rng.uniform(.45,1.2);p.drawEllipse(pt,r,r)
    for layer in range(3):
        path=QPainterPath(QPointF(-20,h))
        for x in range(-20,round(w)+40,18):
            y=h*(.47+layer*.045)+math.sin(x/140+layer*2)*h*.035+math.sin(x/61+layer)*h*.018
            path.lineTo(x,y)
        path.lineTo(w+20,h);path.closeSubpath()
        p.setBrush(QColor(mix('#111e32','#566f72',light.daylight*(.38-layer*.1))))
        p.setPen(Qt.PenStyle.NoPen);p.drawPath(path)


def stream_base(p,w,h,light):
    sky(p,w,h,light,26)
    rng=random.Random(2677)
    # Distant forest and mossy banks frame the winding channel.
    for layer in range(2):
        for i in range(95):
            x=w*i/94+rng.uniform(-10,10);y=h*(.52+layer*.08)+math.sin(x/150)*h*.025
            pine(p,x,y,rng.uniform(45,115)*(1+layer*.5),mix('#07131b',light.foliage,.5+layer*.3))
    ground=QLinearGradient(0,h*.57,0,h)
    ground.setColorAt(0,QColor(light.foliage));ground.setColorAt(1,QColor(mix('#050c10','#15281d',light.daylight)))
    p.fillRect(QRectF(0,h*.59,w,h*.41),ground)
    water=QLinearGradient(0,h*.43,0,h)
    water.setColorAt(0,QColor(light.horizon));water.setColorAt(.27,QColor(light.water));water.setColorAt(1,QColor(mix('#07141e','#244d59',light.daylight)))
    p.setBrush(water);p.setPen(Qt.PenStyle.NoPen);p.drawPath(river_shape(w,h))
    for i in range(48):
        t=rng.uniform(.01,1);pt=river_point(t,w,h);half=river_width(t,w)
        sign=-1 if i%2 else 1;x=pt.x()+sign*(half+w*rng.uniform(.003,.018))
        factor=rng.uniform(.5,1.25)
        rock(p,x,pt.y(),w*(.007+.036*t)*factor,h*(.006+.020*t)*factor,light.daylight,i)
    # Fallen trunk across the far bank.
    p.setPen(QPen(QColor(mix('#11181a','#514631',light.daylight)),12))
    p.drawLine(QPointF(w*.40,h*.61),QPointF(w*.59,h*.56))
    for x,y,size in ((w*.06,h*.90,h*.66),(w*.94,h*.89,h*.75)):
        pine(p,x,y,size,mix('#02090d','#10271d',light.daylight))
    for i in range(150):
        t=rng.random();pt=river_point(t,w,h);side=-1 if i%2 else 1
        x=pt.x()+side*(river_width(t,w)+rng.uniform(15,90))
        y=pt.y()+rng.uniform(-10,15);length=rng.uniform(7,26)*(t+.3)
        p.setPen(QPen(QColor(mix('#102a25','#57724a',light.daylight)),1))
        p.drawLine(QPointF(x,y),QPointF(x+rng.uniform(-12,12),y-length))


def greenhouse(p,w,h,light):
    sky(p,w,h,light,777)
    # Two fictional moons above an alien valley, visible through the glazing.
    for x,y,r in ((w*.28,h*.20,h*.072),(w*.50,h*.13,h*.038)):
        glow(p,x,y,r*2.3,'#c4a2d8',round(55*(1-light.daylight)))
        p.setBrush(QColor(mix('#b8a6cb','#7d8aa0',light.daylight)));p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x,y),r,r)
        p.setBrush(QColor(light.top));p.drawEllipse(QPointF(x+r*.35,y-r*.12),r*.90,r*.90)
    floor=QLinearGradient(0,h*.58,0,h)
    floor.setColorAt(0,QColor('#10101e'));floor.setColorAt(1,QColor(mix('#130d1b','#3d2e3a',light.daylight)))
    p.fillRect(QRectF(0,h*.58,w,h*.42),floor)
    for i in range(12):
        p.setPen(QPen(QColor(151,125,154,27),1))
        p.drawLine(QPointF(w*.5,h*.53),QPointF(w*(i/11*1.4-.2),h))
    for i in range(12):
        yy=h*(.58+.42*(i/11)**1.7)
        p.drawLine(QPointF(0,yy),QPointF(w,yy))
    # Pointed ribs and glass panels make a cathedral-like greenhouse.
    metal=mix('#293245','#67747b',light.daylight)
    for side in (-1,1):
        for i in range(4):
            x=w*(.5+side*(.15+i*.095))
            arch=QPainterPath(QPointF(x,h))
            arch.lineTo(x,h*.42)
            arch.cubicTo(x,h*.20,w*.5,h*.02,w*.5,-h*.03)
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(metal),3.5 if i==3 else 2))
            p.drawPath(arch)
    for i in range(4):
        yy=h*(.16+i*.12)
        p.setPen(QPen(QColor(metal),1.3));p.drawLine(QPointF(0,yy),QPointF(w,yy))
    p.setPen(QPen(QColor('#121622'),14));p.drawLine(QPointF(0,h*.59),QPointF(w,h*.59))
    # The remote door, seen through drifting mist.
    door=QPainterPath(QPointF(w*.47,h*.60));door.lineTo(w*.47,h*.45)
    door.quadTo(w*.5,h*.36,w*.53,h*.45);door.lineTo(w*.53,h*.60);door.closeSubpath()
    p.setBrush(QColor('#0b101c'));p.setPen(QPen(QColor(metal),2));p.drawPath(door)
    rng=random.Random(666)
    for i in range(24):
        x=rng.uniform(.04,.80)*w;y=rng.uniform(.70,.97)*h
        rock(p,x,y,w*.028,h*.018,light.daylight,i+700)


def island_shape(w,h):
    return polygon([QPointF(w*x,h*y) for x,y in ((.05,.91),(.13,.80),(.19,.77),(.23,.71),(.31,.70),(.38,.77),(.47,.88),(.48,1.02),(.02,1.02))])


def lighthouse_base(p,w,h,light):
    sky(p,w,h,light,107)
    # A ringed planet: deliberately fictional, not a chart of Earth's sky.
    x,y,r=w*.70,h*.29,h*.14
    glow(p,x,y,r*1.65,'#b3a2d4',45)
    p.save();p.translate(x,y);p.rotate(-22)
    p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(163,155,191,80),r*.11))
    p.drawEllipse(QPointF(0,0),r*1.8,r*.42)
    sphere=QRadialGradient(QPointF(-r*.4,-r*.5),r*1.8)
    sphere.setColorAt(0,QColor('#9a94a9'));sphere.setColorAt(.45,QColor('#494966'));sphere.setColorAt(1,QColor('#10172d'))
    p.setBrush(sphere);p.setPen(QPen(QColor('#a0a3bc'),.8));p.drawEllipse(QPointF(0,0),r,r)
    p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(211,193,204,90),r*.065))
    p.drawArc(QRectF(-r*1.8,-r*.42,r*3.6,r*.84),180*16,180*16);p.restore()
    sea=QLinearGradient(0,h*.61,0,h)
    sea.setColorAt(0,QColor(mix('#192940','#647d89',light.daylight)))
    sea.setColorAt(.4,QColor(mix('#0a172b','#355562',light.daylight)));sea.setColorAt(1,QColor('#030a16'))
    p.fillRect(QRectF(0,h*.61,w,h*.39),sea)
    island=island_shape(w,h)
    stone=QLinearGradient(w*.18,h*.7,w*.38,h)
    stone.setColorAt(0,QColor(mix('#384049','#777f7c',light.daylight)))
    stone.setColorAt(.4,QColor('#14202c'));stone.setColorAt(1,QColor('#030812'))
    p.setBrush(stone);p.setPen(QPen(QColor('#354451'),1));p.drawPath(island)
    # Tapering tower, corroded panels, lantern and antenna.
    tower=polygon([QPointF(w*.248,h*.74),QPointF(w*.267,h*.33),QPointF(w*.307,h*.33),QPointF(w*.332,h*.77)])
    gradient=QLinearGradient(w*.25,0,w*.33,0)
    gradient.setColorAt(0,QColor('#142333'));gradient.setColorAt(.38,QColor(mix('#5d6065','#a4a399',light.daylight)))
    gradient.setColorAt(.68,QColor('#333e4b'));gradient.setColorAt(1,QColor('#0a1625'))
    p.setBrush(gradient);p.setPen(QPen(QColor('#7c858a'),1.1));p.drawPath(tower)
    for i in range(8):
        yy=h*(.38+i*.043)
        p.setPen(QPen(QColor('#182633'),2));p.drawLine(QPointF(w*.262,yy),QPointF(w*.315,yy))
        p.setBrush(QColor('#080f1b'));p.setPen(QPen(QColor('#6a6d77'),.8))
        p.drawRoundedRect(QRectF(w*.282,yy+h*.009,w*.008,h*.021),2,2)
    p.setBrush(QColor('#0d1725'));p.setPen(QPen(QColor('#a0a0a0'),1))
    p.drawRect(QRectF(w*.252,h*.33,w*.075,h*.016))
    p.setBrush(QColor(171,202,193,58));p.drawRect(QRectF(w*.265,h*.271,w*.049,h*.056))
    for xx in (.265,.289,.314):
        p.setPen(QPen(QColor('#101c2c'),3));p.drawLine(QPointF(w*xx,h*.267),QPointF(w*xx,h*.328))
    roof=polygon([QPointF(w*.25,h*.273),QPointF(w*.29,h*.244),QPointF(w*.331,h*.273)])
    p.setBrush(QColor('#233044'));p.setPen(QPen(QColor('#6e7783'),1));p.drawPath(roof)
    p.drawLine(QPointF(w*.29,h*.245),QPointF(w*.29,h*.206))
    glow(p,w*.289,h*.298,h*.043,'#e3ceb3',130)


@lru_cache(maxsize=6)
def background(theme,width,height,minute):
    light=light_for_minute(minute)
    image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(QColor('#050b15'))
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale=min(width/1920,height/1080);p.scale(scale,scale)
    try:
        {'stream':stream_base,'rose_garden':greenhouse,'lighthouse':lighthouse_base}[theme](p,width/scale,height/scale,light)
    finally:p.end()
    return image


def flowing_stream(p,w,h,light,phase):
    p.save();p.setClipPath(river_shape(w,h))
    for i in range(100):
        t=(i/100+phase/math.tau)%1;pt=river_point(t,w,h);half=river_width(t,w)
        offset=math.sin(i*6.71)*half*.8
        xx=pt.x()+offset;length=half*(.08+(i%5)*.025)
        alpha=round((30+70*light.daylight)*math.sin(t*math.pi)**.5)
        p.setPen(QPen(QColor(181,220,222,alpha),.7+t*.9));p.setBrush(Qt.BrushStyle.NoBrush)
        wave=QPainterPath(QPointF(xx-length,pt.y()))
        wave.quadTo(xx,pt.y()+3+t*5,xx+length,pt.y())
        p.drawPath(wave)
    p.restore()
    # Slowly waving bankside fronds and fireflies at night.
    for i in range(12):
        t=.45+i*.045;pt=river_point(t,w,h);sign=-1 if i%2 else 1
        x=pt.x()+sign*(river_width(t,w)+25);y=pt.y()+10
        length=25+t*40;sway=8*math.sin(phase+i*.8)
        stem=QPainterPath(QPointF(x,y));stem.quadTo(x+sway,y-length*.6,x+sign*18+sway,y-length)
        p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(mix('#17342d','#5c8157',light.daylight)),1.4));p.drawPath(stem)
        for j in range(1,6):
            anchor=stem.pointAtPercent(j/7)
            p.drawLine(anchor,QPointF(anchor.x()+sign*(16-j*1.5),anchor.y()-9))
            p.drawLine(anchor,QPointF(anchor.x()-sign*(12-j),anchor.y()-8))
    for i in range(16):
        x=w*(.21+i*.037)+14*math.sin(phase+i);y=h*.60+50*math.cos(phase+i*1.9)
        glow(p,x,y,9,'#b7d99b',round((1-light.daylight)*90*(.6+.4*math.sin(phase+i)**2)))


def rose(p,x,y,size,opening,light,rotation):
    p.save();p.translate(x,y);p.rotate(rotation)
    glow(p,0,0,size*2.1,'#b43b72',25+round((1-light.daylight)*25))
    for layer in range(4):
        radius=size*(1-layer*.19)*opening
        for i in range(5):
            angle=i/5*math.tau+layer*.63
            p.save();p.rotate(math.degrees(angle))
            petal=QPainterPath(QPointF(0,radius*.16))
            petal.cubicTo(-radius*.9,-radius*.10,-radius*.9,-radius*.92,0,-radius)
            petal.cubicTo(radius*.75,-radius*.85,radius*.72,-radius*.12,0,radius*.16)
            gradient=QLinearGradient(0,-radius,0,radius*.1)
            gradient.setColorAt(0,QColor(mix('#a64c72','#ce7693',light.daylight)))
            gradient.setColorAt(.35,QColor('#641e45'));gradient.setColorAt(1,QColor('#160c21'))
            p.setBrush(gradient);p.setPen(QPen(QColor(192,107,147,95),.6));p.drawPath(petal);p.restore()
    p.restore()


def rose_motion(p,w,h,light,phase):
    rng=random.Random(666)
    for i in range(24):
        x=rng.uniform(.04,.80)*w;y=rng.uniform(.70,.97)*h
        length=rng.uniform(.07,.21)*h;sway=9*math.sin(phase+i*.7)
        stem=QPainterPath(QPointF(x,y));stem.cubicTo(x-15,y-length*.35,x+18+sway,y-length*.7,x+sway,y-length)
        p.setPen(QPen(QColor('#273d36'),2.1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(stem)
        p.setPen(QPen(QColor(126,45,102,70),.9));p.drawPath(stem)
        for j in (.25,.50):
            pt=stem.pointAtPercent(j);leaf=QPainterPath(pt)
            leaf.quadTo(pt.x()-32,pt.y()-35,pt.x()-35,pt.y()-9)
            leaf.quadTo(pt.x()-16,pt.y()+5,pt.x(),pt.y())
            p.setBrush(QColor('#162a2b'));p.setPen(QPen(QColor('#425148'),.7));p.drawPath(leaf)
        travel=(phase/math.tau+i*.137)%1
        bead=stem.pointAtPercent(travel)
        glow(p,bead.x(),bead.y(),7,'#df559b',round(110*math.sin(math.pi*travel)**2))
        rose(p,x+sway,y-length,rng.uniform(15,33),.78+.22*math.sin(phase+i*.6)**2,light,6*math.sin(phase+i))
    # Petals drift and fade before wrapping, making the loop continuous.
    rng=random.Random(6107)
    for i in range(25):
        t=(phase/math.tau+i/25)%1
        x=w*rng.uniform(.1,.86)+55*math.sin(phase+i);y=h*(.28+.68*t)
        alpha=round(150*math.sin(math.pi*t)**2)
        p.save();p.translate(x,y);p.rotate(i*61+30*math.sin(phase+i))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(164,61,107,alpha))
        path=QPainterPath(QPointF(-5,0));path.cubicTo(-3,-8,6,-7,7,0);path.quadTo(2,7,-5,0)
        p.drawPath(path);p.restore()
    # A distant silhouette, only hinted at behind the fog, without a sudden reveal.
    alpha=round(20*(1-light.daylight)*((1+math.sin(phase-1))/2)**3)
    x=w*.50+4*math.sin(phase);y=h*.55
    p.setBrush(QColor(105,112,135,alpha));p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(x,y-h*.05),h*.009,h*.014)
    ghost=polygon([QPointF(x-h*.008,y-h*.04),QPointF(x+h*.008,y-h*.04),QPointF(x+h*.025,y+h*.03),QPointF(x-h*.022,y+h*.03)])
    p.drawPath(ghost)


def sea_motion(p,w,h,light,phase):
    p.save();sea=QPainterPath();sea.addRect(QRectF(0,h*.61,w,h*.39))
    p.setClipPath(sea.subtracted(island_shape(w,h)))
    for i in range(65):
        t=(i/65+phase/math.tau)%1
        y=h*(.61+.4*t*t);x=w*((i*.6180339)%1)+20*math.sin(phase+i)
        length=w*(.006+.07*t)
        alpha=round((18+35*light.daylight)*math.sin(t*math.pi)**.4)
        p.setPen(QPen(QColor(171,194,209,alpha),.7+t))
        line=QPainterPath(QPointF(x-length,y));line.quadTo(x,y+2+4*t,x+length,y)
        p.drawPath(line)
    # A very large presence glides behind the sea mist on the horizon.
    alpha=round((18+24*(1-light.daylight))*((1+math.sin(phase-.8))/2)**2)
    xx=w*.76+35*math.sin(phase);yy=h*.626+5*math.cos(phase)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(5,11,24,alpha))
    p.drawEllipse(QPointF(xx,yy),w*.115,h*.027)
    for offset in (-.07,.025):
        p.drawPath(polygon([QPointF(xx+w*offset,yy),QPointF(xx+w*(offset+.014),yy-h*.065),QPointF(xx+w*(offset+.035),yy)]))
    p.restore()
    # A rotating projected beam; its brightness changes smoothly rather than flashing.
    cx,cy=w*.289,h*.298
    direction=math.cos(phase)
    farx=cx+direction*w*.90;fary=cy+math.sin(phase)*h*.11
    spread=h*(.035+.045*abs(direction))
    beam=polygon([QPointF(cx,cy),QPointF(farx,fary-spread),QPointF(farx,fary+spread)])
    gradient=QLinearGradient(cx,cy,farx,fary)
    alpha=round((45+65*(1-light.daylight))*(.5+.5*abs(direction)))
    gradient.setColorAt(0,QColor(231,222,190,alpha));gradient.setColorAt(1,QColor(177,203,210,0))
    p.setBrush(gradient);p.setPen(Qt.PenStyle.NoPen);p.drawPath(beam)
    glow(p,cx,cy,h*.024,'#f2dfb5',180)


def render_landscape(moment,settings,width,height,phase):
    light=lighting_at(moment,settings.timezone)
    image=background(settings.theme,min(1920,width),min(1080,height),light.minute).scaled(
        width,height,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale=min(width/1920,height/1080);p.scale(scale,scale);w,h=width/scale,height/scale
    try:
        {'stream':flowing_stream,'rose_garden':rose_motion,'lighthouse':sea_motion}[settings.theme](p,w,h,light,phase)
        # Common mist drifts gently across all three landscapes.
        for i in range(5):
            p.save();p.translate(w*(.13+i*.19)+28*math.sin(phase+i),h*(.56+i%2*.035))
            p.scale(3.6,.22);glow(p,0,0,95,'#b7bfca',round((8+10*(1-light.daylight))*(.7+.3*math.sin(phase+i)**2)));p.restore()
        if settings.guides:
            titles={'stream':'METSIEN PURO','rose_garden':'VARJORUUSUJEN PUUTARHA','lighthouse':'VIIMEINEN MAJAKKA'}
            label(p,QRectF(w*.65,h*.09,w*.33,36),titles[settings.theme],17,'#d3d9e4')
            label(p,QRectF(w*.65,h*.14,w*.33,25),light.name+' · '+settings.timezone,11,'#a6b2c8')
    finally:p.end()
    return image
