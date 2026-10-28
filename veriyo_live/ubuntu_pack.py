"""Data-only Ubuntu animation pack, safe installation and native GNOME slideshow XML."""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QImage, QImageReader, QPainter

PACK_VERSION='1.0.0'
PACK_NAME='Ubuntu-Live-Pack-1.0.0.zip'
STATIC_DURATION=.04


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent/'assets/ubuntu_catalog.json').read_text(encoding='utf-8'))['releases']


def versions():
    return tuple(record['version'] for record in catalog())


@dataclass(frozen=True)
class MotionEntry:
    version: str
    name: str
    motion_label: str
    frames: tuple
    period: float


def validate_manifest(value):
    if not isinstance(value,dict) or value.get('format')!='veriyo-ubuntu-live' or value.get('version')!=PACK_VERSION:
        raise ValueError('Valitse Ubuntu Live Pack 1.0.0 -paketti.')
    rows=value.get('releases')
    known={entry['version']:entry for entry in catalog()}
    if not isinstance(rows,list) or len(rows)!=len(known):
        raise ValueError('Live-paketista puuttuu Ubuntu-versioita.')
    seen=set();files=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('version') not in known or row['version'] in seen:
            raise ValueError('Live-paketin versioluettelo on virheellinen.')
        seen.add(row['version']);original=known[row['version']]
        if row.get('source_sha256')!=original['sha256'] or row.get('id')!=original['id'] or row.get('name')!=original['name']:
            raise ValueError('Live-paketin alkuperäistiedot eivät täsmää.')
        period=row.get('period')
        if isinstance(period,bool) or not isinstance(period,(int,float)) or not math.isfinite(period) or not 24<=period<=120:
            raise ValueError('Live-paketin liike on liian nopea tai virheellinen.')
        if row.get('size')!=[1920,1080] or not isinstance(row.get('frames'),list) or len(row['frames'])!=16:
            raise ValueError('Live-paketin kuvakoko tai kuvaluettelo on virheellinen.')
        for number,frame in enumerate(row['frames']):
            expected=f'{original["id"]}/{number:02d}.jpg'
            if not isinstance(frame,dict) or frame.get('file')!=expected or not re.fullmatch('[0-9a-f]{64}',str(frame.get('sha256',''))):
                raise ValueError('Live-paketin kuvatiedot eivät täsmää.')
            if expected in files:raise ValueError('Live-paketissa on päällekkäisiä kuvia.')
            files.add(expected)
    return files


class PackLibrary:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.root=self.directory/'packs'/f'ubuntu-live-{PACK_VERSION}'

    def installed(self):
        return (self.root/'pack.json').is_file()

    @lru_cache(maxsize=8)
    def entry(self,version):
        if not self.installed():
            raise ValueError('Asenna ensin Ubuntu live -paketti: '+PACK_NAME)
        value=json.loads((self.root/'pack.json').read_text(encoding='utf-8'))
        validate_manifest(value)
        row=next((item for item in value['releases'] if item['version']==version),None)
        if row is None:raise ValueError('Ubuntu-versiota ei löydy live-paketista.')
        frames=tuple(self.root/item['file'] for item in row['frames'])
        if not all(path.is_file() and path.resolve().is_relative_to(self.root.resolve()) for path in frames):
            raise ValueError('Live-paketin kuvia puuttuu. Asenna paketti uudelleen.')
        return MotionEntry(row['version'],row['name'],row['motion_label'],frames,float(row['period']))

    def install(self,archive):
        archive=Path(archive)
        if not archive.is_file() or archive.stat().st_size>800*1024*1024:
            raise ValueError('Live-pakettia ei löydy tai se on liian suuri.')
        self.root.parent.mkdir(parents=True,exist_ok=True)
        temporary=Path(tempfile.mkdtemp(prefix='.ubuntu-live-',dir=self.root.parent))
        try:
            with ZipFile(archive) as stream:
                members=stream.infolist()
                if len(members)>900 or sum(item.file_size for item in members)>1024*1024*1024:
                    raise ValueError('Live-paketin sisältö on liian suuri.')
                seen=set()
                for item in members:
                    path=PurePosixPath(item.filename)
                    if (not item.filename or path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename
                            or item.filename.casefold() in seen or stat.S_ISLNK(item.external_attr>>16)):
                        raise ValueError('Live-paketissa on turvaton tiedostopolku.')
                    seen.add(item.filename.casefold())
                    if item.file_size>8*1024*1024:raise ValueError('Live-paketin yksittäinen tiedosto on liian suuri.')
                if 'pack.json' not in stream.namelist() or stream.getinfo('pack.json').file_size>2*1024*1024:
                    raise ValueError('Live-paketin luettelo puuttuu.')
                manifest=stream.read('pack.json');value=json.loads(manifest)
                expected=validate_manifest(value)
                optional={name for name in stream.namelist() if name=='README.md' or
                          (len(PurePosixPath(name).parts)==2 and name.startswith('LICENSES/') and name.endswith(('.txt','.md')))}
                if set(stream.namelist()) != expected|optional|{'pack.json'}:
                    raise ValueError('Live-paketti sisältää tuntemattomia tiedostoja.')
                checks={frame['file']:frame['sha256'] for row in value['releases'] for frame in row['frames']}
                for item in members:
                    content=stream.read(item)
                    if item.filename in checks and sha256(content).hexdigest()!=checks[item.filename]:
                        raise ValueError('Live-paketin kuvan tarkiste on väärä: '+item.filename)
                    target=temporary/item.filename
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(content)
                    if item.filename in checks:
                        reader=QImageReader(str(target))
                        try:
                            if reader.size()!=QSize(1920,1080) or reader.read().isNull():
                                raise ValueError('Live-paketissa on vioittunut kuva.')
                        finally:
                            # QImageReader owns a QFile until destruction. Windows cannot
                            # atomically rename the staging directory while that file is open.
                            del reader
            if self.root.exists():
                if (self.root/'pack.json').read_bytes()==manifest:
                    # Repair an interrupted/corrupted installation only while the app is stopped.
                    old=self.root.with_name(self.root.name+'.previous')
                    if old.exists():shutil.rmtree(old)
                    os.replace(self.root,old)
                    try:os.replace(temporary,self.root)
                    except Exception:
                        os.replace(old,self.root);raise
                    shutil.rmtree(old)
                else:raise ValueError('Samanniminen live-paketti eri sisällöllä on jo asennettu.')
            else:os.replace(temporary,self.root)
            load_frame.cache_clear()
            self.entry.cache_clear()
            return self.root
        finally:
            if temporary.exists():shutil.rmtree(temporary)


def frame_pair(seconds,count=16,period=48):
    if not math.isfinite(seconds):raise ValueError('Virheellinen animaation aika.')
    position=(seconds%period)/period*count
    index=int(position)%count
    duration=period/count
    blend=max(0,min(1,((position-index)*duration-STATIC_DURATION)/(duration-STATIC_DURATION)))
    return index,(index+1)%count,blend


@lru_cache(maxsize=8)
def load_frame(path,width,height):
    reader=QImageReader(str(path))
    if not reader.size().isValid() or reader.size().width()*reader.size().height()>8_500_000:
        raise ValueError('Live-kuvan tarkkuus on virheellinen.')
    if width and height:reader.setScaledSize(QSize(width,height))
    image=reader.read()
    if image.isNull():raise ValueError('Live-kuvaa ei voi lukea: '+str(path))
    return image


def draw_motion(painter,entry,seconds,rect):
    first,second,blend=frame_pair(seconds,len(entry.frames),entry.period)
    # Decode at the displayed size. Keep a small cache, not all 720 frames in memory.
    width,height=1920,1080
    if rect.width()<1920 and rect.height()<1080:
        scale=max(rect.width()/1920,rect.height()/1080)
        width,height=max(1,round(1920*scale)),max(1,round(1080*scale))
    a=load_frame(entry.frames[first],width,height)
    b=load_frame(entry.frames[second],width,height)
    ratio=max(rect.width()/a.width(),rect.height()/a.height())
    target=QRectF(rect.x()+(rect.width()-a.width()*ratio)/2,rect.y()+(rect.height()-a.height()*ratio)/2,
                  a.width()*ratio,a.height()*ratio)
    painter.setOpacity(1)
    painter.drawImage(target,a)
    if blend:
        painter.setOpacity(blend);painter.drawImage(target,b);painter.setOpacity(1)


def render_motion(entry,seconds,width=1920,height=1080):
    image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.black)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    try:draw_motion(painter,entry,seconds,QRectF(0,0,width,height))
    finally:painter.end()
    return image


def write_gnome_slideshow(entry,path):
    root=ET.Element('background')
    start=ET.SubElement(root,'starttime')
    for key,value in (('year',1970),('month',1),('day',1),('hour',0),('minute',0),('second',0)):
        ET.SubElement(start,key).text=str(value)
    for index,frame in enumerate(entry.frames):
        static=ET.SubElement(root,'static')
        ET.SubElement(static,'duration').text=str(STATIC_DURATION)
        ET.SubElement(static,'file').text=str(frame.resolve())
        transition=ET.SubElement(root,'transition',{'type':'overlay'})
        ET.SubElement(transition,'duration').text=str(entry.period/len(entry.frames)-STATIC_DURATION)
        ET.SubElement(transition,'from').text=str(frame.resolve())
        ET.SubElement(transition,'to').text=str(entry.frames[(index+1)%len(entry.frames)].resolve())
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    ET.ElementTree(root).write(temporary,encoding='UTF-8',xml_declaration=True)
    os.replace(temporary,path)
    return path
