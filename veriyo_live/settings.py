"""Small validated settings, separate from the calendar/weather application's data."""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import tempfile


def data_dir():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'VeriyoLive'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'veriyo-live'


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.veriyo-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class Settings:
    theme: str = 'otava'
    latitude: float = 65.071562
    longitude: float = 25.507046
    guides: bool = True
    date_mode: str = 'blood'
    interval: int = 60
    lock_screen: bool = False
    autostart: bool = False

    def validate(self):
        if self.theme not in ('otava', 'hiillos'):
            raise ValueError('Tuntematon taustakuva.')
        if self.date_mode not in ('none', 'blood', 'gregorian', 'both'):
            raise ValueError('Tuntematon päivämäärän näyttötapa.')
        for name, limit in (('latitude', 90), ('longitude', 180)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
                raise ValueError('Virheellinen sijainti.')
        # This first composition is designed for circumpolar Otava in northern Finland.
        if not 60 <= self.latitude <= 70:
            raise ValueError('Tämän version taivasnäkymä tukee leveysasteita 60–70° N.')
        if type(self.interval) is not int or self.interval not in (60, 300, 1560):
            raise ValueError('Päivitysvälin pitää olla 1, 5 tai 26 minuuttia.')
        for name in ('guides', 'lock_screen', 'autostart'):
            if type(getattr(self, name)) is not bool:
                raise ValueError('Virheellinen valinta: ' + name)
        return self

    def save(self, path):
        self.validate()
        atomic_json(path, asdict(self))

    @classmethod
    def load(cls, path):
        if not Path(path).exists():
            return cls()
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('Asetustiedosto ei ole oikeaa muotoa.')
        if 'calendar' in value:
            legacy = value.pop('calendar')
            if type(legacy) is not bool:
                raise ValueError('Virheellinen vanhan version päivämäärävalinta.')
            value.setdefault('date_mode', 'blood' if legacy else 'none')
        return cls(**value).validate()
