"""Finnish standalone GUI, tray, CLI export, and explicitly enabled background engine."""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from PyQt6.QtCore import QLockFile, QTimer, Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget)
from . import VERSION
from .calendar import ZONE
from .engine import Engine
from .platforms import set_autostart
from .render import ASSETS, render
from .settings import Settings, data_dir

STYLE = '''
QWidget { background: #0d080d; color: #f5eaf0; font-size: 13px; }
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget { background: #070508; }
QLabel#title { color: #f0788b; font-size: 27px; font-weight: 700; }
QLabel#subtitle, QLabel#hint { color: #c8a8b3; }
QPushButton, QComboBox, QDoubleSpinBox { background: #24131c; border: 1px solid #56303c;
 border-radius: 6px; padding: 8px; min-height: 18px; }
QPushButton:hover { background: #42212f; }
QPushButton:disabled { color: #78646e; border-color: #30232a; }
QPushButton#primary { background: #92344d; color: #ffffff; font-weight: 600; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #8a596a; border-radius: 3px; background: #24131c; }
QCheckBox::indicator:checked { background: #c55873; }
QSlider::groove:horizontal { height: 4px; background: #56303c; }
QSlider::handle:horizontal { background: #f0788b; width: 15px; margin: -6px 0; border-radius: 7px; }
QToolTip { background: #24131c; color: #f5eaf0; border: 1px solid #92344d; }
'''


class Preview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.setMinimumSize(320, 180)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName('Otavan todellisen asennon esikatselu pohjoiseen katsottaessa')

    def update_image(self, frame):
        self.frame = frame
        self._scale()

    def _scale(self):
        if self.frame is not None:
            self.setPixmap(QPixmap.fromImage(self.frame).scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                              Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        self._scale()
        super().resizeEvent(event)


class Window(QMainWindow):
    def __init__(self, settings, directory):
        super().__init__()
        self.settings, self.directory = settings, Path(directory)
        self.engine = Engine(directory, self)
        self.engine.status.connect(self.show_status)
        self.engine.changed.connect(self.update_controls)
        self.setWindowTitle(f'Veriyö Live {VERSION}')
        self.setWindowIcon(QIcon(str(ASSETS/'icon.svg')))
        self.resize(1280, 860)
        self.preview = Preview()
        self.status = QLabel('Esikatselu · työpöydän asetuksia ei ole muutettu.')
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Taustakuvan tila')
        self.allow_quit = False
        self.demo_start = None
        self.backgrounds = {}
        self.last_preview_second = None
        self.tray = None
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(12)
        title = QLabel('VERIYÖ LIVE')
        title.setObjectName('title')
        outer.addWidget(title)
        subtitle = QLabel('Oma yötaivas. Otavan oikea liike. Veri Ajan 777 päivän vuosi.')
        subtitle.setObjectName('subtitle')
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        outer.addWidget(self.preview, 1)
        time_row = QHBoxLayout()
        self.demo = QCheckBox('Nopeutettu esikatselu · vuorokausi minuutissa')
        self.demo.setToolTip('Vaikuttaa vain esikatseluun. Työpöytä ja tallennettu kuva käyttävät aina oikeaa aikaa.')
        self.demo.toggled.connect(self.toggle_demo)
        time_row.addWidget(self.demo)
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        time_row.addWidget(self.time_label)
        outer.addLayout(time_row)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.theme = QComboBox()
        self.theme.addItem('Veriyö · Otava ja järvi', 'otava')
        self.theme.addItem('Veriyö · Hiillos', 'hiillos')
        self.theme.setCurrentIndex(0 if settings.theme == 'otava' else 1)
        self.theme.currentIndexChanged.connect(self.refresh_preview)
        form.addRow('Taustakuvan tyyli', self.theme)
        location = QHBoxLayout()
        self.latitude, self.longitude = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, minimum, maximum, value, label in (
            (self.latitude, 60, 70, settings.latitude, 'Leveysaste pohjoista'),
            (self.longitude, -180, 180, settings.longitude, 'Pituusaste itään')):
            spin.setRange(minimum, maximum)
            spin.setDecimals(6)
            spin.setValue(value)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(self.refresh_preview)
            location.addWidget(spin)
        form.addRow('Sijainti · leveys / pituus', location)
        flags = QHBoxLayout()
        self.guides = QCheckBox('Suunnat ja Alkaid')
        self.guides.setChecked(settings.guides)
        self.guides.toggled.connect(self.refresh_preview)
        flags.addWidget(self.guides)
        form.addRow('Kuvassa näkyy', flags)
        self.date_mode = QComboBox()
        for label, mode in (('Piilossa', 'none'), ('Veri Aika', 'blood'),
                            ('Tavallinen päivämäärä', 'gregorian'), ('Molemmat', 'both')):
            self.date_mode.addItem(label, mode)
        self.date_mode.setCurrentIndex(self.date_mode.findData(settings.date_mode))
        self.date_mode.setAccessibleName('Taustakuvan päivämäärä')
        self.date_mode.setToolTip('Valinta tallentuu ja päivittyy myös käynnissä olevaan taustaan. Piilossa poistaa kaikki päivämäärät taustakuvasta.')
        self.date_mode.currentIndexChanged.connect(self.change_date_mode)
        form.addRow('Päivämäärä', self.date_mode)
        advanced = QHBoxLayout()
        self.interval = QComboBox()
        for title, seconds in (('1 minuutti', 60), ('5 minuuttia', 300), ('26 minuuttia', 1560)):
            self.interval.addItem(title, seconds)
        self.interval.setCurrentIndex(self.interval.findData(settings.interval))
        self.lock = QCheckBox('Päivitä myös lukituskuvaa')
        self.lock.setChecked(settings.lock_screen)
        self.lock.setToolTip('Ajantasainen pysäytyskuva. Jo avoin lukitusnäyttö ei välttämättä virkisty. Windowsin Spotlight-/diaesitysvalinta palautetaan Windowsin asetuksista.')
        advanced.addWidget(self.interval)
        advanced.addWidget(self.lock)
        form.addRow('Päivitysväli', advanced)
        self.autostart = QCheckBox('Käynnistä elävä tausta kirjautuessani sisään')
        self.autostart.setChecked(settings.autostart)
        form.addRow('', self.autostart)
        outer.addWidget(form_widget)
        hint = QLabel('Pohjoiseen katsottu taivas: länsi vasemmalla, itä oikealla. Taivaannavan korkeus vastaa leveysastetta. '
            'Lukituskuva on pysäytyskuva; GNOME käyttää usein työpöydän kuvaa myös lukituksen pohjana. '
            'Tämä versio tekee saman kuvan kaikille näytöille päänäytön tarkkuudella.')
        hint.setWordWrap(True)
        hint.setObjectName('hint')
        outer.addWidget(hint)
        actions = QHBoxLayout()
        self.start_button = QPushButton('Ota elävä tausta käyttöön')
        self.start_button.setObjectName('primary')
        self.stop_button = QPushButton('Pysäytä päivitys')
        self.restore_button = QPushButton('Palauta aiempi tausta')
        self.export_button = QPushButton('Tallenna kuva…')
        for button, callback in ((self.start_button, self.start), (self.stop_button, self.engine.stop),
                                 (self.restore_button, self.engine.restore), (self.export_button, self.export)):
            button.clicked.connect(callback)
            actions.addWidget(button)
        outer.addLayout(actions)
        outer.addWidget(self.status)
        self.save_button = QPushButton('Tallenna asetukset')
        self.save_button.clicked.connect(self.save)
        outer.addWidget(self.save_button)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            menu = QMenu()
            for label, callback in (('Avaa Veriyö Live', self.open_window), ('Pysäytä päivitys', self.engine.stop),
                                    ('Palauta aiempi tausta', self.engine.restore), ('Lopeta (jätä viimeinen kuva)', self.quit)):
                menu.addAction(label, callback)
            self.tray.setContextMenu(menu)
            self.tray.setToolTip(f'Veriyö Live {VERSION}')
            self.tray.activated.connect(lambda reason: self.open_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray.show()
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(100)
        self.preview_timer.timeout.connect(self.preview_tick)
        self.preview_timer.start()
        self.refresh_preview()
        self.update_controls()

    def values(self):
        return Settings(theme=self.theme.currentData(), latitude=self.latitude.value(), longitude=self.longitude.value(),
                        guides=self.guides.isChecked(), date_mode=self.date_mode.currentData(), interval=self.interval.currentData(),
                        lock_screen=self.lock.isChecked(), autostart=self.autostart.isChecked()).validate()

    def change_date_mode(self, *args):
        try:
            value = replace(self.settings, date_mode=self.date_mode.currentData())
            value.save(self.directory/'settings.json')
            self.settings = value
            self.engine.set_date_mode(value.date_mode)
            self.refresh_preview()
            self.show_status('Päivämäärävalinta tallennettu. Taustakuva päivittyy, jos elävä tausta on käytössä.')
        except Exception as error:
            self.show_status(str(error))

    def show_status(self, value):
        self.status.setText(value)
        if self.tray:
            self.tray.setToolTip(('Veriyö Live · ' + value)[:120])
        if value.startswith('Toiminto ei onnistunut:'):
            self.open_window()

    def save(self):
        try:
            value = self.values()
            # Explicit save refreshes a moved Windows ZIP's own Run path, too.
            set_autostart(value.autostart, Path(__file__).resolve().parents[1])
            value.save(self.directory/'settings.json')
            self.settings = value
            self.show_status('Asetukset tallennettu. Käynnistysvalinta päivitetty tähän asennukseen.')
            return True
        except Exception as error:
            self.show_status(str(error))
            return False

    def start(self):
        if not self.save():
            self.open_window()
            return
        try:
            size = QApplication.primaryScreen().size()
            ratio = QApplication.primaryScreen().devicePixelRatio()
            width, height = round(size.width()*ratio), round(size.height()*ratio)
            factor = min(1, 7680/width, 4320/height)
            self.engine.start(self.settings, max(320, round(width*factor)), max(240, round(height*factor)))
        except Exception as error:
            self.show_status(str(error))
            self.open_window()
        self.update_controls()

    def update_controls(self):
        active = self.engine.running or self.engine.busy
        for widget in (self.theme, self.latitude, self.longitude, self.guides, self.interval, self.lock,
                       self.autostart, self.save_button):
            widget.setEnabled(not active)
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(self.engine.running)
        self.restore_button.setEnabled((self.directory/'wallpaper-backup.json').exists() and not self.engine.pending_restore)

    def toggle_demo(self, checked):
        import time
        self.demo_start = (time.monotonic(), datetime.now(timezone.utc)) if checked else None
        self.refresh_preview()

    def preview_tick(self):
        if not self.isVisible():
            return  # A hidden tray process only renders its scheduled wallpaper updates.
        now = datetime.now(timezone.utc)
        if self.demo_start is not None:
            import time
            now = self.demo_start[1] + timedelta(seconds=(time.monotonic()-self.demo_start[0])*1440)
        elif self.last_preview_second == int(now.timestamp()):
            return
        self.last_preview_second = int(now.timestamp())
        self.refresh_preview(moment=now)

    def refresh_preview(self, *args, moment=None):
        if not hasattr(self, 'autostart'):
            return
        try:
            value = self.values()
            if value.theme not in self.backgrounds:
                self.backgrounds[value.theme] = QImage(str(ASSETS/(value.theme+'.png')))
            moment = moment or datetime.now(timezone.utc)
            self.preview.update_image(render(moment, value, 1280, 720, self.backgrounds[value.theme]))
            local = moment.astimezone(ZONE)
            self.time_label.setText(('ESIKATSELU · ' if self.demo.isChecked() else '') + f'{local:%d.%m.%Y %H:%M:%S} {local.tzname()}')
        except Exception as error:
            self.show_status(str(error))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Tallenna tämän hetken taivas', 'veriyo-live.png', 'PNG-kuva (*.png)')
        if not path:
            return
        try:
            size = QApplication.primaryScreen().size()
            image = render(datetime.now(timezone.utc), self.values(), max(320, size.width()), max(240, size.height()))
            if not image.save(path, 'PNG'):
                raise RuntimeError('Kuvan tallennus ei onnistunut.')
            self.show_status('Tämän hetken taivas tallennettu: ' + path)
        except Exception as error:
            self.show_status(str(error))

    def open_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.allow_quit:
            event.accept()
        elif self.tray and (self.engine.running or self.engine.busy):
            self.hide()
            event.ignore()
        elif self.engine.busy:
            self.quit()
            event.ignore()
        else:
            QApplication.instance().quit()
            event.accept()

    def quit(self):
        self.engine.stop()
        if self.engine.busy:
            self.show_status('Odotetaan keskeneräisen päivityksen valmistumista…')
            QTimer.singleShot(100, self.quit)
            return
        self.allow_quit = True
        QApplication.instance().quit()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Veriyö Live — Otavan oikea asento ja Veri Aika')
    parser.add_argument('--version', action='version', version='Veriyö Live ' + VERSION)
    parser.add_argument('--background', action='store_true', help='Käynnistä tallennettu elävä tausta')
    parser.add_argument('--export', type=Path, help='Tallenna PNG muuttamatta työpöytää')
    parser.add_argument('--at', help='Aikavyöhykkeen sisältävä ISO-aika vientiin, esim. 2026-10-27T21:00:00+02:00')
    parser.add_argument('--size', default='1920x1080', help='Vientikuvan tarkkuus')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    app.setApplicationName('VeriyoLive')
    app.setApplicationVersion(VERSION)
    if args.self_test:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1]/'tests'), pattern='test_*.py')
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    directory = data_dir()
    try:
        settings = Settings.load(directory/'settings.json')
        if args.export:
            moment = datetime.fromisoformat(args.at) if args.at else datetime.now(timezone.utc)
            width, height = map(int, args.size.lower().split('x'))
            if not render(moment, settings, width, height).save(str(args.export), 'PNG'):
                raise RuntimeError('Kuvan tallennus ei onnistunut.')
            print(args.export)
            return 0
        directory.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(directory/'instance.lock'))
        # Qt verifies the owning PID; never start a second competing wallpaper writer.
        if not lock.tryLock(100):
            QMessageBox.information(None, 'Veriyö Live', 'Veriyö Live on jo käynnissä. Avaa se ilmoitusalueen kuvakkeesta tai sulje aiempi ikkuna.')
            return 0
        app.setStyle('Fusion')
        app.setStyleSheet(STYLE)
        window = Window(settings, directory)
        if args.background:
            QTimer.singleShot(0, window.start)
            if not window.tray:
                window.show()
        else:
            window.show()
        return app.exec()
    except Exception as error:
        if args.export:
            print(str(error), file=sys.stderr)
        else:
            QMessageBox.critical(None, 'Veriyö Live ei käynnistynyt', str(error))
        return 1
