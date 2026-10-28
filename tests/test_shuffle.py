"""Selected random backgrounds, serialized choices and one original backup."""
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QListWidget
from veriyo_live.app import Window
from veriyo_live.engine import Engine
from veriyo_live.settings import Settings
from veriyo_live.shuffle import background_key, choose_next, eligible_options
from test_live import FakeBackend, spin_until


class ShuffleTests(unittest.TestCase):
    def test_settings_migrate_and_reject_invalid_or_unknown_selections(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';path.write_text('{"theme":"stream"}')
            value=Settings.load(path)
            self.assertFalse(value.shuffle_enabled);self.assertEqual(value.shuffle_choices,[])
            self.assertEqual(value.shuffle_interval,1560)
            for change in ({'shuffle_interval':True},{'shuffle_interval':7},{'shuffle_enabled':1},
                           {'shuffle_choices':['not-a-theme']},{'shuffle_choices':['stream','stream']},
                           {'shuffle_choices':[{}]},{'shuffle_choices':'stream'}):
                with self.subTest(change=change),self.assertRaises(ValueError):replace(value,**change).validate()

    def test_eligibility_respects_installed_pack_and_legacy_location_limits(self):
        local=Settings(theme='stream')
        a=dict(eligible_options(local,False));b=dict(eligible_options(local,True))
        self.assertEqual(len(b)-len(a),45)
        self.assertIn('stream',a);self.assertIn('otava',a)
        south=dict(eligible_options(replace(local,latitude=-33),False))
        self.assertNotIn('otava',south);self.assertNotIn('hiillos',south)
        self.assertIn('moon',south);self.assertIn('rose_garden',south)

    def test_random_choice_never_repeats_current_or_escapes_selected_set(self):
        options=eligible_options(Settings(theme='stream'),True)
        rng=random.Random(77)
        for _ in range(40):
            self.assertEqual(choose_next(options,'stream',['stream','lighthouse'],rng),'lighthouse')
        self.assertIsNone(choose_next(options,'stream',['stream'],rng))
        self.assertIsNone(choose_next(eligible_options(Settings(),False),'stream',['ubuntu:26.10'],rng))

    def test_engine_switches_photo_and_moving_scenes_with_one_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='stream'),640,360);spin_until(lambda:not engine.busy)
                for theme in ('otava','rose_garden','lighthouse'):
                    engine.set_background(theme);spin_until(lambda:not engine.busy)
                    self.assertEqual(engine.settings.theme,theme)
                    if theme=='otava':self.assertIsNone(engine.motion_entry)
                    else:self.assertEqual(engine.motion_entry.settings.theme,theme)
                self.assertEqual(adapter.captures,1)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_background_switch_waits_for_worker_and_latest_choice_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();adapter.block=True
            engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='stream'),640,360);spin_until(adapter.started.is_set)
                engine.set_background('rose_garden');engine.set_background('lighthouse')
                self.assertEqual(engine.settings.theme,'stream')
                adapter.release.set();spin_until(lambda:not engine.busy and engine.pending_background is None)
                self.assertEqual(engine.settings.theme,'lighthouse');self.assertEqual(adapter.captures,1)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                adapter.release.set()
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_restore_precedes_a_pending_random_change(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeBackend();adapter.block=True
            engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='stream'),640,360);spin_until(adapter.started.is_set)
                engine.set_background('rose_garden');engine.restore();adapter.release.set()
                spin_until(lambda:not engine.busy and not engine.pending_restore)
                self.assertEqual(adapter.calls,['apply','restore'])
                self.assertFalse(engine.running);self.assertEqual(adapter.current,'original')
            finally:
                adapter.release.set()
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_manual_random_when_stopped_only_changes_preview_and_saved_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(theme='stream',shuffle_choices=['rose_garden']),folder)
            window.preview_timer.stop();window.shuffle_timer.stop();window.engine.timer.stop()
            try:
                self.assertTrue(window.random_background())
                self.assertEqual(window.theme.currentData(),'rose_garden')
                self.assertEqual(Settings.load(Path(folder)/'settings.json').theme,'rose_garden')
                self.assertFalse(window.engine.running)
                self.assertFalse((Path(folder)/'wallpaper-backup.json').exists())
                self.assertFalse(window.random_background())
            finally:window.allow_quit=True;window.close()

    def test_running_auto_shuffle_uses_selected_themes_and_stops_with_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            value=Settings(theme='stream',shuffle_enabled=True,shuffle_interval=60,
                           shuffle_choices=['stream','rose_garden'])
            # The GUI scheduler test must not enter a real WorkerW surface in
            # offscreen Windows. Native drawing has its own Windows smoke job.
            window=Window(value,folder);adapter=FakeBackend()
            window.engine.adapter_factory=lambda:adapter
            window.preview_timer.stop();window.shuffle_timer.stop();window.engine.timer.stop()
            try:
                with patch('veriyo_live.app.set_autostart'):window.start()
                spin_until(lambda:not window.engine.busy)
                self.assertTrue(window.engine.running)
                window.shuffle_due=0;window.shuffle_tick();spin_until(lambda:not window.engine.busy)
                self.assertEqual(window.theme.currentData(),'rose_garden')
                self.assertEqual(window.engine.settings.theme,'rose_garden')
                saved=Settings.load(Path(folder)/'settings.json')
                self.assertTrue(saved.shuffle_enabled);self.assertEqual(saved.shuffle_choices,value.shuffle_choices)
                window.engine.stop();spin_until(lambda:not window.engine.busy)
                window.shuffle_tick();self.assertIsNone(window.shuffle_due)
                window.engine.restore();spin_until(lambda:not window.engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if window.engine.busy:spin_until(lambda:not window.engine.busy)
                window.allow_quit=True;window.close()

    def test_selection_dialog_persists_only_the_checked_backgrounds(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(theme='stream'),folder)
            window.preview_timer.stop();window.shuffle_timer.stop();window.engine.timer.stop()
            def select(dialog):
                listing=dialog.findChild(QListWidget)
                for i in range(listing.count()):
                    item=listing.item(i)
                    item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in ('stream','lighthouse')
                                       else Qt.CheckState.Unchecked)
                return QDialog.DialogCode.Accepted
            try:
                with patch.object(QDialog,'exec',select):window.choose_shuffle_backgrounds()
                self.assertEqual(Settings.load(Path(folder)/'settings.json').shuffle_choices,['stream','lighthouse'])
            finally:window.allow_quit=True;window.close()
