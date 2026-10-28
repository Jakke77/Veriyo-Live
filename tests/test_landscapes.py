"""Civil-time scenery, visible looped motion and desktop recovery."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtGui import QColor, QImage
from veriyo_live.app import Window
from veriyo_live.engine import Engine
from veriyo_live.landscapes import LANDSCAPES, light_for_minute, lighting_at
from veriyo_live.render import render
from veriyo_live.scenes import PERIOD, SceneEntry, build_slideshow, render_scene
from veriyo_live.settings import Settings
from test_live import APP, spin_until
from test_windows_lock import FakeWindowsBackend

DAY=datetime(2026,10,28,10,tzinfo=timezone.utc)
NIGHT=DAY+timedelta(hours=12)


def brightness(image):
    return sum(sum(QColor(image.pixel(x,y)).getRgb()[:3])
               for x in range(20,image.width(),40) for y in range(20,image.height(),40))


class LandscapeTests(unittest.TestCase):
    def test_clock_selects_all_four_lighting_periods(self):
        for hour,name in ((6,'Aamu'),(12,'Päivä'),(18,'Ilta'),(23,'Yö')):
            self.assertEqual(light_for_minute(hour*60).name,name)

    def test_lighting_follows_selected_zone_and_dst_fold(self):
        self.assertEqual(lighting_at(DAY,'Europe/Helsinki').name,'Päivä')
        self.assertEqual(lighting_at(DAY,'Australia/Sydney').name,'Yö')
        first=datetime(2026,10,25,0,30,tzinfo=timezone.utc)
        second=first+timedelta(hours=1)
        self.assertEqual(lighting_at(first,'Europe/Helsinki'),lighting_at(second,'Europe/Helsinki'))

    def test_lighting_colour_has_no_sudden_jump_at_midnight_or_period_boundaries(self):
        for minute in (0,300,420,600,720,1020,1140,1260):
            a=light_for_minute((minute-1)%1440);b=light_for_minute(minute)
            self.assertLess(abs(a.daylight-b.daylight),.02)
            for key in ('top','horizon','water','foliage'):
                rgb1=QColor(getattr(a,key)).getRgb()[:3];rgb2=QColor(getattr(b,key)).getRgb()[:3]
                self.assertLessEqual(max(abs(x-y) for x,y in zip(rgb1,rgb2)),3)

    def test_day_is_visibly_brighter_than_night_in_every_landscape(self):
        for theme in LANDSCAPES:
            with self.subTest(theme=theme):
                settings=Settings(theme=theme,date_mode='none',guides=False)
                a=render_scene(DAY,settings,640,360,0)
                b=render_scene(NIGHT,settings,640,360,0)
                self.assertGreater(brightness(a),brightness(b)*1.5)

    def test_flow_and_scenery_move_and_remain_continuous_across_the_loop(self):
        for theme in LANDSCAPES:
            with self.subTest(theme=theme):
                settings=Settings(theme=theme,date_mode='none',guides=False)
                a=render_scene(NIGHT,settings,640,360,0)
                b=render_scene(NIGHT,settings,640,360,8)
                seam=render_scene(NIGHT,settings,640,360,PERIOD-1e-5)
                ba=a.constBits().asstring(a.sizeInBytes());bb=b.constBits().asstring(b.sizeInBytes())
                bs=seam.constBits().asstring(seam.sizeInBytes())
                self.assertGreater(sum(x!=y for x,y in zip(ba,bb)),1000)
                self.assertLess(sum(x!=y for x,y in zip(ba,bs)),5000)

    def test_same_instant_uses_different_local_lighting(self):
        for theme in LANDSCAPES:
            settings=Settings(theme=theme,date_mode='none',guides=False)
            a=render(DAY,settings,640,360,animation_seconds=0)
            settings.timezone='Australia/Sydney'
            b=render(DAY,settings,640,360,animation_seconds=0)
            self.assertGreater(brightness(a),brightness(b)*1.5)

    def test_gnome_slideshow_contains_the_current_local_lighting(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=Settings(theme='stream',date_mode='none',guides=False)
            day,xml1=build_slideshow(DAY,settings,640,360,folder,0)
            night,xml2=build_slideshow(NIGHT,settings,640,360,folder,1)
            self.assertEqual(len(day.frames),16);self.assertEqual(day.period,PERIOD)
            self.assertTrue(xml1.is_file() and xml2.is_file())
            self.assertGreater(brightness(QImage(str(day.frames[0]))),brightness(QImage(str(night.frames[0])))*1.5)
            self.assertEqual(len(list(Path(folder).glob('scene-*/*.jpg'))),32)

    def test_all_new_scenes_stop_freeze_and_restore_without_recapturing_backup(self):
        for theme in LANDSCAPES:
            with self.subTest(theme=theme),tempfile.TemporaryDirectory() as folder:
                adapter=FakeWindowsBackend();engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
                try:
                    engine.start(Settings(theme=theme),640,360);spin_until(lambda:not engine.busy)
                    self.assertTrue(engine.running);self.assertIsInstance(engine.motion_entry,SceneEntry)
                    engine.stop();spin_until(lambda:not engine.busy)
                    self.assertFalse(QImage(str(Path(folder)/'scene-paused.jpg')).isNull())
                    engine.start(Settings(theme=theme),640,360);spin_until(lambda:not engine.busy)
                    engine.restore();spin_until(lambda:not engine.busy)
                    self.assertEqual(adapter.current,'original-desktop')
                    self.assertFalse((Path(folder)/'wallpaper-backup.json').exists())
                finally:
                    if engine.busy:spin_until(lambda:not engine.busy)
                    engine.deleteLater()

    def test_new_menu_choices_and_day_preview_are_available_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(),folder);window.engine.timer.stop();window.preview_timer.stop()
            try:
                for theme in LANDSCAPES:
                    window.theme.setCurrentIndex(window.theme.findData(theme))
                    self.assertFalse(window.demo.isHidden())
                    self.assertFalse(window.timezone.isHidden())
                    self.assertIn('vuorokaudenaika',window.guides.text())
                    with patch('veriyo_live.app.set_autostart'):self.assertTrue(window.save())
                    self.assertEqual(Settings.load(Path(folder)/'settings.json').theme,theme)
            finally:
                window.allow_quit=True;window.close()

    def test_preview_clock_uses_the_selected_landscape_zone(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(theme='stream',timezone='Australia/Sydney'),folder)
            window.engine.timer.stop();window.preview_timer.stop()
            try:
                window.refresh_preview(moment=DAY)
                self.assertIn('21:00:00 AEDT',window.time_label.text())
            finally:
                window.allow_quit=True;window.close()
