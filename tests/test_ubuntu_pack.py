"""Pack security, 45-version selection, native slideshow and pause/restore ordering."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED

from PyQt6.QtCore import QByteArray,QBuffer,QIODevice
from PyQt6.QtGui import QColor,QImage
from PyQt6.QtWidgets import QApplication
from veriyo_live.ubuntu_pack import (PackLibrary,catalog,versions,validate_manifest,frame_pair,
                                    render_motion,write_gnome_slideshow,load_frame)
from veriyo_live.settings import Settings
from veriyo_live.render import render
from veriyo_live.app import Window
from veriyo_live.engine import Engine
from veriyo_live.platforms import GnomeBackend,WallpaperSession
from test_live import FakeBackend,spin_until,APP
from test_windows_lock import FakeWindowsBackend


def sample_manifest():
    return {'format':'veriyo-ubuntu-live','version':'1.0.0','releases':[
        {'id':row['id'],'version':row['version'],'name':row['name'],'motion_label':row['motion_label'],
         'period':48,'size':[1920,1080],'source_sha256':row['sha256'],
         'frames':[{'file':f'{row["id"]}/{i:02d}.jpg','sha256':'0'*64} for i in range(16)]}
        for row in catalog()]}


def jpeg(color):
    image=QImage(1920,1080,QImage.Format.Format_RGB32);image.fill(QColor(color))
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer,'JPEG',90)
    return bytes(data)


class ManifestTests(unittest.TestCase):
    def test_all_45_versions_and_shared_original_are_present(self):
        self.assertEqual(len(versions()),45)
        self.assertEqual(len(set(versions())),45)
        self.assertEqual(versions()[0],'4.10');self.assertEqual(versions()[-1],'26.10')
        rows={row['version']:row for row in catalog()}
        self.assertEqual(rows['14.04']['sha256'],rows['14.10']['sha256'])
        self.assertNotEqual(rows['14.04']['name'],rows['14.10']['name'])

    def test_settings_remain_compatible_and_reject_unknown_ubuntu(self):
        value=Settings(theme='ubuntu',ubuntu_version='8.04').validate()
        self.assertEqual(value.ubuntu_version,'8.04')
        for version in ('../../../tmp','27.04',None):
            with self.assertRaises(ValueError):Settings(ubuntu_version=version).validate()

    def test_manifest_requires_known_complete_sources_and_bounded_motion(self):
        value=sample_manifest();self.assertEqual(len(validate_manifest(value)),720)
        for change in ('missing','duplicate','source','path','fast','size','nan'):
            bad=deepcopy(value)
            if change=='missing':bad['releases'].pop()
            elif change=='duplicate':bad['releases'][1]=bad['releases'][0]
            elif change=='source':bad['releases'][0]['source_sha256']='0'*64
            elif change=='path':bad['releases'][0]['frames'][0]['file']='../../elsewhere.jpg'
            elif change=='fast':bad['releases'][0]['period']=1
            elif change=='size':bad['releases'][0]['size']=[100000,100000]
            elif change=='nan':bad['releases'][0]['period']=float('nan')
            with self.subTest(change=change),self.assertRaises(ValueError):validate_manifest(bad)

    def test_frame_blend_is_continuous_at_loop_and_respects_static_hold(self):
        self.assertEqual(frame_pair(0),(0,1,0))
        self.assertEqual(frame_pair(.02),(0,1,0))
        last=frame_pair(48-1e-7)
        self.assertEqual(last[:2],(15,0));self.assertAlmostEqual(last[2],1,places=6)
        self.assertEqual(frame_pair(48),frame_pair(0))
        for seconds in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):frame_pair(seconds)

    def test_unsafe_archive_names_and_links_never_escape_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);library=PackLibrary(root/'data')
            for index,name in enumerate(('../escaped.txt','C:/escaped.txt','x\\escaped.txt','/escaped.txt','link.jpg')):
                archive=root/f'bad-{index}.zip'
                with ZipFile(archive,'w') as stream:
                    entry=ZipInfo(name)
                    if name=='link.jpg':entry.external_attr=(stat.S_IFLNK|0o777)<<16
                    stream.writestr(entry,b'bad')
                with self.subTest(name=name),self.assertRaises(ValueError):library.install(archive)
                self.assertFalse((root/'escaped.txt').exists())
                self.assertFalse(library.installed())

    def test_duplicate_archive_names_and_excess_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);library=PackLibrary(root/'data')
            for names in (('PACK.JSON','pack.json'),tuple('x'+str(i) for i in range(901))):
                archive=root/'bad.zip'
                with ZipFile(archive,'w') as stream:
                    for name in names:stream.writestr(name,b'{}')
                with self.assertRaises(ValueError):library.install(archive)


class InstalledPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.root=Path(cls.temporary.name)
        cls.library=PackLibrary(cls.root/'installed')
        value=sample_manifest()
        a,b=jpeg('#281327'),jpeg('#311932')
        cls.archive=cls.root/'pack.zip'
        with ZipFile(cls.archive,'w',ZIP_DEFLATED) as stream:
            for row in value['releases']:
                for index,frame in enumerate(row['frames']):
                    content=a if index%2==0 else b
                    frame['sha256']=sha256(content).hexdigest();stream.writestr(frame['file'],content)
            stream.writestr('pack.json',json.dumps(value))
            stream.writestr('LICENSES/source.txt','Synthetic test images')
        cls.library.install(cls.archive)

    @classmethod
    def tearDownClass(cls):
        cls.library.entry.cache_clear();load_frame.cache_clear();cls.temporary.cleanup()

    def test_valid_archive_and_all_versions_load(self):
        self.assertTrue(self.library.installed())
        for version in versions():
            entry=self.library.entry(version)
            self.assertEqual(entry.version,version);self.assertEqual(len(entry.frames),16)
            self.assertTrue(all(path.is_file() for path in entry.frames))

    def test_xml_duration_absolute_paths_and_final_transition(self):
        entry=self.library.entry('22.04')
        path=write_gnome_slideshow(entry,self.root/'test & source'/ 'live.xml')
        xml=ET.parse(path).getroot()
        self.assertEqual(len(xml.findall('static')),16);self.assertEqual(len(xml.findall('transition')),16)
        total=sum(float(item.text) for item in xml.findall('./static/duration')+xml.findall('./transition/duration'))
        self.assertAlmostEqual(total,48)
        self.assertEqual(xml.findall('transition')[-1].findtext('to'),str(entry.frames[0].resolve()))
        for node in xml.findall('./static/file'):self.assertTrue(Path(node.text).is_absolute())

    def test_render_is_periodic_and_ubuntu_has_no_sky_or_calendar_overlay(self):
        entry=self.library.entry('26.10')
        self.assertEqual(render_motion(entry,0,640,360),render_motion(entry,48,640,360))
        self.assertNotEqual(render_motion(entry,0,640,360),render_motion(entry,2.9,640,360))
        moment=datetime(2026,10,28,tzinfo=timezone.utc)
        with patch('veriyo_live.render.sky_at',side_effect=AssertionError('sky overlay not expected')):
            image=render(moment,Settings(theme='ubuntu'),640,360,library=self.library)
        self.assertEqual(image,render_motion(entry,moment.timestamp(),640,360))
        with self.assertRaises(ValueError):render(datetime(2026,10,28),Settings(theme='ubuntu'),640,360,library=self.library)

    def test_bad_checksum_keeps_previous_installation_intact(self):
        with ZipFile(self.archive) as original:
            value=json.loads(original.read('pack.json'))
        value['releases'][0]['frames'][0]['sha256']='0'*64
        target=self.root/'invalid.zip'
        with ZipFile(self.archive) as original,ZipFile(target,'w') as out:
            for info in original.infolist():out.writestr(info.filename,json.dumps(value) if info.filename=='pack.json' else original.read(info))
        before=(self.library.root/'pack.json').read_bytes()
        with self.assertRaises(ValueError):self.library.install(target)
        self.assertEqual(before,(self.library.root/'pack.json').read_bytes())

    def test_version_dropdown_only_appears_for_ubuntu_and_choice_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(),folder)
            window.library=self.library
            try:
                self.assertTrue(window.ubuntu_row.isHidden())
                window.theme.setCurrentIndex(window.theme.findData('ubuntu'))
                self.assertFalse(window.ubuntu_row.isHidden())
                self.assertEqual(window.ubuntu_version.count(),45)
                window.ubuntu_version.setCurrentIndex(window.ubuntu_version.findData('22.04'))
                with patch('veriyo_live.app.set_autostart'):
                    self.assertTrue(window.save())
                self.assertEqual(Settings.load(Path(folder)/'settings.json').ubuntu_version,'22.04')
                self.assertFalse(window.date_mode.isEnabled())
                window.theme.setCurrentIndex(window.theme.findData('otava'))
                self.assertTrue(window.ubuntu_row.isHidden())
                self.assertTrue(window.date_mode.isEnabled())
            finally:
                window.preview_timer.stop();window.engine.timer.stop();window.allow_quit=True;window.close()

    def test_native_mode_stops_with_a_static_frame_and_restores_original(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.library=self.library;engine.timer.stop()
            try:
                engine.start(Settings(theme='ubuntu'),640,360);spin_until(lambda:not engine.busy)
                self.assertIsNotNone(engine.motion_entry)
                engine.tick();self.assertEqual(adapter.calls,['apply'])
                engine.stop();spin_until(lambda:not engine.busy)
                self.assertFalse(engine.running);self.assertIsNone(engine.motion_entry)
                self.assertTrue((Path(folder)/'ubuntu-paused.jpg').is_file())
                self.assertEqual(adapter.calls,['apply','apply'])
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_stop_during_pending_start_waits_before_freezing(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();adapter.block=True
            engine=Engine(folder,adapter_factory=lambda:adapter);engine.library=self.library;engine.timer.stop()
            try:
                engine.start(Settings(theme='ubuntu'),640,360);spin_until(adapter.started.is_set)
                engine.stop();self.assertTrue(engine.pending_freeze)
                adapter.release.set();spin_until(lambda:not engine.busy and not engine.pending_freeze)
                self.assertEqual(adapter.calls,['apply','apply']);self.assertIsNone(engine.motion_entry)
            finally:
                adapter.release.set()
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_windows_lock_rejection_still_publishes_motion_entry_and_freezes_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeWindowsBackend();adapter.lock_error='rejected'
            engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.library=self.library;engine.timer.stop()
            try:
                engine.start(Settings(theme='ubuntu',lock_screen=True),640,360)
                spin_until(lambda:not engine.busy)
                self.assertTrue(engine.running)
                self.assertIsNotNone(engine.motion_entry)
                self.assertTrue(engine.session.warning)
                engine.set_ubuntu_version('8.04');spin_until(lambda:not engine.busy)
                self.assertEqual(engine.motion_entry.version,'8.04')
                self.assertEqual(adapter.lock_calls,['Backup','Set'])
                engine.stop();spin_until(lambda:not engine.busy)
                self.assertIsNone(engine.motion_entry)
                self.assertTrue((Path(folder)/'ubuntu-paused.jpg').is_file())
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original-desktop')
                self.assertEqual(adapter.lock_image,b'original-lock')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_gnome_gets_xml_on_desktop_and_jpeg_on_lock_screen(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=object.__new__(GnomeBackend)
            writes=[];adapter.set=lambda schema,key,value:writes.append((schema,key,value))
            entry=self.library.entry('26.10')
            xml=write_gnome_slideshow(entry,Path(folder)/'live.xml')
            journal={'original':[{'schema':adapter.desktop,'key':'picture-uri'},
                                 {'schema':adapter.desktop,'key':'picture-uri-dark'},
                                 {'schema':adapter.desktop,'key':'picture-options'},
                                 {'schema':adapter.saver,'key':'picture-uri'}]}
            adapter.apply_paths(xml,entry.frames[0],journal)
            self.assertEqual(json.loads(writes[0][2]),xml.resolve().as_uri())
            self.assertEqual(json.loads(writes[3][2]),entry.frames[0].resolve().as_uri())

    def test_active_version_change_updates_scene_without_recapturing_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.library=self.library;engine.timer.stop()
            try:
                engine.start(Settings(theme='ubuntu'),640,360);spin_until(lambda:not engine.busy)
                engine.set_ubuntu_version('8.04');spin_until(lambda:not engine.busy)
                self.assertEqual(engine.motion_entry.version,'8.04')
                self.assertEqual(engine.settings.ubuntu_version,'8.04')
                self.assertEqual(adapter.captures,1)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_mixed_background_switch_keeps_the_same_original_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.library=self.library;engine.timer.stop()
            try:
                engine.start(Settings(theme='stream'),640,360);spin_until(lambda:not engine.busy)
                engine.set_background('ubuntu:8.04');spin_until(lambda:not engine.busy)
                self.assertEqual(engine.settings.theme,'ubuntu');self.assertEqual(engine.motion_entry.version,'8.04')
                engine.set_background('rose_garden');spin_until(lambda:not engine.busy)
                self.assertEqual(engine.motion_entry.settings.theme,'rose_garden')
                self.assertEqual(adapter.captures,1)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_disguised_non_jpeg_is_rejected_before_image_decoder(self):
        with ZipFile(self.archive) as original:
            value=json.loads(original.read('pack.json'))
        payload=b'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"/>'
        first=value['releases'][0]['frames'][0]
        first['sha256']=sha256(payload).hexdigest()
        target=self.root/'disguised.zip'
        with ZipFile(self.archive) as original,ZipFile(target,'w') as out:
            for info in original.infolist():
                content=json.dumps(value) if info.filename=='pack.json' else payload if info.filename==first['file'] else original.read(info)
                out.writestr(info.filename,content)
        before=(self.library.root/'pack.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'JPEG'):self.library.install(target)
        self.assertEqual(before,(self.library.root/'pack.json').read_bytes())
