"""One worker at a time: stop waits for a pending update before restoration."""
from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from .platforms import WallpaperSession, backend
from .render import render


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

    def stop(self):
        self.running = False
        self.stop_requested = True
        self.status.emit('Pysäytetään päivitys. Viimeinen kuva jää taustaksi.')
        self.changed.emit()

    def restore(self):
        self.running = False
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
            self.status.emit('Toiminto ei onnistunut: ' + error + ' Varmuuskopio säilytetään palautusta varten.')
        elif operation == 'restore':
            self.status.emit('Aiempi tausta palautettu. Muualla valitsemaasi uutta työpöytäkuvaa ei korvata.')
        elif self.running:
            self.status.emit(f'Elävä tausta käytössä · päivitys {self.settings.interval // 60} min välein')
        elif self.stop_requested:
            self.status.emit('Päivitys pysäytetty. Viimeinen kuva jää taustaksi.')
        self.changed.emit()
        if self.pending_restore:
            self._restore_now()
        elif self.running and self.pending_date_mode is not None:
            self._refresh_date_mode()
