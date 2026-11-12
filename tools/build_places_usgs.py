"""Civic and emergency places from USGS National Structures: derived/geo/places-usgs.sqlite.

  derived/buildenv/bin/python tools/build_places_usgs.py             # download what is missing, then build
  derived/buildenv/bin/python tools/build_places_usgs.py --no-download  # build from what is already downloaded
  derived/buildenv/bin/python tools/build_places_usgs.py --refresh      # download every state again (USGS updates them)

If a state cannot be downloaded the build stops with an error and the old places-usgs.sqlite is kept; pass
--allow-missing to build without it anyway (meta 'states' then lists the states that are in).

The USGS National Structures Dataset (part of The National Map, public domain) is a hand-checked register of named
fire stations, EMS stations, police stations, post offices, city and county halls, hospitals, schools, colleges,
cemeteries, prisons and federal recreation points (campgrounds, trailheads, visitor centres, ranger stations). These are
exactly the places a survival game needs and that OpenStreetMap often lacks in suburbs (around Novi, Michigan it adds
Novi Fire Stations 1-4, Novi and Northville police, two post offices, Novi City Hall and the Providence hospital).

USGS publishes one zip per state and territory at
https://prd-tnm.s3.amazonaws.com/StagedProducts/Struct/Shape/STRUCT_<State>_State_Shape.zip (also as GPKG and GDB).
The zips are huge (Michigan is about 1 GB) because they carry the FEMA building footprints, but the point layer we need
is a few MB. The Shape zips keep each layer as its own zip member, so this script reads the zip's directory over HTTP
Range requests and fetches only Shape/Struct_Point.{shp,shx,dbf,prj} (plus the metadata XML), 4 states at a time, into
derived/geo/sources/usgs/<State>/. The same data is in the GPKG zips, but there the 4 GB GeoPackage is one deflate
stream and would have to be downloaded whole.

fcode_desc is mostly "Undefined", so FCODE is mapped here (FCODES below). Coordinates are NAD83 (EPSG:4269), used as
WGS84 (they differ by about a metre). Only class, name and position are kept: no addresses or contact fields. Same table
as tools/build_places_overture.py so game/serve.py can merge it.
"""
import argparse, collections, io, math, re, sqlite3, struct, sys, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/usgs'
OUT = HERE / 'derived/geo/places-usgs.sqlite'
BUCKET = 'https://prd-tnm.s3.amazonaws.com'
PREFIX = 'StagedProducts/Struct/Shape/'
WANT = ('Shape/Struct_Point.shp', 'Shape/Struct_Point.shx', 'Shape/Struct_Point.dbf', 'Shape/Struct_Point.prj')
CONF = 0.95
# USGS National Structures FCODE -> game class (https://www.usgs.gov/ngp-standards-and-specifications/national-structures-dataset)
FCODES = {
    73002: 'school', 73003: 'school', 73004: 'school', 73005: 'school',  # school, elementary, middle, high
    73006: 'school', 73007: 'school',  # college / university, technical / trade school
    74001: 'ems_station', 74026: 'fire_station', 74034: 'police', 74036: 'prison',
    78006: 'post_office', 80012: 'hospital',
    82007: 'cabin', 82008: 'campground', 82010: 'cemetery', 82040: 'picnic_site', 82047: 'trailhead', 82048: 'visitor_centre',
    83006: 'town_hall', 83010: 'courthouse', 83011: 'town_hall', 83044: 'town_hall',  # state capitol, supreme court, county, city/town hall
    83023: 'ranger_station', 83033: 'ranger_station',  # national forest supervisor office, ranger district / park HQ
    83004: 'town_hall', 83008: 'courthouse', 83042: 'landmark', 82018: 'landmark',  # US Capitol, US Supreme Court, White House, historic site
}
FALLBACK = {'school': 'School', 'ems_station': 'Ambulance Station', 'fire_station': 'Fire Station', 'police': 'Police Station',
            'prison': 'Jail', 'post_office': 'Post Office', 'hospital': 'Hospital', 'cemetery': 'Cemetery', 'campground': 'Campground',
            'trailhead': 'Trailhead', 'town_hall': 'Town Hall', 'ranger_station': 'Ranger Station'}
SMALL = {'a', 'an', 'and', 'at', 'by', 'de', 'del', 'for', 'in', 'la', 'of', 'on', 'or', 'the', 'to', 'y'}
ACRONYMS = {'EMS', 'VFD', 'FD', 'PD', 'USPS', 'HS', 'MS', 'ES', 'JHS', 'PS', 'IS', 'MS', 'K-8', 'ALS', 'BLS', 'VA', 'YMCA', 'NCT',
            'USFS', 'BLM', 'NPS', 'KOA', 'FFA', 'II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'US', 'U.S.', 'ISD',
            'USD', 'CUSD', 'UCLA', 'USC', 'SUNY', 'CUNY', 'MIT', 'NYC', 'NYPD', 'FDNY', 'LAPD', 'LAFD', 'SFFD', 'DC', 'HWT', 'RV',
            'VFW', 'AME', 'KIPP', 'STEM', 'PK', 'TK', 'HQ', 'EOC', 'CCC', 'ATV', 'OHV', 'NW', 'NE', 'SW', 'SE'}


# ---------------------------------------------------------------- download
class HttpFile(io.RawIOBase):
    """A remote file as a seekable read-only stream, one HTTP Range request per read."""
    def __init__(self, url):
        self.url, self.pos = url, 0
        self.size = int(urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60).headers['Content-Length'])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        for attempt in range(5):
            try:
                req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{end}'})
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def list_states():
    for attempt in range(4):
        try:
            xml = urllib.request.urlopen(f'{BUCKET}/?prefix={PREFIX}', timeout=60).read().decode()
            break
        except Exception as e:
            print(f'  listing {BUCKET}/{PREFIX}: {e}; retrying', flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        sys.exit(f'could not list {BUCKET}/{PREFIX} (use --no-download to build from the states already downloaded)')
    if '<IsTruncated>true</IsTruncated>' in xml:
        sys.exit('the state listing is longer than one page: add paging to list_states()')
    keys = re.findall(r'<Key>([^<]*_State_Shape\.zip)</Key>', xml)
    return [k[len(PREFIX) + len('STRUCT_'):-len('_State_Shape.zip')] for k in keys]


def fetch(state, refresh=False):
    dest = SRC / state
    if (dest / 'Struct_Point.dbf').exists() and not refresh:
        return state, 'have'
    url = f'{BUCKET}/{PREFIX}STRUCT_{state}_State_Shape.zip'
    z = zipfile.ZipFile(io.BufferedReader(HttpFile(url), 4 << 20))
    names = {i.filename: i for i in z.infolist()}
    dest.mkdir(parents=True, exist_ok=True)
    got = 0
    for m in [*WANT, f'STRUCT_{state}_State_Shape.xml']:
        if m in names:
            (dest / (Path(m).name + '.part')).write_bytes(z.read(m))
            got += names[m].compress_size
    for m in [*WANT, f'STRUCT_{state}_State_Shape.xml']:  # rename last, so a half-done state is fetched again
        p = dest / (Path(m).name + '.part')
        if p.exists():
            p.replace(dest / Path(m).name)
    return state, f'{got / 1e6:.1f} MB' if (dest / 'Struct_Point.dbf').exists() else 'no point layer'


# ---------------------------------------------------------------- read shapefile (points only)
def read_points(folder):
    """Yield dicts of the .dbf fields plus 'lon', 'lat' for each point record."""
    dbf = (folder / 'Struct_Point.dbf').read_bytes()
    nrec, hlen, rlen = struct.unpack('<IHH', dbf[4:12])
    fields, off = [], 32
    while dbf[off] != 0x0D:
        name = dbf[off:off + 11].split(b'\0')[0].decode()
        fields.append((name, chr(dbf[off + 11]), dbf[off + 16]))
        off += 32
    cp = 'utf-8'
    if (folder / 'Struct_Point.cpg').exists():
        cp = (folder / 'Struct_Point.cpg').read_text().strip() or cp
    shp = (folder / 'Struct_Point.shp').read_bytes()
    shx = (folder / 'Struct_Point.shx').read_bytes()
    for i in range(nrec):
        rec = dbf[hlen + i * rlen: hlen + (i + 1) * rlen]
        if rec[:1] == b'*':  # deleted
            continue
        row, p = {}, 1
        for name, typ, ln in fields:
            raw = rec[p:p + ln]
            p += ln
            try:
                v = raw.decode(cp).strip()
            except UnicodeDecodeError:
                v = raw.decode('latin-1').strip()
            row[name.lower()] = v
        so = struct.unpack('>i', shx[100 + i * 8:104 + i * 8])[0] * 2
        stype = struct.unpack('<i', shp[so + 8:so + 12])[0]
        if stype in (1, 11, 21):
            row['lon'], row['lat'] = struct.unpack('<dd', shp[so + 12:so + 28])
            yield row


# ---------------------------------------------------------------- names
def word_case(w, first):
    core = w.strip('()",.')
    if core.upper() in ACRONYMS:
        return w.upper()
    if re.fullmatch(r'\d+(st|nd|rd|th)', w, re.I):
        return w.lower()
    if not first and w.lower() in SMALL:
        return w.lower()
    t = '-'.join(x[:1].upper() + x[1:].lower() for x in w.split('-'))
    t = re.sub(r"\bMc([a-z])", lambda m: 'Mc' + m.group(1).upper(), t)
    t = re.sub(r"\bO'([a-z])", lambda m: "O'" + m.group(1).upper(), t)
    return re.sub(r"'S\b", "'s", t)


def tidy(name):
    """game/serve.py tidy_name rules (collapse spaces, fix ALL CAPS and lower case, "'S" -> "'s", drop Inc/LLC) but keep
    numbers: here they are station and school numbers (Fire Station 3, PS 87), not store numbers."""
    n = ' '.join(name.replace(' ', ' ').split()).strip(' -#,;')
    if not n:
        return ''
    letters = [c for c in n if c.isalpha()]
    if letters and (all(c.isupper() for c in letters) or all(c.islower() for c in letters)):
        n = ' '.join(word_case(w, i == 0) for i, w in enumerate(n.split(' ')))
    n = re.sub(r"'S\b", "'s", n)
    return re.sub(r',?\s+(Inc|Llc|Co)\.?$', '', n, flags=re.I)


def cell(v):
    return math.floor(v * 20)


# ---------------------------------------------------------------- build
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-download', action='store_true')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--refresh', action='store_true', help='download every state again')
    ap.add_argument('--allow-missing', action='store_true', help='build even when some states failed to download')
    a = ap.parse_args()
    failed = []
    t0 = time.time()
    SRC.mkdir(parents=True, exist_ok=True)
    if not a.no_download:
        states = list_states()
        print(f'{len(states)} states and territories listed', flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(fetch, s, a.refresh): s for s in states}
            for f in futs:
                try:
                    s, msg = f.result()
                    print(f'  {s}: {msg}', flush=True)
                except Exception as e:  # keep going; a rerun fetches what is missing
                    print(f'  {futs[f]}: FAILED {e!r}', flush=True)
                    failed.append(futs[f])
        if failed and not a.allow_missing:
            sys.exit(f'{len(failed)} states failed ({", ".join(failed)}); rerun to fetch them, or pass --allow-missing. '
                     f'{OUT.name} was not changed.')

    seen, rows, skipped, per_state = set(), [], collections.Counter(), {}
    for folder in sorted(p for p in SRC.iterdir() if (p / 'Struct_Point.dbf').exists()):
        n0 = len(rows)
        for r in read_points(folder):
            try:
                fc = int(float(r.get('fcode') or 0))
            except ValueError:
                fc = 0
            cls = FCODES.get(fc)
            if not cls:
                skipped[fc] += 1
                continue
            la, lo = r['lat'], r['lon']
            if not (-90 <= la <= 90 and -180 <= lo <= 180) or (la == 0 and lo == 0):
                continue
            name = tidy(r.get('name', ''))
            if cls in ('campground', 'trailhead', 'picnic_site'):  # recreation.gov-style abbreviations: 'Iron Creek Cg', 'Cave Creek Th'
                name = re.sub(r'\s+(Cg|Cgd)$', ' Campground', re.sub(r'\s+(Th|Trhd|Thd)$', ' Trailhead', name))
            name = name or FALLBACK.get(cls, '')
            key = (cls, name.lower(), round(la, 4), round(lo, 4))
            if not name or key in seen:
                continue
            seen.add(key)
            rows.append((cls, name, round(la, 6), round(lo, 6), CONF, cell(lo), cell(la)))
        per_state[folder.name] = len(rows) - n0
    if skipped:
        print('unmapped FCODEs (dropped):', dict(skipped.most_common()))

    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    db.executemany('INSERT INTO place VALUES (?,?,?,?,?,?,?)', rows)
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('count', str(len(rows))),
        ('source', f'USGS National Structures Dataset (The National Map), Struct_Point from {len(per_state)} state/territory '
                   f'Shape files at {BUCKET}/{PREFIX}'),
        ('licence', 'Public domain (US federal government work, USGS)'),
        ('built', time.strftime('%Y-%m-%d')),
        ('states', ','.join(per_state))])
    db.commit(); db.close()
    tmp.replace(OUT)
    by = collections.Counter(r[0] for r in rows)
    print(f'{len(rows):,} places from {len(per_state)} states in {time.time() - t0:.0f}s:',
          ', '.join(f'{k} {v:,}' for k, v in by.most_common()))
    if failed:
        print(f'WARNING: built without {len(failed)} states that failed to download: {", ".join(failed)}')


if __name__ == '__main__':
    main()
