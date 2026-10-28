"""One worker at a time: stop waits for a pending update before restoration."""
from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from .platforms import WallpaperSession, backend
from .render import render
from .ubuntu_pack import PackLibrary, render_motion, write_gnome_slideshow
from .scenes import SCENES, SceneEntry, build_slideshow, render_entry


class Task(QThread):
    result = pyqtSignal(str, str)

    def __init__(self, operation, function, parent=None):
        super().__init__(parent)
        self.operation, self.function = operation, function
        self.error = ''

    def run(self):
        try:
            self.function()
        except Exception as error:
            self.error = str(error)


class Engine(QObject):
    status = pyqtSignal(str)
    changed = pyqtSignal()

    def __init__(self, directory, parent=None, adapter_factory=None):
        super().__init__(parent)
        self.directory = Path(directory)
        self.adapter_factory = adapter_factory or backend
        self.session = None
        self.running = False
        self.worker = None
        self.pending_restore = False
        self.stop_requested = False
        self.last_update = 0
        self.last_wall_time = 0
        self.slot = 0
        self.settings = None
        self.pending_date_mode = None
        self.pending_ubuntu_version = None
        self.motion_entry = None
        self.pending_freeze = False
        self.library = PackLibrary(directory)
        self.size = (1920, 1080)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    @property
    def busy(self):
        return self.worker is not None

    def _launch(self, operation, function):
        if self.worker is not None:
            raise RuntimeError('Edellinen taustakuvan päivitys on vielä kesken.')
        self.worker = Task(operation, function, self)
        self.worker.finished.connect(self._finished)
        self.changed.emit()
        self.worker.start()

    def start(self, settings, width, height):
        if self.running or self.busy:
            return
        self.settings = replace(settings).validate()
        self.pending_date_mode = None
        self.pending_ubuntu_version = None
        self.motion_entry = None
        self.pending_freeze = False
        self.size = (width, height)
        self.session = WallpaperSession(self.directory, self.adapter_factory())
        self.stop_requested = False
        self.running = True
        self.status.emit('Valmistellaan elävää taustaa…')

        def begin():
            self.session.begin(self.settings.lock_screen)
            self._update()
        self._launch('start', begin)

    def _update(self):
        if self.settings.theme in SCENES:
            moment = datetime.now(timezone.utc)
            self.slot = 1-self.slot
            self.directory.mkdir(parents=True, exist_ok=True)
            if self.session.adapter.kind == 'gnome':
                entry, path = build_slideshow(moment, self.settings, *self.size, self.directory, self.slot)
                self.session.apply_paths(path, entry.frames[0])
            else:
                path = self.directory/f'scene-poster-{self.slot}.jpg'
                temporary = self.directory/f'.scene-poster-{self.slot}.jpg'
                if not render(moment, self.settings, *self.size).save(str(temporary), 'JPEG', 94):
                    raise RuntimeError('Taivasteeman pysäytyskuvan tallennus epäonnistui.')
                os.replace(temporary, path)
                self.session.apply(path, self.settings.lock_screen)
                # Keep a stable native actor on periodic lock/poster updates.
                entry = SceneEntry(replace(self.settings))
                if self.motion_entry == entry:
                    entry = self.motion_entry
            self.motion_entry = entry
            self.last_update = time.monotonic()
            self.last_wall_time = moment.timestamp()
            return
        if self.settings.theme=='ubuntu':
            entry=self.library.entry(self.settings.ubuntu_version)
            if self.session.adapter.kind=='gnome':
                path=write_gnome_slideshow(entry,self.directory/f'live-ubuntu-{entry.version}.xml')
                self.session.apply_paths(path,entry.frames[0])
            else:
                self.session.apply(entry.frames[0],self.settings.lock_screen)
            self.motion_entry=entry
            return
        moment = datetime.now(timezone.utc)
        self.slot = 1 - self.slot
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f'frame-{self.slot}.jpg'
        temporary = self.directory / f'.frame-{self.slot}.jpg'
        image = render(moment, self.settings, *self.size)
        if not image.save(str(temporary), 'JPEG', 95):
            raise RuntimeError('Taustakuvan tallennus ei onnistunut.')
        os.replace(temporary, target)
        self.session.apply(target, self.settings.lock_screen)
        self.last_update = time.monotonic()
        self.last_wall_time = moment.timestamp()

    def tick(self):
        if not self.running or self.busy:
            return
        if self.settings.theme=='ubuntu':
            return  # GNOME or the native Windows desktop actor animates continuously.
        elapsed = time.monotonic() - self.last_update
        # A suspend or clock correction must not leave a stale star arrangement.
        wall_elapsed = time.time() - self.last_wall_time
        if elapsed >= self.settings.interval or wall_elapsed < 0 or abs(wall_elapsed - elapsed) > 5:
            self._launch('update', self._update)

    def set_date_mode(self, mode):
        if self.settings is None:
            return
        replace(self.settings, date_mode=mode).validate()
        self.pending_date_mode = mode
        if self.running and not self.busy:
            self._refresh_date_mode()

    def _refresh_date_mode(self):
        # Never mutate settings which a pending render/apply task is reading.
        self.settings = replace(self.settings, date_mode=self.pending_date_mode)
        self.pending_date_mode = None
        self._launch('update', self._update)

    def set_ubuntu_version(self,version):
        if self.settings is None or self.settings.theme!='ubuntu':return
        replace(self.settings,ubuntu_version=version).validate()
        self.pending_ubuntu_version=version
        if self.running and not self.busy:self._refresh_ubuntu_version()

    def _refresh_ubuntu_version(self):
        self.settings=replace(self.settings,ubuntu_version=self.pending_ubuntu_version)
        self.pending_ubuntu_version=None;self.motion_entry=None
        self._launch('update',self._update)

    def stop(self):
        freeze=self.running and self.settings is not None and (self.settings.theme=='ubuntu' or self.settings.theme in SCENES)
        self.running = False
        self.stop_requested = True
        if freeze:self.pending_freeze=True
        self.status.emit('Pysäytetään päivitys. Viimeinen kuva jää taustaksi.')
        self.changed.emit()
        if self.pending_freeze and not self.busy:self._freeze_now()

    def _freeze_now(self):
        self.pending_freeze=False
        if self.motion_entry is None:return
        def freeze():
            if self.session.can_resume():
                image=render_entry(self.motion_entry,time.time(),*self.size)
                name='ubuntu-paused' if self.settings.theme=='ubuntu' else 'scene-paused'
                path=self.directory/(name+'.jpg')
                temporary=self.directory/('.'+name+'.jpg')
                if not image.save(str(temporary),'JPEG',95):
                    raise RuntimeError('Pysäytyskuvan tallentaminen ei onnistunut.')
                os.replace(temporary,path)
                self.session.apply(path,self.settings.lock_screen)
            self.motion_entry=None
        self._launch('freeze',freeze)

    def restore(self):
        self.running = False
        self.pending_freeze = False
        self.pending_restore = True
        if not self.busy:
            self._restore_now()
        self.changed.emit()

    def _restore_now(self):
        self.pending_restore = False
        try:
            if self.session is None:
                self.session = WallpaperSession(self.directory, self.adapter_factory())
            self.status.emit('Palautetaan aiempi taustakuva…')
            self._launch('restore', self.session.restore)
        except Exception as error:
            self.status.emit(str(error))
            self.changed.emit()

    def _finished(self):
        task = self.worker
        operation, error = task.operation, task.error
        self.worker = None
        task.deleteLater()
        if error:
            self.running = False
            self.pending_freeze = False
            self.status.emit('Toiminto ei onnistunut: ' + error + ' Varmuuskopio säilytetään palautusta varten.')
        elif operation == 'restore':
            if self.session.warning:
                self.status.emit('Työpöytätaustan palautus valmis. ' + self.session.warning)
            else:
                self.status.emit('Aiempi tausta palautettu. Muualla valitsemaasi uutta työpöytäkuvaa ei korvata.')
        elif self.running:
            if self.settings.theme=='ubuntu':
                message = f'Ubuntu {self.settings.ubuntu_version} · taustakuvakokoelma käytössä · animaatiota ei luvata'
            elif self.settings.theme in SCENES:
                message = SCENES[self.settings.theme][0] + ' · liikkuva tausta käytössä'
            else:
                message = f'Elävä tausta käytössä · päivitys {self.settings.interval // 60} min välein'
            if self.session.warning:
                message += '\n' + self.session.warning
            self.status.emit(message)
        elif self.stop_requested:
            self.status.emit('Päivitys pysäytetty. Viimeinen kuva jää taustaksi.')
        self.changed.emit()
        if self.pending_restore:
            self._restore_now()
        elif self.pending_freeze:
            self._freeze_now()
        elif self.running and self.pending_ubuntu_version is not None:
            self._refresh_ubuntu_version()
        elif self.running and self.pending_date_mode is not None:
            self._refresh_date_mode()
