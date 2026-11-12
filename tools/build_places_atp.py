"""Chain stores and services from AllThePlaces: derived/geo/places-atp.sqlite.

  derived/buildenv/bin/python tools/build_places_atp.py [--zip derived/geo/sources/atp/output.zip] [--workers 16] [--refresh]

AllThePlaces (https://www.alltheplaces.xyz, CC0 1.0, no conditions) scrapes brand store locators every week, so it has
nearly every branded supermarket, dollar store, gas station, pharmacy, hardware store, auto parts store, farm store,
propane exchange, equipment rental yard, urgent care and vet in the US, at the store's own coordinates. OpenStreetMap
and Overture both miss many of these in suburbs (around Novi, Michigan ATP has three Krogers, a Home Depot, an Ace,
Sunbelt Rentals and a dozen gas stations). Keeps US features whose OpenStreetMap-style tags map to a game class (see
classify()); skips infrastructure spiders (trees, poles, manholes, post boxes), untagged points, closed or planned
stores and non-store sub-departments. A store's own fuel station and pharmacy stay as separate rows of their own class,
but repeats of one brand and class within 50 m become one row. Names are the brand (no store numbers or city
prefixes). conf 0.9. Same table as tools/build_places_overture.py so game/serve.py can merge them.

The weekly run is one zip of per-spider GeoJSON files (about 3.1 GB; the parquet file is 404). If --zip is missing it
is downloaded from https://data.alltheplaces.xyz/runs/latest.json -> output_url to that path (--refresh downloads the
latest run again). The run id is saved next to the zip as <zip>.run.json only once the zip is complete, so meta names
the run that is really on disk.
"""
import argparse, json, math, multiprocessing as mp, re, sqlite3, time, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/atp'
OUT = HERE / 'derived/geo/places-atp.sqlite'
TODAY = time.strftime('%Y-%m-%d')

# Spiders kept for a tag value only when listed (the rest of that tag is fashion, car dealers, trucks or welding gas).
SPORTS_OK = {'dicks_sporting_goods', 'academy_us', 'dunhams_sports_us', 'sun_and_ski_sports_us', 'big_5_sporting_goods_us', 'scheels_us'}
CAR_PARTS_SKIP = re.compile(r'toyota|hyundai|cadillac|honda|ford|chevrolet|nissan|kia|subaru')
RENTAL = {'plant_hire': 'equipment_rental', 'tool_hire': 'equipment_rental'}
RENTAL_SKIP = {'scania', 'willscot_ca_us'}
TRUCK_RENTAL = {'uhaul', 'penske', 'budget_truck_rental_us', 'ryder_us'}
FACILITY_HOME = {'nursing_home', 'assisted_living'}
HOME_SPIDERS = {'brookdale_us', 'genesis_rehab_us', 'careone_us', 'brandywine_living_us'}
HOSPITAL_NAME = re.compile(r'hospital|medical cent|emergency|\ber\b', re.I)  # game/serve.py NAME_OK['hospital']
NAME_BAD = re.compile(r'radiolog|imaging|dermatolog|research|laborator|dental|orthodont|hormone|footcare|podiatr|plastic surg|'
                      r'cosmetic|med ?spa|prosthet|orthotic|physical therapy|rehab|sleep|lab services|behavioral|hearing|vision|eye ', re.I)
CLINIC_SPIDERS = {'afc_urgent_care', 'gohealth_urgent_care_us', 'nextcare_us', 'nextcare', 'carbon_health_us', 'one_medical_us',
                  'concentra_us', 'department_veterans_affairs', 'planned_parenthood', 'minuteclinic_us'}  # walk-in care, any name
CLINIC_SKIP = {'hangerclinic_us', 'touchstone_medical_imaging_us', 'national_seating_mobility'}
CLINIC_NAME = re.compile(r'urgent|immediate care|express care|walk.?in|clinic\b|primary care|family (medicine|practice|health|physicians)|'
                         r'internal medicine|medical (center|centre|group|plaza|office)|health (center|centre)|community health', re.I)
NAME_BAD2 = re.compile(r'cancer|oncolog|surg|spine|gastro|cardio|neuro|ortho|urolog|head & neck|midwi|adult day|day health|'
                       r"men's health|women's|wound|infusion|dialysis|psych|pain|allerg|diabet|vein|bariatric|fertility|hospice", re.I)
# Names that say what the place is: kept for independent co-op members ('Great Lakes Ace', 'Bryant Hardware'); other names
# under a brand are usually a city or mall ('Novi', 'New York - Columbus Ave') and the brand reads better.
TYPE_WORD = re.compile(r'hardware|\bace\b|lumber|supply|feed|farm|market|grocer|foods?\b|super|pharm|drug|apothec|fuel|gas\b|'
                       r'station|oil|mart\b|store|shop|library|clinic|care\b|medical|health|hospital|propane|rental|auto|parts', re.I)
CLOSED = re.compile(r'\b(closed|coming soon|opening soon|now hiring|permanently)\b', re.I)


def classify(p, spider):
    """OpenStreetMap-style tags of one AllThePlaces feature -> game class, or None to skip."""
    shop, amen, hc = p.get('shop'), p.get('amenity'), p.get('healthcare')
    if shop in ('supermarket', 'wholesale'):
        return 'supermarket'
    if shop in ('convenience', 'variety_store'):
        return 'convenience'
    if shop in ('doityourself', 'hardware') or (shop == 'trade' and 'lumber' in spider) or spider == 'mccoys':
        return 'hardware'
    if shop == 'car_parts' and not CAR_PARTS_SKIP.search(spider):
        return 'auto_parts'
    if shop == 'outdoor' and spider != 'fjallraven' or (shop == 'sports' and spider in SPORTS_OK):
        return 'outdoor_store'
    if shop in ('agrarian', 'country_store'):
        return 'farm_supply'
    if shop == 'department_store' and spider in ('target_us', 'big_lots_us', 'bi_mart_us', 'runnings_us', 'kmart_us', 'sears_us'):
        return 'department_store'  # general merchandise (Target also sells groceries; its supermarket rows are tagged as such)
    if shop in RENTAL and spider not in RENTAL_SKIP:
        return RENTAL[shop]
    if spider in TRUCK_RENTAL or (shop == 'rental' and spider == 'penske'):
        return 'truck_rental'
    if spider == 'suburban_propane_us' or (amen == 'vending_machine' and (p.get('fuel:lpg') == 'yes' or p.get('vending') == 'gas')):
        return 'propane'
    if shop == 'water':
        return 'water_store'
    if amen == 'fuel':
        return 'fuel'
    if amen == 'pharmacy' or hc == 'pharmacy':
        return 'pharmacy'
    if amen == 'hospital' or hc == 'hospital':
        return 'hospital'
    if amen == 'clinic' or hc in ('clinic', 'urgent_care'):
        return 'clinic'
    if amen == 'veterinary':
        return 'vet'
    if amen == 'post_office' and spider == 'usps':
        return 'post_office'
    if amen == 'library' and (spider != 'worldcat' or (p.get('worldcat:type') == 'PUBLIC' and p.get('access') != 'private')):
        return 'library'
    if amen == 'community_centre' or (amen == 'social_facility' and p.get('social_facility') == 'outreach' and 'boys_and_girls' in spider):
        return 'community_centre'
    if amen == 'social_facility' and (p.get('social_facility') in FACILITY_HOME or spider in HOME_SPIDERS):
        return 'nursing_home'
    if amen == 'drinking_water':
        return 'drinking_water'
    return None


def tidy(n):
    """Same rules as game/serve.py tidy_name: no store numbers, sensible case, no Inc/LLC."""
    n = re.sub(r'(\s+(#\s*)?[A-Za-z]{0,3}-?\d{2,}[A-Za-z]?)+$', '', ' '.join(n.split())).strip(' -#,')
    if (n.isupper() and len(n) > 4) or n.islower():  # 'KROGER' -> 'Kroger', but 'BP' and 'REI' stay
        n = n.title()
    return re.sub(r"'S\b", "'s", re.sub(r',?\s+(Inc|Llc|Co)\.?$', '', n, flags=re.I))


def pick_name(p, cls):
    """The name a player sees: the brand (or the place's own name when it has no brand), never a store number or city."""
    name = (p.get('name') or '').split(' | ')[0].strip()
    brand = (p.get('brand') or p.get('operator') or '').strip()
    places = {(p.get('addr:city') or '').lower(), (p.get('branch') or '').lower()} - {''}
    if cls == 'post_office':
        town = (p.get('branch') or p.get('addr:city') or '').strip()
        return f'{tidy(town).title()} Post Office' if town else 'Post Office'
    if brand and cls != 'library' and (not name or brand.lower() in name.lower() or len(name) > 50 or re.search(r'\d{3,}', name) or name.lower() in places
                  or ' - ' in name or '(' in name or not TYPE_WORD.search(name)):
        name = brand  # 'Florence Sam's Club', 'Kroger Fuel Center 632', 'AmerGas Propane', 'Novi', 'Mark Twain' -> the brand
    if cls == 'propane' and 'propane' not in name.lower():
        name += ' Propane'
    return tidy(name) if name else ''


def point(g):
    """A feature's point: itself, or the mean of a line's or polygon's vertices."""
    if not g:
        return None
    t, c = g.get('type'), g.get('coordinates')
    if t == 'Point':
        return c[1], c[0]
    flat = []
    def walk(x):
        if x and isinstance(x[0], (int, float)):
            flat.append(x)
        else:
            for y in x or ():
                walk(y)
    walk(c)
    return (sum(v[1] for v in flat) / len(flat), sum(v[0] for v in flat) / len(flat)) if flat else None


def in_us(la, lo):
    return (17.5 <= la <= 50 and -125 <= lo <= -64.5) or (51 <= la <= 72 and -180 <= lo <= -129) or (18.5 <= la <= 23 and -161 <= lo <= -154) \
        or (13 <= la <= 21 and 144 <= lo <= 146.5) or (-15 <= la <= -10 and -171.5 <= lo <= -168)  # CONUS+PR/VI, AK, HI, GU/MP, AS


def read_spider(args):
    """One spider file -> ([(cls, name, lat, lon, brand_key)], bad_lines)."""
    zpath, member = args
    spider = member.rsplit('/', 1)[-1][:-len('.geojson')]
    rows, bad = [], 0
    with zipfile.ZipFile(zpath) as z, z.open(member) as f:
        for line in f:
            line = line.strip().rstrip(b',')
            if not line.startswith(b'{"type": "Feature"') and not line.startswith(b'{"type":"Feature"'):
                continue
            if b'"amenity"' not in line and b'"shop"' not in line and b'"healthcare"' not in line and spider not in TRUCK_RENTAL:
                continue  # trees, poles, addresses: no tags the game uses
            try:
                ft = json.loads(line)
            except ValueError:
                bad += 1
                continue
            p = ft.get('properties') or {}
            country = p.get('addr:country')
            if country not in (None, 'US', 'PR', 'VI', 'GU', 'AS', 'MP'):
                continue
            cls = classify(p, spider)
            if not cls:
                continue
            pt = point(ft.get('geometry'))
            if not pt or not in_us(*pt) or (country is None and re.search(r'_(ca|mx)$', spider)):
                continue
            if p.get('end_date') or (p.get('start_date') or '') > TODAY or p.get('opening_hours') in ('closed', 'off') \
                    or any(k.startswith(('disused:', 'was:', 'planned:', 'construction:')) for k in p) or CLOSED.search(p.get('name') or ''):
                continue
            name = pick_name(p, cls)
            if not name:
                continue
            if cls in ('clinic', 'hospital'):
                text = name + ' ' + (p.get('name') or '') + ' ' + (p.get('healthcare:speciality') or '')
                if spider in CLINIC_SKIP or NAME_BAD.search(text) or NAME_BAD2.search(text):
                    continue
                if cls == 'hospital' and not HOSPITAL_NAME.search(p.get('name') or name):
                    cls = 'clinic'  # health systems tag their outpatient offices as hospitals
                if cls == 'clinic' and spider not in CLINIC_SPIDERS and not p.get('urgent_care') and not CLINIC_NAME.search(text):
                    continue  # a specialist's office, not somewhere to walk in hurt
            rows.append((cls, name, round(pt[0], 6), round(pt[1], 6), p.get('brand:wikidata') or p.get('brand') or spider))
    return rows, bad


def dedupe(rows):
    """One row per brand and class within 50 m (a store's departments, the same store in two spiders)."""
    seen, out = {}, []
    for r in rows:
        cls, name, la, lo, bk = r
        ky, kx = int(la * 2000), int(lo * 2000)  # about 55 m cells
        dup = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for la2, lo2 in seen.get((cls, bk, ky + dy, kx + dx), ()):
                    if math.hypot(la - la2, (lo - lo2) * math.cos(math.radians(la))) * 111_000 < 50:
                        dup = True
        if not dup:
            seen.setdefault((cls, bk, ky, kx), []).append((la, lo))
            out.append(r)
    return out


def cell(v):
    return math.floor(v * 20)  # grid of 0.05 degrees for nearby lookups


def run_file(zpath):
    return zpath.with_name(zpath.name + '.run.json')


def download(dst):
    """The latest weekly run to dst; its run record is written only after the zip is complete."""
    with urllib.request.urlopen('https://data.alltheplaces.xyz/runs/latest.json', timeout=60) as r:
        run = json.load(r)
    dst.parent.mkdir(parents=True, exist_ok=True)
    print('downloading', run['output_url'], 'to', dst, flush=True)
    tmp = dst.with_name(dst.name + '.part')
    with urllib.request.urlopen(run['output_url'], timeout=300) as r, open(tmp, 'wb') as f:
        while b := r.read(1 << 22):
            f.write(b)
    zipfile.ZipFile(tmp).namelist()  # a truncated download fails here, before anything is replaced
    tmp.replace(dst)
    run_file(dst).write_text(json.dumps(run))
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', type=Path, default=SRC / 'output.zip')
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--refresh', action='store_true', help='download the latest weekly run again')
    a = ap.parse_args()
    t0 = time.time()
    zpath = download(a.zip) if a.refresh or not a.zip.exists() else a.zip
    run = 'unknown run'
    for f in (run_file(zpath), zpath.parent / 'latest.json'):  # latest.json: written by older versions of this script
        try:
            run = json.loads(f.read_text())['run_id']
            break
        except (OSError, ValueError, KeyError):
            pass
    members = [n for n in zipfile.ZipFile(zpath).namelist() if n.endswith('.geojson')]
    rows, bad = [], 0
    with mp.Pool(a.workers) as pool:
        for i, (r, b) in enumerate(pool.imap_unordered(read_spider, [(str(zpath), m) for m in members], chunksize=4)):
            rows += r
            bad += b
            if i % 500 == 0:
                print(f'{i:,}/{len(members):,} spiders, {len(rows):,} places, {time.time() - t0:.0f}s', flush=True)
    rows.sort(key=lambda r: (r[0], r[4], r[2], r[3]))
    kept = dedupe(rows)
    print(f'{len(rows):,} matched, {len(kept):,} after dedupe, {bad:,} unreadable lines', flush=True)
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    db.executemany('INSERT INTO place VALUES (?,?,?,?,0.9,?,?)', ((c, n, la, lo, cell(lo), cell(la)) for c, n, la, lo, _ in kept))
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [('count', str(len(kept))), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
                                                    ('source', f'AllThePlaces weekly run {run}'), ('licence', 'CC0 1.0')])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'done: {len(kept):,} places in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
