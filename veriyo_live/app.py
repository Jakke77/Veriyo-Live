"""Finnish standalone GUI, tray, CLI export, and explicitly enabled background engine."""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import os
import time
from PyQt6.QtCore import QLockFile, QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem)
from . import VERSION
from .calendar import ZONE
from .engine import Engine, Task
from .ubuntu_pack import PackLibrary, catalog, PACK_NAME
from .platforms import set_autostart
from .render import ASSETS, render
from .settings import Settings, data_dir
from .shuffle import INTERVALS, background_options, background_key, choose_next, eligible_options, with_background

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
        self.engine.changed.connect(self.sync_motion_desktop)
        self.library=self.engine.library
        self.motion_desktop=None
        self.motion_failure=""
        self.pack_worker=None
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
        self.shuffle_due = None
        self.tray = None
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(12)
        title = QLabel('VERIYÖ LIVE')
        title.setObjectName('title')
        outer.addWidget(title)
        subtitle = QLabel('Liikkuvia taivasteemoja ja Ubuntun oletustaustakuvakokoelma.')
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
        from .scenes import SCENES
        for key, (name, _) in SCENES.items():
            self.theme.addItem(name, key)
        self.theme.addItem('Ubuntun oletustaustat', 'ubuntu')
        self.theme.setCurrentIndex(self.theme.findData(settings.theme))
        self.theme.currentIndexChanged.connect(self.refresh_preview)
        self.theme.currentIndexChanged.connect(self.update_controls)
        form.addRow('Taustakuvan tyyli', self.theme)
        self.ubuntu_row=QWidget()
        ubuntu_layout=QHBoxLayout(self.ubuntu_row);ubuntu_layout.setContentsMargins(0,0,0,0)
        self.ubuntu_version=QComboBox()
        for entry in reversed(catalog()):
            self.ubuntu_version.addItem(f'Ubuntu {entry["version"]} · {entry["name"]}',entry['version'])
        self.ubuntu_version.setCurrentIndex(self.ubuntu_version.findData(settings.ubuntu_version))
        self.ubuntu_version.setAccessibleName('Ubuntu-versio')
        self.ubuntu_version.currentIndexChanged.connect(self.change_ubuntu_version)
        self.pack_button=QPushButton('Asenna Ubuntu-kuvat…')
        self.pack_button.clicked.connect(self.install_pack)
        ubuntu_layout.addWidget(self.ubuntu_version,1);ubuntu_layout.addWidget(self.pack_button)
        form.addRow('Ubuntu-versio',self.ubuntu_row)
        self.ubuntu_row_label=form.labelForField(self.ubuntu_row)
        self.motion_label=QLabel();self.motion_label.setWordWrap(True);self.motion_label.setObjectName('hint')
        form.addRow('',self.motion_label)
        location = QHBoxLayout()
        self.latitude, self.longitude = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, minimum, maximum, value, label in (
            (self.latitude, -90, 90, settings.latitude, 'Leveysaste pohjoista'),
            (self.longitude, -180, 180, settings.longitude, 'Pituusaste itään')):
            spin.setRange(minimum, maximum)
            spin.setDecimals(6)
            spin.setValue(value)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(self.refresh_preview)
            location.addWidget(spin)
        form.addRow('Sijainti · leveys / pituus', location)
        self.location_label=form.labelForField(location)
        from zoneinfo import available_timezones
        self.timezone=QComboBox(); self.timezone.setEditable(True)
        self.timezone.addItems(sorted(available_timezones()))
        self.timezone.setCurrentText(settings.timezone)
        self.timezone.setAccessibleName('Sijainnin aikavyöhyke')
        self.timezone.currentTextChanged.connect(self.refresh_preview)
        form.addRow('Aikavyöhyke',self.timezone)
        self.timezone_label=form.labelForField(self.timezone)
        flags = QHBoxLayout()
        self.guides = QCheckBox('Suunnat ja Alkaid')
        self.guides.setChecked(settings.guides)
        self.guides.toggled.connect(self.refresh_preview)
        flags.addWidget(self.guides)
        form.addRow('Kuvassa näkyy', flags)
        self.guides_label=form.labelForField(flags)
        self.date_mode = QComboBox()
        for label, mode in (('Piilossa', 'none'), ('Veri Aika', 'blood'),
                            ('Tavallinen päivämäärä', 'gregorian'), ('Molemmat', 'both')):
            self.date_mode.addItem(label, mode)
        self.date_mode.setCurrentIndex(self.date_mode.findData(settings.date_mode))
        self.date_mode.setAccessibleName('Taustakuvan päivämäärä')
        self.date_mode.setToolTip('Valinta tallentuu ja päivittyy myös käynnissä olevaan taustaan. Piilossa poistaa kaikki päivämäärät taustakuvasta.')
        self.date_mode.currentIndexChanged.connect(self.change_date_mode)
        form.addRow('Päivämäärä', self.date_mode)
        self.date_label=form.labelForField(self.date_mode)
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
        self.interval_label=form.labelForField(advanced)
        self.autostart = QCheckBox('Käynnistä elävä tausta kirjautuessani sisään')
        self.autostart.setChecked(settings.autostart)
        form.addRow('', self.autostart)
        shuffle_row=QWidget();shuffle_layout=QVBoxLayout(shuffle_row);shuffle_layout.setContentsMargins(0,0,0,0)
        shuffle_top=QHBoxLayout()
        self.shuffle=QCheckBox('Vaihda taustaa satunnaisesti');self.shuffle.setChecked(settings.shuffle_enabled)
        self.shuffle.setToolTip('Automaattinen vaihto toimii, kun tausta on otettu käyttöön. Pysäytä päivitys pysäyttää myös satunnaisvaihdon.')
        self.shuffle_interval=QComboBox()
        for seconds,name in INTERVALS:self.shuffle_interval.addItem(name,seconds)
        self.shuffle_interval.setCurrentIndex(self.shuffle_interval.findData(settings.shuffle_interval))
        shuffle_top.addWidget(self.shuffle);shuffle_top.addWidget(self.shuffle_interval)
        shuffle_layout.addLayout(shuffle_top)
        shuffle_buttons=QHBoxLayout()
        self.shuffle_select=QPushButton('Valitse mukaan tulevat taustat…')
        self.shuffle_now=QPushButton('Vaihda satunnainen tausta nyt')
        self.shuffle_now.setToolTip('Vaihtaa käynnissä olevan taustan; pysäytettynä valitsee vain esikatselun.')
        shuffle_buttons.addWidget(self.shuffle_select);shuffle_buttons.addWidget(self.shuffle_now)
        shuffle_layout.addLayout(shuffle_buttons);form.addRow('Satunnaisvaihto',shuffle_row)
        self.shuffle.toggled.connect(self.shuffle_changed)
        self.shuffle_interval.currentIndexChanged.connect(self.shuffle_changed)
        self.shuffle_select.clicked.connect(self.choose_shuffle_backgrounds)
        self.shuffle_now.clicked.connect(self.random_background)
        outer.addWidget(form_widget)
        hint = QLabel('Otava-maisemissa katsotaan pohjoiseen. Uudet taivaskartat näyttävät koko näkyvän taivaan; sijainti ja aikavyöhyke valitaan itse. '
            'Ubuntu-kuvat ovat taustakuvakokoelma; niihin ei luvata havaittavaa animaatiota. '
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
        self.shuffle_timer=QTimer(self);self.shuffle_timer.setInterval(1000)
        self.shuffle_timer.timeout.connect(self.shuffle_tick);self.shuffle_timer.start()
        self.refresh_preview()
        self.update_controls()

    def values(self):
        return Settings(theme=self.theme.currentData(), latitude=self.latitude.value(), longitude=self.longitude.value(),
                        guides=self.guides.isChecked(), date_mode=self.date_mode.currentData(), interval=self.interval.currentData(),
                        lock_screen=self.lock.isChecked(), autostart=self.autostart.isChecked(),
                        ubuntu_version=self.ubuntu_version.currentData(),timezone=self.timezone.currentText(),
                        shuffle_enabled=self.shuffle.isChecked(),shuffle_interval=self.shuffle_interval.currentData(),
                        shuffle_choices=list(self.settings.shuffle_choices)).validate()

    def shuffle_changed(self,*args):
        try:
            self.settings=replace(self.settings,shuffle_enabled=self.shuffle.isChecked(),
                                  shuffle_interval=self.shuffle_interval.currentData())
            self.settings.save(self.directory/'settings.json')
            self.shuffle_due=None;self.update_controls()
        except Exception as error:self.show_status(str(error))

    def choose_shuffle_backgrounds(self):
        value=self.values()
        options=background_options()
        eligible=dict(eligible_options(value,self.library.installed()))
        selected=set(value.shuffle_choices) if value.shuffle_choices else set(eligible)
        dialog=QDialog(self);dialog.setWindowTitle('Satunnaisvaihdon taustat');dialog.resize(580,580)
        layout=QVBoxLayout(dialog)
        hint=QLabel('Valitse vaihtoon mukaan tulevat taustat. Nykyistä taustaa ei arvota heti uudelleen. Ubuntu-kuvat tarvitsevat asennetun kuvapaketin.')
        hint.setWordWrap(True);layout.addWidget(hint)
        listing=QListWidget();layout.addWidget(listing)
        for key,name in options:
            item=QListWidgetItem(name);item.setData(Qt.ItemDataRole.UserRole,key)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in selected else Qt.CheckState.Unchecked)
            if key not in eligible:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip('Asenna ensin Ubuntu-kuvapaketti.' if key.startswith('ubuntu:') else 'Otava-maisemat tukevat leveysasteita 60–70° N.')
            listing.addItem(item)
        actions=QHBoxLayout();all_button=QPushButton('Kaikki käytettävissä olevat');clear_button=QPushButton('Tyhjennä')
        def check_items(all_available):
            for index in range(listing.count()):
                item=listing.item(index);checked=all_available and item.data(Qt.ItemDataRole.UserRole) in eligible
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        all_button.clicked.connect(lambda:check_items(True));clear_button.clicked.connect(lambda:check_items(False))
        actions.addWidget(all_button);actions.addWidget(clear_button);layout.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def choices():
            return [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count())
                    if listing.item(i).checkState()==Qt.CheckState.Checked]
        def accept():
            if not set(choices()).intersection(eligible):
                QMessageBox.information(dialog,'Valitse tausta','Valitse vähintään yksi käytettävissä oleva tausta. Automaattinen vaihtelu tarvitsee vähintään kaksi.')
                return
            dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            self.settings=replace(self.settings,shuffle_choices=choices())
            self.settings.save(self.directory/'settings.json');self.shuffle_due=None
            self.show_status(f'Satunnaisvaihtoon valittu {len(self.settings.shuffle_choices)} taustaa.')
        except Exception as error:self.show_status(str(error))

    def random_background(self):
        if self.engine.busy or self.pack_worker is not None:return False
        try:
            value=self.values()
            choice=choose_next(eligible_options(value,self.library.installed()),background_key(value),value.shuffle_choices)
            self.shuffle_due=time.monotonic()+value.shuffle_interval
            if choice is None:
                self.show_status('Satunnaisvaihtoon ei löydy toista käytettävissä olevaa taustaa. Valitse mukaan vähintään kaksi taustaa.')
                return False
            value=with_background(value,choice);value.save(self.directory/'settings.json');self.settings=value
            blockers=[QSignalBlocker(self.theme),QSignalBlocker(self.ubuntu_version)]
            self.theme.setCurrentIndex(self.theme.findData(value.theme))
            self.ubuntu_version.setCurrentIndex(self.ubuntu_version.findData(value.ubuntu_version))
            del blockers
            if self.engine.running:self.engine.set_background(choice)
            self.refresh_preview();self.update_controls()
            if not self.engine.running:self.show_status('Satunnainen tausta valittu esikatseluun. Ota tausta käyttöön käynnistyspainikkeella.')
            return True
        except Exception as error:
            self.show_status(str(error));return False

    def shuffle_tick(self):
        if not self.engine.running or not self.shuffle.isChecked():
            self.shuffle_due=None;return
        if self.engine.busy or self.pack_worker is not None:return
        if QApplication.activeModalWidget() is not None:return
        if self.shuffle_due is None:
            self.shuffle_due=time.monotonic()+self.shuffle_interval.currentData()
        elif time.monotonic()>=self.shuffle_due:self.random_background()

    def install_pack(self):
        path,_=QFileDialog.getOpenFileName(self,'Asenna Ubuntu-kuvat: '+PACK_NAME,'','Ubuntu-kuvapaketti (*.zip)')
        if not path:return
        self.show_status('Asennetaan live-pakettia ja tarkistetaan kuvat…')
        self.pack_worker=Task('pack-install',lambda:self.library.install(path),self)
        self.pack_worker.finished.connect(self.pack_installed)
        self.update_controls();self.pack_worker.start()

    def pack_installed(self):
        worker=self.pack_worker;self.pack_worker=None
        error=worker.error;worker.deleteLater()
        self.refresh_preview();self.update_controls()
        self.show_status('Asennus ei onnistunut: '+error if error else 'Ubuntu-kuvapaketti asennettu · 45 versiota valittavana.')

    def sync_motion_desktop(self):
        active=(os.name=='nt' and self.engine.running and self.engine.motion_entry is not None and
                self.engine.session is not None and self.engine.session.adapter.kind=='windows')
        if not active and self.motion_desktop is not None:
            desktop=self.motion_desktop;self.motion_desktop=None;desktop.shutdown()
        elif active and self.motion_desktop is None:
            try:
                from .windows_motion import MotionDesktop
                self.motion_desktop=MotionDesktop(self.engine.motion_entry,self.motion_error)
            except Exception as error:self.motion_error(str(error))
        elif active and self.motion_desktop is not None:
            self.motion_desktop.entry=self.engine.motion_entry

    def motion_error(self,message):
        self.motion_failure=message
        self.engine.stop()
        self.show_status('Windowsin live-tausta ei käynnistynyt: '+message)
        self.open_window()

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

    def change_ubuntu_version(self,*args):
        try:
            value=replace(self.settings,ubuntu_version=self.ubuntu_version.currentData())
            value.save(self.directory/'settings.json');self.settings=value
            self.engine.set_ubuntu_version(value.ubuntu_version)
            self.refresh_preview()
        except Exception as error:self.show_status(str(error))

    def show_status(self, value):
        if self.motion_failure and value.startswith("Päivitys pysäytetty"):
            value="Pysäytyskuva käytössä · "+self.motion_failure
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
        self.motion_failure=""
        self.shuffle_due=None
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
        if not hasattr(self,'save_button'):return
        active = self.engine.running or self.engine.busy or self.pack_worker is not None
        shuffling_available=not self.engine.busy and self.pack_worker is None
        self.shuffle.setEnabled(shuffling_available)
        self.shuffle_interval.setEnabled(shuffling_available and self.shuffle.isChecked())
        self.shuffle_select.setEnabled(shuffling_available);self.shuffle_now.setEnabled(shuffling_available)
        ubuntu=self.theme.currentData()=='ubuntu'
        from .scenes import SCENES
        scene=self.theme.currentData() in SCENES
        landscape=self.theme.currentData() in ('stream','rose_garden','lighthouse')
        location=self.theme.currentData() in ('otava','hiillos','polaris','moon')
        self.latitude.setRange(60 if self.theme.currentData() in ('otava','hiillos') else -90,
                               70 if self.theme.currentData() in ('otava','hiillos') else 90)
        for widget in (self.theme, self.latitude, self.longitude, self.guides, self.interval, self.lock,
                       self.autostart, self.save_button,self.ubuntu_version,self.pack_button,self.timezone):
            widget.setEnabled(not active)
        for widget in (self.latitude,self.longitude,self.guides,self.interval):
            widget.setEnabled(not active and not ubuntu)
        self.date_mode.setEnabled(not ubuntu and self.pack_worker is None)
        self.demo.setEnabled(not ubuntu)
        if ubuntu and self.demo.isChecked():self.demo.setChecked(False)
        self.ubuntu_row.setVisible(ubuntu);self.ubuntu_row_label.setVisible(ubuntu);self.motion_label.setVisible(ubuntu)
        self.ubuntu_version.setEnabled(self.pack_worker is None)
        for widget in (self.demo,self.time_label,self.latitude,self.longitude,self.location_label,self.guides,
                       self.guides_label,self.date_mode,self.date_label,self.interval):widget.setVisible(not ubuntu)
        for widget in (self.latitude,self.longitude,self.location_label):widget.setVisible(location)
        self.timezone.setVisible(scene);self.timezone_label.setVisible(scene)
        self.motion_label.setVisible(ubuntu or scene)
        self.guides.setText('Teeman nimi ja vuorokaudenaika' if landscape else 'Suunnat ja tähtinimet' if scene else 'Suunnat ja Alkaid')
        self.start_button.setText('Ota taustakuva käyttöön' if ubuntu else 'Ota elävä tausta käyttöön')
        self.demo.setVisible(landscape or self.theme.currentData() in ('otava','hiillos','polaris','moon'))
        if self.demo.isHidden() and self.demo.isChecked():self.demo.setChecked(False)
        self.interval_label.setText('Lukituskuva' if ubuntu else 'Päivitysväli')
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
        from .scenes import SCENES
        if self.theme.currentData()=='ubuntu':
            self.refresh_preview(moment=now);return
        if self.demo_start is not None:
            import time
            now = self.demo_start[1] + timedelta(seconds=(time.monotonic()-self.demo_start[0])*1440)
        elif self.last_preview_second == int(now.timestamp()) and self.theme.currentData() not in SCENES:
            return
        self.last_preview_second = int(now.timestamp())
        self.refresh_preview(moment=now)

    def refresh_preview(self, *args, moment=None):
        if not hasattr(self, 'autostart'):
            return
        try:
            value = self.values()
            from .scenes import SCENES
            if value.theme=='ubuntu':
                self.motion_label.setText('Ubuntu-taustakuvakokoelma · animaatiota ei luvata.')
            elif value.theme in SCENES:
                self.motion_label.setText(SCENES[value.theme][1])
            elif value.theme not in self.backgrounds:
                self.backgrounds[value.theme] = QImage(str(ASSETS/(value.theme+'.png')))
            moment = moment or datetime.now(timezone.utc)
            self.preview.update_image(render(moment, value, 1280, 720, self.backgrounds.get(value.theme),library=self.library,
                                             animation_seconds=datetime.now(timezone.utc).timestamp()))
            from zoneinfo import ZoneInfo
            local = moment.astimezone(ZoneInfo(value.timezone) if value.theme in SCENES else ZONE)
            self.time_label.setText(('ESIKATSELU · ' if self.demo.isChecked() else '') + f'{local:%d.%m.%Y %H:%M:%S} {local.tzname()}')
        except Exception as error:
            if self.theme.currentData()=='ubuntu':
                self.preview.frame=None;self.preview.clear();self.preview.setText('Asenna Ubuntu-kuvapaketti näyttääksesi tämän taustan.')
            self.show_status(str(error))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Tallenna tämän hetken taivas', 'veriyo-live.png', 'PNG-kuva (*.png)')
        if not path:
            return
        try:
            size = QApplication.primaryScreen().size()
            image = render(datetime.now(timezone.utc), self.values(), max(320, size.width()), max(240, size.height()),library=self.library)
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
        elif self.engine.busy or self.pack_worker is not None or (self.engine.running and self.engine.motion_entry is not None):
            self.quit()
            event.ignore()
        else:
            QApplication.instance().quit()
            event.accept()

    def quit(self):
        self.engine.stop()
        if self.engine.busy or self.pack_worker is not None:
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
    parser.add_argument('--install-ubuntu-pack',type=Path,help='Asenna Ubuntu Live Pack -ZIP paikallisesti')
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
        if args.install_ubuntu_pack:
            print(PackLibrary(directory).install(args.install_ubuntu_pack))
            return 0
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
        if args.export or args.install_ubuntu_pack:
            print(str(error), file=sys.stderr)
        else:
            QMessageBox.critical(None, 'Veriyö Live ei käynnistynyt', str(error))
        return 1
