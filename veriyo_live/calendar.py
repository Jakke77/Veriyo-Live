"""Same 777-local-day Veri Aika rules as Ajanlaskut ja Sää 1.12.3."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Helsinki')
EPOCH = date(2026, 6, 26)
CUTOVER = time(1, 7, 7)


def blood_label(moment):
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('Aikaleima tarvitsee aikavyöhykkeen.')
    local = moment.astimezone(ZONE)
    day = local.date() - timedelta(days=local.time() < CUTOVER)
    ordinal = (day - EPOCH).days
    if ordinal < 0:
        return f'{-ordinal}. päivä ennen Veri Ajan alkua', ''
    position = ordinal % 777
    return (f'{position % 7 + 1}. päivä · {position // 7 + 1}. viikko · vuosi {ordinal // 777 + 1:04d}',
            f'Vuoden päivä {position + 1}/777')


def date_block(moment, mode):
    """All wallpaper dates belong to this optional block, never the footer."""
    if mode == 'none':
        return '', ()
    if mode not in ('blood', 'gregorian', 'both'):
        raise ValueError('Tuntematon päivämäärän näyttötapa.')
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('Aikaleima tarvitsee aikavyöhykkeen.')
    local = moment.astimezone(ZONE)
    civil = f'{local:%d.%m.%Y} · klo {local:%H:%M} {local.tzname()}'
    if mode == 'gregorian':
        weekdays = ('Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai', 'Sunnuntai')
        return 'PÄIVÄMÄÄRÄ', (weekdays[local.weekday()], civil)
    label, ordinal = blood_label(moment)
    pieces = label.split(' · ')
    lines = tuple(line for line in (' · '.join(pieces[:2]), ' · '.join(pieces[2:]), ordinal) if line)
    if mode == 'both':
        return 'VERI AIKA JA PÄIVÄMÄÄRÄ', (*lines, civil)
    return 'VERI AIKA', lines
