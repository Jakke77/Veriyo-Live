"""Date selection migration, visible output and updates during a running session."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication
from veriyo_live.calendar import date_block
from veriyo_live.engine import Engine
from veriyo_live.render import render
from veriyo_live.settings import Settings, atomic_json
from veriyo_live.app import Window
from test_live import FakeBackend, spin_until

NOW = datetime(2026,10,27,13,41,tzinfo=timezone.utc)
APP = QApplication.instance() or QApplication([])


class DateSelectionTests(unittest.TestCase):
    def test_old_calendar_choice_is_preserved_without_changing_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for old,expected in ((False,'none'),(True,'blood')):
                atomic_json(path,{'theme':'hiillos','calendar':old,'latitude':65.1,'interval':1560,'autostart':True})
                value=Settings.load(path)
                self.assertEqual(value.date_mode,expected)
                self.assertEqual((value.theme,value.latitude,value.interval,value.autostart),('hiillos',65.1,1560,True))
            atomic_json(path,{'calendar':True,'date_mode':'gregorian'})
            self.assertEqual(Settings.load(path).date_mode,'gregorian')

    def test_invalid_legacy_choice_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            atomic_json(path,{'calendar':'false'})
            with self.assertRaises(ValueError):
                Settings.load(path)

    def test_all_four_choices_persist_in_new_format(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for mode in ('none','blood','gregorian','both'):
                Settings(date_mode=mode).save(path)
                self.assertEqual(Settings.load(path).date_mode,mode)
                self.assertNotIn('calendar',json.loads(path.read_text(encoding='utf-8')))
            with self.assertRaises(ValueError):
                Settings(date_mode='unknown').save(path)
            self.assertEqual(Settings.load(path).date_mode,'both')

    def test_dates_and_timezone_are_correct_for_each_mode(self):
        self.assertEqual(date_block(NOW,'none'),('',()))
        title,lines=date_block(NOW,'blood')
        self.assertEqual(title,'VERI AIKA')
        self.assertIn('vuosi 0001',lines)
        self.assertIn('Vuoden päivä 124/777',lines)
        title,lines=date_block(NOW,'gregorian')
        self.assertEqual(title,'PÄIVÄMÄÄRÄ')
        self.assertEqual(lines,('Tiistai','27.10.2026 · klo 15:41 EET'))
        title,lines=date_block(NOW,'both')
        self.assertIn('VERI AIKA',title)
        self.assertIn('Vuoden päivä 124/777',lines)
        self.assertIn('27.10.2026 · klo 15:41 EET',lines)

    def test_hidden_wallpaper_has_no_date_or_time_anywhere(self):
        from veriyo_live.render import text
        with patch('veriyo_live.render.text',wraps=text) as painted:
            render(NOW,Settings(date_mode='none'),1280,720)
        strings=[call.args[2] for call in painted.call_args_list]
        combined=' '.join(strings)
        self.assertNotIn('2026',combined)
        self.assertNotIn('15:41',combined)
        self.assertNotIn('VERI AIKA',combined)
        self.assertNotIn('/777',combined)
        self.assertIn('Alkaid',strings)

    def test_modes_only_change_the_date_area_not_the_sky(self):
        hidden=render(NOW,Settings(date_mode='none'),1280,720)
        sky_rect=QRect(0,0,800,650)
        date_rect=QRect(850,490,420,190)
        images=[]
        for mode in ('blood','gregorian','both'):
            image=render(NOW,Settings(date_mode=mode),1280,720)
            self.assertEqual(image.copy(sky_rect),hidden.copy(sky_rect))
            self.assertNotEqual(image.copy(date_rect),hidden.copy(date_rect))
            images.append(image)
        self.assertNotEqual(images[0],images[1])
        self.assertNotEqual(images[1],images[2])

    def test_ui_selection_saves_and_updates_active_wallpaper_immediately(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(interval=1560),folder)
            adapter=FakeBackend()
            window.engine.adapter_factory=lambda:adapter
            try:
                window.engine.start(Settings(interval=1560),640,360)
                spin_until(lambda:not window.engine.busy)
                self.assertTrue(window.date_mode.isEnabled())
                window.date_mode.setCurrentIndex(window.date_mode.findData('none'))
                spin_until(lambda:not window.engine.busy)
                self.assertEqual(window.engine.settings.date_mode,'none')
                self.assertEqual(Settings.load(Path(folder)/'settings.json').date_mode,'none')
                self.assertEqual(len(adapter.calls),2)  # No wait for the 26-minute interval.
                self.assertEqual(adapter.captures,1)
                window.engine.restore()
                spin_until(lambda:not window.engine.busy)
            finally:
                window.engine.timer.stop()
                window.preview_timer.stop()
                window.allow_quit=True
                window.close()

    def test_choice_during_apply_waits_and_latest_selection_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend()
            adapter.block=True
            engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.timer.stop()
            try:
                engine.start(Settings(),640,360)
                spin_until(adapter.started.is_set)
                engine.set_date_mode('none')
                engine.set_date_mode('both')
                self.assertEqual(engine.settings.date_mode,'blood')
                self.assertEqual(adapter.calls,['apply'])
                adapter.release.set()
                spin_until(lambda:not engine.busy)
                self.assertEqual(engine.settings.date_mode,'both')
                self.assertEqual(adapter.calls,['apply','apply'])
                engine.restore()
                spin_until(lambda:not engine.busy)
            finally:
                adapter.release.set()
                spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_restore_takes_precedence_over_pending_date_change(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend()
            adapter.block=True
            engine=Engine(folder,adapter_factory=lambda:adapter)
            engine.timer.stop()
            try:
                engine.start(Settings(),640,360)
                spin_until(adapter.started.is_set)
                engine.set_date_mode('none')
                engine.restore()
                adapter.release.set()
                spin_until(lambda:not engine.busy and not engine.pending_restore)
                self.assertEqual(adapter.calls,['apply','restore'])
                self.assertEqual(adapter.current,'original')
            finally:
                adapter.release.set()
                spin_until(lambda:not engine.busy)
                engine.deleteLater()
