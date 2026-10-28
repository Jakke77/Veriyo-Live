"""Rejected optional lock images must not stop desktop updates or lose recovery."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from veriyo_live.engine import Engine
from veriyo_live.platforms import LockScreenError, WallpaperSession, WindowsBackend
from veriyo_live.settings import Settings, atomic_json
from test_live import spin_until


class FakeWindowsBackend(WindowsBackend):
    """Use the real adapter/session logic with only native API calls replaced."""
    def __init__(self):
        self.current = 'original-desktop'
        self.lock_image = b'original-lock'
        self.lock_error = None
        self.backup_error = False
        self.desktop_error = False
        self.lock_calls = []

    def desktop_path(self):
        return self.current

    def set_desktop(self, path):
        if self.desktop_error:
            raise RuntimeError('Desktop write denied')
        self.current = str(path)

    def lock(self, operation, path):
        self.lock_calls.append(operation)
        if operation == 'Backup':
            if self.backup_error:
                raise LockScreenError('backup')
            Path(path).write_bytes(self.lock_image)
        elif self.lock_error:
            raise LockScreenError(self.lock_error)
        else:
            self.lock_image = Path(path).read_bytes()


class WindowsLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.adapter = FakeWindowsBackend()
        self.session = WallpaperSession(self.directory, self.adapter)
        self.frame = self.directory / 'frame.jpg'
        self.frame.write_bytes(b'new-image')

    def tearDown(self):
        self.temp.cleanup()

    def journal(self):
        return json.loads(self.session.path.read_text(encoding='utf-8'))

    def test_rejection_keeps_desktop_running_without_repeated_lock_attempts(self):
        self.adapter.lock_error = 'rejected'
        engine = Engine(self.directory, adapter_factory=lambda: self.adapter)
        engine.timer.stop()
        messages = []
        engine.status.connect(messages.append)
        try:
            engine.start(Settings(lock_screen=True), 640, 360)
            spin_until(lambda: not engine.busy)
            self.assertTrue(engine.running)
            self.assertIn('Windows ei hyväksynyt', messages[-1])
            self.assertIn('työpöytätausta toimii edelleen', messages[-1])
            self.assertNotIn('Toiminto ei onnistunut', messages[-1])
            engine.last_update -= 61
            engine.last_wall_time -= 61
            engine.tick()
            spin_until(lambda: not engine.busy)
            self.assertTrue(engine.running)
            self.assertEqual(self.adapter.lock_calls, ['Backup', 'Set'])
            self.assertEqual(self.adapter.lock_image, b'original-lock')
            self.assertFalse(self.journal()['lock_restore_needed'])
            engine.restore()
            spin_until(lambda: not engine.busy)
            self.assertEqual(self.adapter.current, 'original-desktop')
            self.assertEqual(self.adapter.lock_calls, ['Backup', 'Set'])
            self.assertFalse(self.session.path.exists())
        finally:
            if engine.busy:
                spin_until(lambda: not engine.busy)
            engine.deleteLater()

    def test_failed_backup_allows_desktop_but_never_sets_lock_image(self):
        self.adapter.backup_error = True
        self.session.begin(True)
        self.session.apply(self.frame, True)
        self.assertEqual(self.adapter.current, str(self.frame.resolve()))
        self.assertEqual(self.adapter.lock_calls, ['Backup'])
        self.assertEqual(self.adapter.lock_image, b'original-lock')
        self.assertIn('varmuuskopioida', self.session.warning)
        self.session.restore()
        self.assertEqual(self.adapter.current, 'original-desktop')
        self.assertFalse(self.session.path.exists())

    def test_previous_success_is_still_restored_after_later_rejection_and_restart(self):
        self.session.begin(True)
        self.session.apply(self.frame, True)
        self.assertEqual(self.adapter.lock_image, b'new-image')
        self.adapter.lock_error = 'rejected'
        self.session.apply(self.frame, True)
        self.assertTrue(self.journal()['lock_restore_needed'])
        restarted = WallpaperSession(self.directory, self.adapter)
        restarted.begin(True)
        restarted.apply(self.frame, True)
        self.assertEqual(self.adapter.lock_calls, ['Backup', 'Set', 'Set'])
        self.assertTrue(restarted.warning)
        self.adapter.lock_error = None
        restarted.restore()
        self.assertEqual(self.adapter.current, 'original-desktop')
        self.assertEqual(self.adapter.lock_image, b'original-lock')
        self.assertFalse(restarted.path.exists())

    def test_failed_lock_restore_preserves_backup_and_can_be_retried(self):
        self.session.begin(True)
        self.session.apply(self.frame, True)
        self.adapter.lock_error = 'rejected'
        self.session.restore()
        self.assertEqual(self.adapter.current, 'original-desktop')
        self.assertTrue(self.session.path.exists())
        self.assertEqual(Path(self.journal()['lock_backup']).read_bytes(), b'original-lock')
        self.assertIn('varmuuskopio säilytetään', self.session.warning)
        self.adapter.lock_error = None
        self.session.restore()
        self.assertFalse(self.session.path.exists())
        self.assertEqual(self.adapter.lock_image, b'original-lock')
        self.assertEqual(self.session.warning, '')

    def test_disable_lock_after_020_failure_preserves_original_backup(self):
        backup = self.directory / 'previous-lock.jpg'
        backup.write_bytes(b'original-lock')
        self.adapter.current = str(self.frame.resolve())
        # 0.2.0 journals have none of the new optional lock state fields.
        atomic_json(self.session.path, {'kind': 'windows', 'lock_screen': True,
                    'desktop': 'original-desktop', 'lock_backup': str(backup),
                    'frames': [self.adapter.current]})
        self.session.begin(False)
        self.session.apply(self.frame, False)
        self.assertEqual(self.adapter.lock_calls, [])
        self.assertEqual(self.journal()['lock_backup'], str(backup))
        self.assertFalse(self.journal()['lock_screen'])
        self.session.restore()
        self.assertEqual(self.adapter.current, 'original-desktop')
        self.assertEqual(self.adapter.lock_calls, ['Set'])
        self.assertFalse(self.session.path.exists())

    def test_unknown_set_failure_retains_recovery_for_possible_partial_change(self):
        self.session.begin(True)
        self.adapter.lock_error = 'failed'
        self.session.apply(self.frame, True)
        self.assertTrue(self.journal()['lock_restore_needed'])
        self.assertTrue(self.journal()['lock_disabled'])
        self.adapter.lock_error = None
        self.session.restore()
        self.assertEqual(self.adapter.lock_calls, ['Backup', 'Set', 'Set'])

    def test_journal_registers_lock_recovery_before_native_mutation(self):
        self.session.begin(True)
        original_lock = self.adapter.lock
        def checked_lock(operation, path):
            if operation == 'Set':
                self.assertTrue(self.journal()['lock_restore_needed'])
                self.assertIn(str(self.frame.resolve()), self.journal()['frames'])
            return original_lock(operation, path)
        self.adapter.lock = checked_lock
        self.session.apply(self.frame, True)

    def test_desktop_errors_are_not_suppressed_as_optional_lock_failures(self):
        self.session.begin(True)
        self.adapter.desktop_error = True
        with self.assertRaisesRegex(RuntimeError, 'Desktop write denied'):
            self.session.apply(self.frame, True)
        self.assertTrue(self.session.path.exists())
        self.assertEqual(self.adapter.lock_calls, ['Backup'])

    def test_helper_diagnostics_are_bounded_without_powershell_trace_or_personal_path(self):
        adapter = object.__new__(WindowsBackend)
        for code in ('rejected', 'unsupported', 'failed'):
            with self.subTest(code=code):
                with patch('veriyo_live.platforms.run', side_effect=RuntimeError(
                        'VERIYO_LOCK:' + code + '\nAt C:/Users/Personal/lock-screen.ps1:35')):
                    with self.assertRaises(LockScreenError) as caught:
                        adapter.lock('Set', self.frame)
                self.assertNotIn('Personal', str(caught.exception))
                self.assertNotIn('ps1', str(caught.exception))
                self.assertEqual(caught.exception.unchanged, code != 'failed')
        with patch('veriyo_live.platforms.run', side_effect=subprocess.TimeoutExpired('powershell', 30)):
            with self.assertRaises(LockScreenError) as caught:
                adapter.lock('Set', self.frame)
        self.assertFalse(caught.exception.unchanged)

    @unittest.skipUnless(os.name == 'nt', 'Needs Windows PowerShell and WinRT')
    def test_native_helper_missing_file_fails_cleanly_before_any_lock_image_change(self):
        # StorageFile cannot resolve this nonexistent path, so the native helper
        # must fail before reaching TrySetLockScreenImageAsync. No settings change.
        missing = self.directory / 'never-created.jpg'
        self.assertFalse(missing.exists())
        adapter = object.__new__(WindowsBackend)
        with self.assertRaises(LockScreenError) as caught:
            adapter.lock('Set', missing)
        self.assertNotIn(str(missing), str(caught.exception))
        self.assertNotIn('ps1', str(caught.exception))
