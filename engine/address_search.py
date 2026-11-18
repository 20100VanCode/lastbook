"""Read-only address lookup using the state indexes installed with offline maps."""
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

from engine.paths import ro_uri

# Keep normalization compatible with tools/build_addresses.py.
WORDS = {
    'boulevard': 'blvd', 'avenue': 'ave', 'av': 'ave', 'street': 'st',
    'drive': 'dr', 'road': 'rd', 'place': 'pl', 'court': 'ct', 'lane': 'ln',
    'terrace': 'ter', 'circle': 'cir', 'highway': 'hwy', 'parkway': 'pkwy',
    'square': 'sq', 'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
    'mount': 'mt', 'saint': 'st',
}
STATE_NAMES = (
    'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|'
    'District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|'
    'Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|'
    'Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|'
    'New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|'
    'Pennsylvania|Puerto Rico|Rhode Island|South Carolina|South Dakota|'
    'Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
).split('|')
STATE_CODES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY'.split()
STATES = dict(zip((name.lower() for name in STATE_NAMES), STATE_CODES))
ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
ORDINALS = 'zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth'.split()
TO_DIGITS = {word: str(number) for number, word in enumerate(ONES)}
for number, word in enumerate(ORDINALS):
    suffix = 'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
    TO_DIGITS[word] = f'{number}{suffix}'
TO_WORDS = {value: key for key, value in TO_DIGITS.items()}


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


def is_address_query(query):
    """A standalone ZIP remains a place query. A number followed by words is an address."""
    return bool(re.match(r'^\s*\d[\w-]*\s+\S', query))


def street_forms(street):
    words = street.split()
    forms = [street, ' '.join(TO_DIGITS.get(word, word) for word in words),
             ' '.join(TO_WORDS.get(word, word) for word in words)]
    forms += [re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', form) for form in forms[:]]
    if words[0] not in ('n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'):
        forms += [f'{direction} {form}' for form in forms[:] for direction in ('n', 's', 'e', 'w')]
    return list(dict.fromkeys(forms))


def _parts(query):
    number, remainder = query.strip().split(None, 1)
    number = number.upper()
    remainder = re.sub(r'[^a-z0-9 ]+', ' ', remainder.lower()).split()
    # A ZIP+4 ("62704-1234", or "62704 1234" once the hyphen is gone) is the same place as its five-digit ZIP, which the
    # index keeps: drop the four extra digits so the ZIP and the state before it are still read.
    if len(remainder) > 1 and re.fullmatch(r'\d{4}', remainder[-1]) and re.fullmatch(r'\d{5}', remainder[-2]):
        remainder.pop()
    postcode = ''
    if remainder and re.fullmatch(r'\d{5}', remainder[-1]):
        postcode = remainder.pop()
    state = ''
    for count in (3, 2, 1):
        if len(remainder) <= count:
            continue
        name = ' '.join(remainder[-count:])
        code = STATES.get(name) or (name.upper() if count == 1 and name.upper() in STATE_CODES else '')
        if code:
            state = code
            remainder = remainder[:-count]
            break
    return number, normalize(' '.join(remainder)).split(), state, postcode


def find_addresses(query, geo_directory, limit=8, near=None):
    """Return exact house-number matches from installed indexes, never a guessed house."""
    if not is_address_query(query):
        return []
    geo_directory = Path(geo_directory)
    paths = sorted((geo_directory / 'addresses').glob('*.sqlite'))
    if any(path.name.startswith('FR-') for path in paths):
        return find_addresses_fr(query, paths, limit, near)
    number, words, state, postcode = _parts(query)
    if not words:
        return []
    if state:
        paths = [path for path in paths if path.stem.upper() == state]
    legacy = geo_directory / 'addresses.sqlite'
    if not paths and legacy.is_file():
        paths = [legacy]
    connections = []
    try:
        for path in paths:
            try:
                connections.append(sqlite3.connect(ro_uri(path), uri=True))
            except sqlite3.Error:
                continue
        for count in range(len(words), 0, -1):
            street = ' '.join(words[:count])
            if all(word in set(WORDS.values()) for word in words[:count]):
                continue
            city = ' '.join(words[count:])
            rows = []
            for form in street_forms(street):
                conditions = ['num IN (?, ?)', 'norm >= ?', 'norm < ?']
                parameters = [number, number.lower(), form, form + '\uffff']
                if state:
                    conditions.append('state = ?')
                    parameters.append(state)
                if postcode:
                    conditions.append('zip = ?')
                    parameters.append(postcode)
                if city:
                    conditions.append('lower(city) LIKE ?')
                    parameters.append(city + '%')
                sql = ('SELECT num,street,city,state,zip,lat,lon,norm FROM addr WHERE '
                       + ' AND '.join(conditions) + ' ORDER BY length(norm),norm LIMIT ?')
                for connection in connections:
                    try:
                        rows.extend(connection.execute(sql, [*parameters, limit * 3]).fetchall())
                    except sqlite3.Error:
                        continue
            if rows:
                def rank(row):
                    distance = 0
                    if near:
                        distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
                    return len(row[7]), distance, row[3], row[2], row[1]
                results, seen = [], set()
                for num, name, city_name, state_code, zip_code, lat, lon, normalized in sorted(rows, key=rank):
                    key = (num, normalized, lat, lon)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        'name': f'{num} {name}', 'kind': 'Street address',
                        'detail': ', '.join(part for part in (city_name, state_code, zip_code) if part),
                        'lat': lat, 'lon': lon, 'source': 'Overture Maps', 'onMap': True,
                    })
                    if len(results) == limit:
                        break
                return results
        return []
    finally:
        for connection in connections:
            connection.close()


# --------------------------------------------------------------------- France
# The Base Adresse Nationale writes a French address as number, optional repetition
# (bis/ter), street type and name, then the postcode and the commune:
# "14 bis Rue Écuyère, 14000 Caen". The US rules above read a postcode last and a
# state name at the end, so they drop "Bellême" to "me" and look for a state. A
# French index declares meta.country='FR' (tools/build_addresses_fr.py) and is
# searched here, where no trailing word is ever read as a state.
FR_WORDS = {
    'bd': 'boulevard', 'blv': 'boulevard', 'bvd': 'boulevard', 'boulevard': 'boulevard',
    'av': 'avenue', 'ave': 'avenue', 'avenue': 'avenue',
    'imp': 'impasse', 'impa': 'impasse', 'impasse': 'impasse',
    'rte': 'route', 'route': 'route', 'pl': 'place', 'place': 'place',
    'ch': 'chemin', 'chem': 'chemin', 'chemin': 'chemin',
    'all': 'allee', 'alle': 'allee', 'allee': 'allee',
    'fg': 'faubourg', 'faub': 'faubourg', 'faubourg': 'faubourg',
    'qu': 'quai', 'qua': 'quai', 'quai': 'quai',
    'sq': 'square', 'square': 'square', 'pas': 'passage', 'pass': 'passage',
    'passage': 'passage', 'car': 'carrefour', 'carr': 'carrefour',
    'carrefour': 'carrefour', 'prom': 'promenade', 'promenade': 'promenade',
    'r': 'rue', 'rue': 'rue', 'st': 'saint', 'saint': 'saint',
    'ste': 'sainte', 'sainte': 'sainte', 'ham': 'hameau', 'hameau': 'hameau',
    'res': 'residence', 'residence': 'residence',
    'rnd': 'rond point', 'rpt': 'rond point', 'rondpoint': 'rond point',
}
# A street made only of these is not a street ("Rue", "Avenue"), so it never matches.
FR_STREET_TYPES = frozenset(('rue', 'avenue', 'boulevard', 'place', 'chemin', 'route',
                             'impasse', 'allee', 'passage', 'quai', 'square'))
FR_REPETITION = ('bis', 'ter', 'quater', 'quatr') + tuple('abcdefghijklmnopqrstuvwxyz')


def _fold(text):
    """Lower-case, accents folded, œ/æ expanded: the characters a-z0-9 survive it."""
    t = unicodedata.normalize('NFKD', str(text).lower())
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace('œ', 'oe').replace('æ', 'ae')


def normalize_fr(text):
    """'Rue Écuyère' -> 'rue ecuyere'. Accents folded, œ/æ expanded, street words canonical."""
    words = re.sub(r'[^a-z0-9 ]+', ' ', _fold(text)).split()
    return ' '.join(FR_WORDS.get(word, word) for word in words)


def _parts_fr(query):
    """'14 bis Rue Écuyère, 14000 Caen' -> ('14', 'bis', ['rue','ecuyere','caen'], '14000').

    The postcode comes before the commune, so it is taken wherever it appears; no
    trailing word is ever read as a state, which is what removed "Bellême" and "Ri".
    """
    match = re.match(r'^(\d[\w-]*)\s+(.*)$', str(query).strip())
    if not match:
        return None
    number = match.group(1).lower()
    rest = match.group(2)
    repetition = ''
    rep = re.match(r'^(bis|ter|quater|quatr|[a-z])\s+(.*)$', rest, re.I)
    if rep and rep.group(1).lower() != 'r':   # a leading "r" is "rue", not a repetition
        repetition = rep.group(1).lower()
        rest = rep.group(2)
    tokens = re.sub(r'[^a-z0-9 ]+', ' ', _fold(rest)).split()
    postcode = ''
    for index in range(len(tokens) - 1, -1, -1):
        if re.fullmatch(r'\d{5}', tokens[index]):
            postcode = tokens.pop(index)
            break
    return number, repetition, normalize_fr(' '.join(tokens)).split(), postcode


def find_addresses_fr(query, paths, limit=8, near=None):
    """Exact house-number matches from a French index, never a guessed house."""
    parts = _parts_fr(query)
    if not parts:
        return []
    number, repetition, words, postcode = parts
    if not words:
        return []
    numbers = [number] + [f'{number} {r}' for r in FR_REPETITION]
    if repetition:
        numbers.insert(0, f'{number} {repetition}')
    numbers = list(dict.fromkeys(numbers))
    holders = ','.join('?' * len(numbers))

    def lookup(street, city):
        rows = []
        for path in paths:
            try:
                connection = sqlite3.connect(ro_uri(path), uri=True)
            except sqlite3.Error:
                continue
            try:
                rows.extend(connection.execute(
                    f'SELECT num,street,city,state,zip,lat,lon,norm FROM addr'
                    f' WHERE norm >= ? AND norm < ? AND num IN ({holders})'
                    f' ORDER BY length(norm),norm LIMIT ?',
                    [street, street + '\uffff', *numbers, limit * 6]).fetchall())
            except sqlite3.Error:
                continue
            finally:
                connection.close()
        if city:
            rows = [row for row in rows if normalize_fr(row[2]).startswith(city)]
        if postcode:
            rows = [row for row in rows if row[4] == postcode]
        return rows

    # Prefer a split that leaves a commune: "14 rue de la République, Fort-de-France"
    # must not return every "rue de la République" in the département.
    for count in range(len(words) - 1, 0, -1):
        if all(word in FR_STREET_TYPES for word in words[:count]):
            continue
        rows = lookup(' '.join(words[:count]), normalize_fr(' '.join(words[count:])))
        if rows:
            return _fr_results(rows, limit, near)
    rows = lookup(' '.join(words), '')
    return _fr_results(rows, limit, near) if rows else []


def _fr_results(rows, limit, near):
    def rank(row):
        distance = 0
        if near:
            distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
        return len(row[7]), distance, row[2], row[1]

    results, seen = [], set()
    for num, street_name, city_name, _state, zip_code, lat, lon, normalized in sorted(rows, key=rank):
        key = (num, normalized, lat, lon)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'name': f'{num} {street_name}', 'kind': 'Adresse',
            'detail': ', '.join(part for part in (city_name, zip_code) if part),
            'lat': lat, 'lon': lon, 'source': 'Base Adresse Nationale', 'onMap': True,
        })
        if len(results) == limit:
            break
    return results
