"""GNOME caches by URI: a new snapshot must never reuse a previous scene URI."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from veriyo_live.app import Window
from veriyo_live.engine import Engine
from veriyo_live.scenes import build_slideshow, retire_slideshows
from veriyo_live.settings import Settings
from test_live import FakeBackend, spin_until

NOW=datetime(2026,10,29,2,25,tzinfo=timezone.utc)


class Gnome(FakeBackend):
    kind='gnome'
    def apply_paths(self,desktop,lock,journal):
        if self.fail_apply:raise RuntimeError('GNOME refused update')
        self.current=str(Path(desktop).resolve())
        self.calls.append('apply')


class GnomeCacheTests(unittest.TestCase):
    def test_rebuilding_never_changes_files_of_a_displayed_or_cached_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            cache={};old={}
            for i,theme in enumerate(('polaris','bloodwork','deep_space','polaris','polaris')):
                entry,xml=build_slideshow(NOW+timedelta(minutes=i),Settings(theme=theme),640,360,folder,i%2)
                for name,content in old.items():self.assertEqual(Path(name).read_bytes(),content)
                for frame in entry.frames:
                    # Model Shell's URI texture cache, which can outlive a theme.
                    uri=frame.as_uri();content=frame.read_bytes()
                    self.assertEqual(cache.setdefault(uri,content),content)
                    self.assertNotIn(str(frame),old)
                    old[str(frame)]=content
                self.assertTrue(xml.is_file())

    def test_switch_and_refresh_keep_two_complete_snapshots_and_one_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=Gnome();engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='polaris'),640,360);spin_until(lambda:not engine.busy)
                previous=Path(adapter.current)
                for theme in ('bloodwork','deep_space','polaris','moon','stream'):
                    engine.set_background(theme);spin_until(lambda:not engine.busy)
                    current=Path(adapter.current)
                    self.assertNotEqual(current,previous)
                    for xml in (current,previous):
                        for item in ET.parse(xml).findall('./static/file'):
                            self.assertTrue(Path(item.text).is_file())
                    self.assertEqual(len(list(Path(folder).glob('scene-*/*.jpg'))),32)
                    self.assertLessEqual(len(json.loads(engine.session.path.read_text())['frames']),4)
                    previous=current
                self.assertEqual(adapter.captures,1)
                engine.stop();spin_until(lambda:not engine.busy)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_failed_render_or_apply_preserves_current_snapshot_for_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=Gnome();engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='polaris'),640,360);spin_until(lambda:not engine.busy)
                current=Path(adapter.current);content=current.read_bytes()
                with patch('veriyo_live.scenes.render_scene',side_effect=RuntimeError('render failure')):
                    with self.assertRaises(RuntimeError):
                        build_slideshow(NOW,Settings(theme='moon'),640,360,folder,0)
                self.assertEqual(len(list(Path(folder).glob('scene-*'))),1)
                adapter.fail_apply=True
                engine.set_background('bloodwork');spin_until(lambda:not engine.busy)
                self.assertFalse(engine.running)
                self.assertEqual(current.read_bytes(),content)
                self.assertTrue(all(Path(x.text).is_file() for x in ET.parse(current).findall('./static/file')))
                adapter.fail_apply=False
                engine.start(Settings(theme='bloodwork'),640,360);spin_until(lambda:not engine.busy)
                self.assertTrue(current.is_file())  # The actual outgoing scene, not the failed attempt.
                self.assertEqual(len(list(Path(folder).glob('scene-*/*.jpg'))),32)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_cleanup_preserves_original_unrelated_and_linked_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            original,xml=build_slideshow(NOW,Settings(theme='polaris'),640,360,root,0)
            old,oldxml=build_slideshow(NOW,Settings(theme='moon'),640,360,root,1)
            current,newxml=build_slideshow(NOW,Settings(theme='bloodwork'),640,360,root,0)
            unrelated=root/'scene-not-ours';unrelated.mkdir();(unrelated/'note.txt').write_text('user data')
            external=root/'external';external.mkdir();(external/'00.jpg').write_bytes(b'keep')
            alias=root/('scene-1-'+'a'*32)
            try:alias.symlink_to(external,target_is_directory=True)
            except OSError:pass  # Windows runners may not permit user symlinks.
            journal={'original':[{'value':json.dumps(xml.as_uri())}],
                     'frames':[str(oldxml),str(newxml),str(current.frames[0])]}
            retire_slideshows(root,newxml,journal)
            self.assertTrue(xml.is_file());self.assertTrue(oldxml.is_file());self.assertTrue(newxml.is_file())
            self.assertEqual((unrelated/'note.txt').read_text(),'user data')
            self.assertEqual((external/'00.jpg').read_bytes(),b'keep')
            if alias.is_symlink():self.assertTrue(alias.exists())

    def test_legacy_fixed_slots_retire_only_after_a_new_snapshot_is_applied(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);legacy=root/'scene-0';legacy.mkdir()
            legacy_frame=legacy/'00.jpg';legacy_frame.write_bytes(b'old version frame')
            entry,xml=build_slideshow(NOW,Settings(theme='polaris'),640,360,root,1)
            journal={'original':[],'frames':[str(legacy_frame),str(xml),str(entry.frames[0])]}
            retired=retire_slideshows(root,xml,journal)
            self.assertFalse(retired);self.assertTrue(legacy_frame.exists())
            next_entry,next_xml=build_slideshow(NOW,Settings(theme='bloodwork'),640,360,root,0)
            journal['frames'] += [str(next_xml),str(next_entry.frames[0])]
            retired=retire_slideshows(root,next_xml,journal)
            self.assertIn(str(legacy_frame),retired)
            self.assertFalse(legacy.exists())
            self.assertTrue(xml.is_file());self.assertTrue(next_xml.is_file())

    def test_26_minute_shuffle_does_not_fire_on_animation_or_refresh_times(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(theme='polaris',shuffle_enabled=True,shuffle_interval=1560,
                                   shuffle_choices=['polaris','bloodwork']),folder)
            window.engine.timer.stop();window.preview_timer.stop();window.shuffle_timer.stop()
            adapter=FakeBackend();window.engine.adapter_factory=lambda:adapter
            try:
                window.engine.start(window.settings,640,360);spin_until(lambda:not window.engine.busy)
                base=time.monotonic()
                for seconds in (0,1,6,12,60,96,300,1559):
                    with patch('veriyo_live.app.time.monotonic',return_value=base+seconds):window.shuffle_tick()
                    self.assertEqual(window.engine.settings.theme,'polaris')
                with patch('veriyo_live.app.time.monotonic',return_value=base+1560):window.shuffle_tick()
                spin_until(lambda:not window.engine.busy)
                self.assertEqual(window.engine.settings.theme,'bloodwork')
                for seconds in (1561,1566,1600,3119):
                    with patch('veriyo_live.app.time.monotonic',return_value=base+seconds):window.shuffle_tick()
                    self.assertEqual(window.engine.settings.theme,'bloodwork')
            finally:
                if window.engine.busy:spin_until(lambda:not window.engine.busy)
                window.engine.running=False;window.allow_quit=True;window.close()
