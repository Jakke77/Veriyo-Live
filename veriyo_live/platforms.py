"""Native per-user wallpaper adapters; no elevation or lock/security changes."""
import ast
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .settings import atomic_json


class LockScreenError(RuntimeError):
    """A refused/failed optional Windows lock image, separate from desktop errors."""
    def __init__(self, code='failed'):
        self.unchanged = code in {'unsupported', 'rejected', 'backup'}
        messages = {
            'unsupported': 'Windows ei salli lukituskuvan automaattista vaihtamista.',
            'rejected': 'Windows ei hyväksynyt lukituskuvaa.',
            'backup': 'Nykyistä lukituskuvaa ei voitu varmuuskopioida; sitä ei muuteta.',
        }
        super().__init__(messages.get(code, 'Windowsin lukituskuvatoiminto ei onnistunut.'))


def lock_warning(error):
    return (str(error) + ' Lukituskuvan automaattinen päivitys on keskeytetty; '
            'työpöytätausta toimii edelleen. Voit valita kuvan itse: Tallenna kuva… → '
            'Windowsin Asetukset → Mukauttaminen → Lukitusnäyttö → Kuva.')


def run(arguments, timeout=20):
    result = subprocess.run(arguments, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=timeout,
                            creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Järjestelmä ei hyväksynyt taustakuvaa.')
    return result.stdout.strip()


class GnomeBackend:
    kind = 'gnome'
    desktop = 'org.gnome.desktop.background'
    saver = 'org.gnome.desktop.screensaver'

    def __init__(self):
        if not shutil.which('gsettings') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            raise RuntimeError('Elävä työpöytä tarvitsee kirjautuneen GNOME-istunnon. Esikatselu ja kuvan tallennus toimivat silti.')
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if desktop and 'gnome' not in desktop and 'ubuntu' not in desktop:
            raise RuntimeError('Tämä versio vaihtaa taustakuvan GNOME-työpöydällä. Voit tallentaa kuvan ja käyttää sitä muilla työpöydillä.')

    def get(self, schema, key):
        return run(['gsettings', 'get', schema, key])

    def set(self, schema, key, value):
        run(['gsettings', 'set', schema, key, value])
        if ast.literal_eval(self.get(schema, key)) != ast.literal_eval(value):
            raise RuntimeError('GNOME ei tallentanut taustakuva-asetusta: ' + key)

    def capture(self, lock_screen, directory):
        records = []
        for schema, required in ((self.desktop, ('picture-uri', 'picture-options')),):
            keys = run(['gsettings', 'list-keys', schema]).splitlines()
            for key in (*required, 'picture-uri-dark'):
                if key == 'picture-uri-dark' and key not in keys:
                    continue
                if run(['gsettings', 'writable', schema, key]) != 'true':
                    raise RuntimeError('Työpöydän taustakuva on lukittu järjestelmän asetuksissa.')
                records.append({'schema': schema, 'key': key, 'value': self.get(schema, key)})
        if lock_screen:
            keys = run(['gsettings', 'list-keys', self.saver]).splitlines()
            if 'picture-uri' not in keys:
                raise RuntimeError('Tämä GNOME-versio ei tarjoa erillistä lukituskuva-asetusta. Poista erillisen lukituskuvan valinta.')
            if run(['gsettings', 'writable', self.saver, 'picture-uri']) != 'true':
                raise RuntimeError('Lukituskuvan asetus on järjestelmän hallitsema.')
            records.append({'schema': self.saver, 'key': 'picture-uri', 'value': self.get(self.saver, 'picture-uri')})
        return {'kind': self.kind, 'original': records, 'frames': []}

    def apply(self, path, lock_screen, journal):
        self.apply_paths(path, path, journal)

    def apply_paths(self, desktop_path, lock_path, journal):
        for record in journal['original']:
            path=lock_path if record['schema']==self.saver else desktop_path
            uri=json.dumps(Path(path).resolve().as_uri())
            value = "'zoom'" if record['key'] == 'picture-options' else uri
            self.set(record['schema'], record['key'], value)

    def can_resume(self, journal):
        frames = [Path(p).resolve().as_uri() for p in journal['frames']]
        for record in journal['original']:
            if record['key'] == 'picture-options':
                continue
            current = ast.literal_eval(self.get(record['schema'], record['key']))
            if current not in frames and current != ast.literal_eval(record['value']):
                return False
        return True

    def restore(self, journal):
        frames = [Path(p).resolve().as_uri() for p in journal['frames']]
        desktop_owned = all(
            ast.literal_eval(self.get(record['schema'], record['key'])) in
            [*frames, ast.literal_eval(record['value'])]
            for record in journal['original']
            if record['schema'] == self.desktop and record['key'] != 'picture-options')
        for record in journal['original']:
            if (record.get('schema'), record.get('key')) not in {
                (self.desktop, 'picture-uri'), (self.desktop, 'picture-uri-dark'),
                (self.desktop, 'picture-options'), (self.saver, 'picture-uri')}:
                raise RuntimeError('Varmuuskopio sisältää tuntemattoman asetuksen.')
            current = self.get(record['schema'], record['key'])
            # A user-selected different picture made while we ran takes precedence.
            if record['key'] == 'picture-options':
                owned = desktop_owned and current == "'zoom'"
            else:
                try:
                    owned = ast.literal_eval(current) in [Path(p).resolve().as_uri() for p in journal['frames']]
                except (SyntaxError, ValueError):
                    owned = False
            if owned:
                self.set(record['schema'], record['key'], record['value'])


class WindowsBackend:
    kind = 'windows'

    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Windowsin taustakuvasovitin on käytettävissä vain Windowsissa.')
        from ctypes import wintypes
        self.spi = ctypes.WinDLL('user32', use_last_error=True).SystemParametersInfoW
        self.spi.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        self.spi.restype = wintypes.BOOL

    def desktop_path(self):
        buffer = ctypes.create_unicode_buffer(32768)
        if not self.spi(0x0073, len(buffer), buffer, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value

    def set_desktop(self, path):
        value = ctypes.create_unicode_buffer(str(path))
        if not self.spi(0x0014, 0, value, 3):
            raise ctypes.WinError(ctypes.get_last_error())

    def lock(self, operation, path):
        helper = Path(__file__).resolve().parent / 'lock-screen.ps1'
        try:
            return run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                        '-File', str(helper), '-Operation', operation, '-ImagePath', str(path)], timeout=30)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            # Display our bounded diagnostic, never a PowerShell stack/path dump.
            code = next((code for code in ('unsupported', 'rejected', 'backup')
                         if 'VERIYO_LOCK:' + code in str(error)), 'failed')
            raise LockScreenError(code) from error

    def capture(self, lock_screen, directory):
        result = {'kind': self.kind, 'desktop': self.desktop_path(), 'lock_backup': '',
                  'lock_restore_needed': False, 'frames': []}
        if lock_screen:
            backup = Path(directory) / 'previous-lock.jpg'
            # Refuse to change a lock screen which cannot be backed up.
            try:
                self.lock('Backup', backup)
                if not backup.is_file():
                    raise LockScreenError('backup')
                result['lock_backup'] = str(backup)
            except LockScreenError:
                result['lock_disabled'] = True
                result['lock_warning'] = lock_warning(LockScreenError('backup'))
        return result

    def apply(self, path, lock_screen, journal):
        self.set_desktop(path)
        if lock_screen:
            self.lock('Set', path)

    def can_resume(self, journal):
        paths = [*journal['frames'], journal['desktop']]
        return os.path.normcase(str(Path(self.desktop_path()).resolve())) in [
            os.path.normcase(str(Path(p).resolve())) for p in paths]

    def restore(self, journal):
        current = os.path.normcase(str(Path(self.desktop_path()).resolve()))
        owned = [os.path.normcase(str(Path(p).resolve())) for p in journal['frames']]
        if current in owned:
            self.set_desktop(journal['desktop'])
        if journal.get('lock_backup') and journal.get('lock_restore_needed', True):
            self.lock('Set', journal['lock_backup'])


def backend():
    return WindowsBackend() if os.name == 'nt' else GnomeBackend()


class WallpaperSession:
    """Durable backup before any mutation; survives app failure or a moved ZIP."""
    def __init__(self, directory, adapter):
        self.directory = Path(directory)
        self.path = self.directory / 'wallpaper-backup.json'
        self.adapter = adapter
        self.warning = ''

    def begin(self, lock_screen):
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if value['kind'] != self.adapter.kind:
                raise RuntimeError('Palauta aiempi tausta ennen lukituskuvavalinnan muuttamista.')
            if value['lock_screen'] != lock_screen:
                # Let a Windows user turn off an optional failed lock update,
                # including recovery from 0.2.0. Keep the original backup intact.
                if self.adapter.kind != 'windows' or lock_screen:
                    raise RuntimeError('Palauta aiempi tausta ennen lukituskuvavalinnan muuttamista.')
                value['lock_screen'] = False
            if not self.adapter.can_resume(value):
                raise RuntimeError('Taustakuva on vaihtunut toisessa ohjelmassa. Paina ensin Palauta aiempi tausta; muualla valittu työpöytäkuva säilytetään.')
            atomic_json(self.path, value)
            self.warning = value.get('lock_warning', '') if lock_screen else ''
            return  # Resume across login/restart without replacing the original backup.
        self.directory.mkdir(parents=True, exist_ok=True)
        value = self.adapter.capture(lock_screen, self.directory)
        value['lock_screen'] = lock_screen
        atomic_json(self.path, value)
        self.warning = value.get('lock_warning', '')

    def apply(self, path, lock_screen):
        value = json.loads(self.path.read_text(encoding='utf-8'))
        frame = str(Path(path).resolve())
        if frame not in value['frames']:
            value['frames'].append(frame)
        # Register intended frame before either desktop/lock changes. Recovery can
        # recognise both the old frame and a partially applied next frame.
        windows_lock = self.adapter.kind == 'windows' and lock_screen and not value.get('lock_disabled')
        previous_restore = value.get('lock_restore_needed', bool(value.get('lock_backup')))
        if windows_lock:
            # A process crash during WinRT must still leave a restorable backup.
            value['lock_restore_needed'] = True
        atomic_json(self.path, value)
        try:
            self.adapter.apply(frame, lock_screen and not value.get('lock_disabled'), value)
        except LockScreenError as error:
            if self.adapter.kind != 'windows':
                raise
            # The desktop was applied; a refused optional lock image must not
            # stop the live actor or cause repeated lock attempts on every tick.
            value['lock_disabled'] = True
            value['lock_warning'] = self.warning = lock_warning(error)
            if error.unchanged:
                value['lock_restore_needed'] = previous_restore
            atomic_json(self.path, value)

    def apply_paths(self, desktop_path, lock_path):
        value=json.loads(self.path.read_text(encoding='utf-8'))
        for path in (desktop_path,lock_path):
            frame=str(Path(path).resolve())
            if frame not in value['frames']:value['frames'].append(frame)
        atomic_json(self.path,value)
        self.adapter.apply_paths(desktop_path,lock_path,value)

    def can_resume(self):
        value=json.loads(self.path.read_text(encoding='utf-8'))
        return self.adapter.can_resume(value)

    def restore(self):
        self.warning = ''
        if not self.path.exists():
            return
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if value['kind'] != self.adapter.kind:
            raise RuntimeError('Varmuuskopio kuuluu toiselle käyttöjärjestelmälle.')
        try:
            self.adapter.restore(value)
        except LockScreenError as error:
            if self.adapter.kind != 'windows':
                raise
            self.warning = (str(error) + ' Aiemman lukituskuvan varmuuskopio säilytetään. '
                            'Valitse lukituskuva Windowsin omista mukautusasetuksista; '
                            'palautusta voi yrittää myöhemmin uudelleen.')
            return  # The desktop is restored, but lock recovery is still pending.
        self.path.unlink()  # A failed restoration deliberately retains recovery data.


def startup_command(root):
    root = Path(root).resolve()
    if os.name == 'nt':
        executable = root / 'Veriyo-Live.exe'
        return [str(executable), '--background'] if executable.is_file() else [sys.executable, str(root/'main.py'), '--background']
    launcher = Path('/usr/bin/veriyo-live')
    if launcher.exists() and root == Path('/usr/share/veriyo-live'):
        return [str(launcher), '--background']
    return [sys.executable, str(root/'main.py'), '--background']


def set_autostart(enabled, root):
    command = startup_command(root)
    if os.name == 'nt':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                winreg.SetValueEx(key, 'VeriyoLive', 0, winreg.REG_SZ, subprocess.list2cmdline(command))
            else:
                try:
                    winreg.DeleteValue(key, 'VeriyoLive')
                except FileNotFoundError:
                    pass
        return
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    target = config / 'autostart/veriyo-live.desktop'
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Desktop Entry quoting is separate from shell quoting; no shell executes it.
        def quote(value):
            return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
        content = ('[Desktop Entry]\nType=Application\nName=Veriyö Live\nExec=' +
                   ' '.join(quote(p) for p in command) + '\nTerminal=false\nX-GNOME-Autostart-enabled=true\n')
        temporary = target.with_suffix('.tmp')
        temporary.write_text(content, encoding='utf-8')
        os.replace(temporary, target)
    else:
        target.unlink(missing_ok=True)
