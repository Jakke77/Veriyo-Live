"""Numerical reference, recovery, update ordering and actual Qt rendering tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor'), str(ROOT.parent/'vendor')]
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from veriyo_live.calendar import ZONE, blood_label
from veriyo_live.settings import Settings, atomic_json
from veriyo_live.sky import sky_at
from veriyo_live.render import ASSETS, project, render, sky_points
from veriyo_live.platforms import GnomeBackend, WallpaperSession, set_autostart
from veriyo_live.engine import Engine
from veriyo_live.app import Window

APP = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 27, 19, tzinfo=timezone.utc)


def spin_until(condition, seconds=5):
    end = time.monotonic()+seconds
    while not condition() and time.monotonic() < end:
        APP.processEvents()
        QTest.qWait(5)
    if not condition():
        raise AssertionError('Asynchronous task did not finish')


class FakeBackend:
    kind = 'test'
    def __init__(self):
        self.current = 'original'
        self.fail_apply = False
        self.fail_restore = False
        self.captures = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False
        self.calls = []

    def capture(self, lock, directory):
        self.captures += 1
        return {'kind': self.kind, 'original': self.current, 'frames': []}

    def can_resume(self, journal):
        return self.current in [journal['original'], *journal['frames']]

    def apply(self, path, lock, journal):
        self.calls.append('apply')
        self.current = str(path)
        self.started.set()
        if self.block:
            self.release.wait(3)
        if self.fail_apply:
            raise RuntimeError('partial write')

    def restore(self, journal):
        self.calls.append('restore')
        if self.fail_restore:
            raise RuntimeError('restore denied')
        if self.current in journal['frames']:
            self.current = journal['original']


class AstronomyTests(unittest.TestCase):
    def test_reference_erfa(self):
        fixture = json.loads((ROOT/'tests/otava-astropy.json').read_text())
        for case in fixture['fixtures']:
            stars = sky_at(datetime.fromisoformat(case['utc']), fixture['latitude'], fixture['longitude'])
            for got, expected in zip(stars, case['stars']):
                self.assertEqual(got.name, expected['name'])
                self.assertAlmostEqual(got.altitude, expected['altitude'], delta=.025)
                az_error = (got.azimuth-expected['azimuth']+180)%360-180
                self.assertLess(abs(az_error), .15)

    def test_exact_requested_location(self):
        settings = Settings()
        self.assertEqual((settings.latitude, settings.longitude), (65.071562, 25.507046))
        a = sky_at(NOW)
        b = sky_at(NOW, settings.latitude, settings.longitude)
        self.assertEqual(a, b)
        self.assertNotEqual(a, sky_at(NOW, 65.0121, 25.4651))

    def test_longitude_and_time(self):
        later = sky_at(NOW+timedelta(hours=1), 65.071562, 25.507046)
        east = sky_at(NOW, 65.071562, 25.507046+15.04106864)
        for a, b in zip(later, east):
            self.assertAlmostEqual(a.altitude, b.altitude, delta=.001)
            self.assertAlmostEqual(a.azimuth, b.azimuth, delta=.001)

    def test_sidereal_day(self):
        for a,b in zip(sky_at(NOW), sky_at(NOW+timedelta(seconds=86164.0905))):
            self.assertAlmostEqual(a.altitude, b.altitude, delta=.003)
            self.assertAlmostEqual(a.azimuth, b.azimuth, delta=.01)

    def test_naive_and_invalid_location_rejected(self):
        for moment, lat, lon in ((datetime(2026,1,1),65,25),(NOW,91,25),(NOW,65,float('nan'))):
            with self.assertRaises(ValueError):
                sky_at(moment,lat,lon)

    def test_projection_cardinal_geometry(self):
        for alt,az,expected in ((0,0,(0,0)),(90,0,(0,-2)),(0,90,(2,0)),(0,270,(-2,0))):
            for actual, value in zip(project(alt,az), expected):
                self.assertAlmostEqual(actual,value)
        x,y=project(65.071562,0)
        self.assertAlmostEqual(x,0)
        self.assertAlmostEqual(y,-2*math.tan(math.radians(65.071562/2)))

    def test_seven_stars_stay_in_frame_whole_day(self):
        for width,height in ((1920,1080),(1080,1920),(3440,1440)):
            for latitude in (60,65.071562,70):
                settings=Settings(latitude=latitude)
                for minute in range(0,1440,15):
                    stars,points,_,_=sky_points(NOW+timedelta(minutes=minute),settings,width,height)
                    self.assertEqual(len(points),7)
                    for star,point in zip(stars,points):
                        self.assertGreater(star.altitude,0)
                        self.assertTrue(0<point.x()<width,(latitude,point.x()))
                        self.assertTrue(0<point.y()<height,(latitude,point.y()))

    def test_dst_is_same_instant(self):
        utc=datetime(2026,10,25,1,30,tzinfo=timezone.utc)
        self.assertEqual(sky_at(utc),sky_at(utc.astimezone(ZONE)))


class CalendarTests(unittest.TestCase):
    def test_cutover_and_777_year(self):
        epoch=datetime(2026,6,26,1,7,7,tzinfo=ZONE)
        self.assertIn('ennen',blood_label(epoch-timedelta(seconds=1))[0])
        self.assertEqual(blood_label(epoch),('1. päivä · 1. viikko · vuosi 0001','Vuoden päivä 1/777'))
        self.assertIn('111. viikko',blood_label(epoch+timedelta(days=776))[0])
        self.assertIn('vuosi 0002',blood_label(epoch+timedelta(days=777))[0])
        self.assertEqual((epoch+timedelta(days=777)).date().isoformat(),'2028-08-11')

    def test_dst_local_day_boundary(self):
        for hour,expected in ((0,121),(1,122),(3,122),(12,122)):
            moment=datetime(2026,10,25,hour,30,tzinfo=ZONE)
            self.assertEqual(blood_label(moment)[1],f'Vuoden päivä {expected}/777')

    def test_naive_rejected(self):
        with self.assertRaises(ValueError):
            blood_label(datetime(2026,1,1))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.adapter=FakeBackend()
        self.session=WallpaperSession(self.directory,self.adapter)

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_before_partial_write_and_restore(self):
        self.session.begin(False)
        self.assertEqual(json.loads(self.session.path.read_text())['original'],'original')
        self.adapter.fail_apply=True
        frame=self.directory/'frame.jpg'
        with self.assertRaises(RuntimeError):
            self.session.apply(frame,False)
        self.assertEqual(json.loads(self.session.path.read_text())['frames'],[str(frame.resolve())])
        self.session.restore()
        self.assertEqual(self.adapter.current,'original')
        self.assertFalse(self.session.path.exists())

    def test_resume_preserves_first_backup(self):
        self.session.begin(False)
        self.session.apply(self.directory/'a.jpg',False)
        restarted=WallpaperSession(self.directory,self.adapter)
        restarted.begin(False)
        restarted.apply(self.directory/'b.jpg',False)
        self.assertEqual(self.adapter.captures,1)
        restarted.restore()
        self.assertEqual(self.adapter.current,'original')

    def test_changed_wallpaper_not_overwritten(self):
        self.session.begin(False)
        self.session.apply(self.directory/'a.jpg',False)
        self.adapter.current='user chosen elsewhere'
        with self.assertRaises(RuntimeError):
            self.session.begin(False)
        self.session.restore()
        self.assertEqual(self.adapter.current,'user chosen elsewhere')

    def test_restore_failure_keeps_backup(self):
        self.session.begin(False)
        self.adapter.fail_restore=True
        with self.assertRaises(RuntimeError):
            self.session.restore()
        self.assertTrue(self.session.path.exists())

    def test_lock_selection_change_requires_restore(self):
        self.session.begin(False)
        with self.assertRaises(RuntimeError):
            self.session.begin(True)

    def test_many_frames_bounded_by_two_slots(self):
        self.session.begin(False)
        for index in range(50):
            self.session.apply(self.directory/f'frame-{index%2}.jpg',False)
        self.assertEqual(len(json.loads(self.session.path.read_text())['frames']),2)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.adapter=FakeBackend()
        self.engine=Engine(self.directory,adapter_factory=lambda:self.adapter)
        self.engine.timer.stop()

    def tearDown(self):
        self.adapter.release.set()
        if self.engine.busy:
            spin_until(lambda:not self.engine.busy)
        self.engine.deleteLater()
        self.temp.cleanup()

    def test_start_update_restore(self):
        self.engine.start(Settings(),640,360)
        spin_until(lambda:not self.engine.busy)
        self.assertTrue(self.engine.running)
        self.assertTrue((self.directory/'frame-1.jpg').exists())
        self.engine.last_update-=61
        self.engine.last_wall_time-=61
        self.engine.tick()
        spin_until(lambda:not self.engine.busy)
        self.assertEqual(len(self.adapter.calls),2)
        self.engine.restore()
        spin_until(lambda:not self.engine.busy)
        self.assertEqual(self.adapter.current,'original')
        self.assertFalse(self.engine.running)

    def test_restore_waits_for_pending_apply(self):
        self.adapter.block=True
        self.engine.start(Settings(),640,360)
        spin_until(self.adapter.started.is_set)
        self.engine.restore()
        self.assertTrue(self.engine.pending_restore)
        self.assertNotIn('restore',self.adapter.calls)
        self.adapter.release.set()
        spin_until(lambda:not self.engine.busy and not self.engine.pending_restore)
        self.assertEqual(self.adapter.calls,['apply','restore'])
        self.assertEqual(self.adapter.current,'original')

    def test_clock_correction_refreshes_without_wait(self):
        self.engine.start(Settings(),640,360)
        spin_until(lambda:not self.engine.busy)
        self.engine.last_wall_time+=10
        self.engine.tick()
        spin_until(lambda:not self.engine.busy)
        self.assertEqual(len(self.adapter.calls),2)

    def test_stop_and_resume(self):
        self.engine.start(Settings(),640,360)
        spin_until(lambda:not self.engine.busy)
        self.engine.stop()
        self.engine.tick()
        self.assertEqual(len(self.adapter.calls),1)
        self.engine.start(Settings(),640,360)
        spin_until(lambda:not self.engine.busy)
        self.assertEqual(self.adapter.captures,1)
        self.assertTrue(self.engine.running)


class SettingsAndUITests(unittest.TestCase):
    def test_atomic_settings_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            value=Settings(theme='hiillos',autostart=True)
            value.save(path)
            self.assertEqual(Settings.load(path),value)
            for changes in ({'latitude':float('nan')},{'interval':1},{'guides':1},{'latitude':59}):
                with self.assertRaises(ValueError):
                    replace(value,**changes).save(path)
            self.assertEqual(Settings.load(path),value)

    def test_both_assets_decode_and_sky_moves(self):
        for theme in ('otava','hiillos'):
            settings=Settings(theme=theme)
            first=render(NOW,settings,640,360)
            later=render(NOW+timedelta(hours=3),settings,640,360)
            self.assertFalse(first.isNull())
            self.assertNotEqual(first,later)
            self.assertEqual(first.pixelColor(630,50),later.pixelColor(630,50))

    def test_export_size_validation(self):
        with self.assertRaises(ValueError):
            render(NOW,Settings(),100000,100000)

    def test_window_preview_does_not_touch_system_and_demo_is_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('veriyo_live.engine.backend',side_effect=AssertionError('preview modified wallpaper')) as factory:
                window=Window(Settings(),folder)
                window.show()
                APP.processEvents()
                self.assertIsNotNone(window.preview.frame)
                window.demo.setChecked(True)
                window.preview_tick()
                self.assertFalse(window.engine.running)
                self.assertIsNone(window.engine.session)
                factory.assert_not_called()
                self.assertFalse(list(Path(folder).glob('*.json')))
                window.resize(900,720)
                APP.processEvents()
                self.assertLessEqual(window.start_button.mapTo(window,window.start_button.rect().topLeft()).x(),window.width())
                window.preview_timer.stop()
                window.engine.timer.stop()
                window.allow_quit=True
                window.close()

    @unittest.skipIf(os.name=='nt','Linux Desktop Entry only')
    def test_autostart_is_own_entry_and_no_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
                root=Path(folder)/'a $HOME % name'
                set_autostart(True,root)
                path=Path(folder)/'autostart/veriyo-live.desktop'
                value=path.read_text()
                self.assertIn('%%',value)
                self.assertIn('\\$',value)
                self.assertIn('--background',value)
                set_autostart(False,root)
                self.assertFalse(path.exists())


class GnomeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            (GnomeBackend.desktop,'picture-uri'): "'file:///before.jpg'",
            (GnomeBackend.desktop,'picture-uri-dark'): "'file:///before-dark.jpg'",
            (GnomeBackend.desktop,'picture-options'): "'scaled'",
            (GnomeBackend.saver,'picture-uri'): "'file:///lock-before.jpg'",
        }
        self.writable = True
        self.writes=[]
        self.adapter=object.__new__(GnomeBackend)

    def command(self, args, **kwargs):
        self.assertEqual(args[0],'gsettings')
        action,schema=args[1:3]
        if action=='list-keys':
            return '\n'.join(k for s,k in self.values if s==schema)
        key=args[3]
        if action=='get':
            return self.values[schema,key]
        if action=='writable':
            return str(self.writable).lower()
        if action=='set':
            # Canonical GLib output uses single quotes, whereas writes use JSON quotes.
            value=args[4]
            canonical=repr(json.loads(value)) if value.startswith('"') else value
            self.values[schema,key]=canonical
            self.writes.append((schema,key,canonical))
            return ''
        self.fail('unknown command')

    def test_actual_gsettings_plan_and_restore_both_backgrounds(self):
        with tempfile.TemporaryDirectory() as folder, patch('veriyo_live.platforms.run',side_effect=self.command):
            before=dict(self.values)
            session=WallpaperSession(folder,self.adapter)
            session.begin(True)
            session.apply(Path(folder)/'frame 1.jpg',True)
            self.assertEqual(len(self.writes),4)
            self.assertEqual(self.values[self.adapter.desktop,'picture-options'],"'zoom'")
            session.begin(True)
            session.restore()
            self.assertEqual(self.values,before)

    def test_locked_settings_make_no_changes(self):
        self.writable=False
        with tempfile.TemporaryDirectory() as folder, patch('veriyo_live.platforms.run',side_effect=self.command):
            with self.assertRaises(RuntimeError):
                WallpaperSession(folder,self.adapter).begin(False)
            self.assertEqual(self.writes,[])

    def test_external_dark_wallpaper_change_survives(self):
        with tempfile.TemporaryDirectory() as folder, patch('veriyo_live.platforms.run',side_effect=self.command):
            session=WallpaperSession(folder,self.adapter)
            session.begin(False)
            session.apply(Path(folder)/'frame.jpg',False)
            self.values[self.adapter.desktop,'picture-uri-dark']="'file:///user-new.jpg'"
            with self.assertRaises(RuntimeError):
                session.begin(False)
            session.restore()
            self.assertEqual(self.values[self.adapter.desktop,'picture-uri-dark'],"'file:///user-new.jpg'")
            self.assertEqual(self.values[self.adapter.desktop,'picture-uri'],"'file:///before.jpg'")


if __name__=='__main__':
    unittest.main()
