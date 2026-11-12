"""Places the game needs, from Foursquare Open Source Places: derived/geo/places-fsq.sqlite.

  derived/buildenv/bin/python tools/build_places_fsq.py            # download the US subset (once), then build
  derived/buildenv/bin/python tools/build_places_fsq.py --refetch  # download again

OpenStreetMap, Overture and AllThePlaces cover chains well but miss much of the long tail: small and ethnic grocers,
co-ops, liquor and dollar stores, independent clinics, churches, farms, feed and gun shops. Foursquare OS Places
(Apache-2.0, https://opensource.foursquare.com/os-places/) has about 22M US rows and fills that gap. Its rows are
noisy, so this keeps only places that are not marked closed and were refreshed in 2022 or later, maps Foursquare's
category labels to the game's classes (OpenStreetMap-style names, plus new classes the game will use later) and
drops every other kind (restaurants, offices, salons...). conf is 0.8 when refreshed in 2024 or later, else 0.55, so
the merge in game/serve.py can prefer Overture, AllThePlaces and the federal registries. Only the name, kind and
point are kept: no street addresses, phone numbers, e-mails or social handles.

Source: the ungated source.coop mirror of the 2025-02-06 release,
s3://us-west-2.opendata.source.coop/fused/fsq-os-places/2025-02-06/places/*.parquet (anonymous, us-west-2), read
with DuckDB httpfs. The US rows (only the columns used here) are saved once to
derived/geo/sources/fsq/fsq-us-<release>.parquet. Newer releases are on Hugging Face
(huggingface.co/datasets/foursquare/fsq-os-places) behind a click-through the user has to accept themselves.

Personal data: clinics named after a doctor ('Jane Doe, MD') and farms, wells and stables that carry only a family or
person's name ('McPeek Farm', 'Nelson Kevin') are left out, since those are usually someone's home. A farm stays when its
name says it sells to the public (market, stand, orchard, u-pick, creamery...).

Licence: Apache-2.0. Shipping the built file requires the Apache-2.0 licence text and Foursquare's notice (attribution:
"Foursquare Open Source Places", Copyright 2024 Foursquare Labs, Inc.). The builder saves both next to the download:
derived/geo/sources/fsq/LICENSE-2.0.txt and README-mirror.md (the mirror's licence statement).
"""
import argparse, os, re, sqlite3, time, urllib.request
from pathlib import Path

import duckdb

from build_places_overture import doctor_named, PERSON  # same rules for doctors' own listings

HERE = Path(__file__).resolve().parent.parent
SRC_DIR = HERE / 'derived/geo/sources/fsq'
OUT = HERE / 'derived/geo/places-fsq.sqlite'
MIRROR = 's3://us-west-2.opendata.source.coop/fused/fsq-os-places/{release}/places/*.parquet'

# Foursquare category (last part of the label, e.g. 'Retail > Hardware Store' -> 'Hardware Store') -> the game's class.
# A place takes the class of its first mapped label (Foursquare lists the primary category first).
CLASSES = {
    'Supermarket': 'supermarket', 'Grocery Store': 'supermarket', 'Organic Grocery': 'supermarket',
    'Health Food Store': 'supermarket', 'Warehouse or Wholesale Store': 'supermarket', 'Big Box Store': 'supermarket',
    'Asian Grocery Store': 'supermarket', 'International Grocery Store': 'supermarket', 'Ethnic Grocery Store': 'supermarket',
    'Convenience Store': 'convenience', 'Discount Store': 'convenience', 'Liquor Store': 'convenience',
    'Hardware Store': 'hardware', 'Home Improvement Store': 'hardware', 'Lumber Yard': 'hardware', 'Building Supply Store': 'hardware',
    'Fuel Station': 'fuel', 'Truck Stop': 'fuel',
    'Pharmacy': 'pharmacy', 'Drugstore': 'pharmacy',
    'Urgent Care Center': 'clinic', 'Healthcare Clinic': 'clinic', 'Medical Center': 'clinic', "Doctor's Office": 'clinic',
    'Family Medicine Doctor': 'clinic', 'Internal Medicine Doctor': 'clinic', 'Pediatrician': 'clinic', 'Physician': 'clinic',
    "Women's Health Clinic": 'clinic', 'Maternity Clinic': 'clinic',
    'Hospital': 'hospital', "Children's Hospital": 'hospital', 'Emergency Room': 'hospital',
    'Fire Station': 'fire_station', 'Police Station': 'police', 'Ambulance Service': 'ems_station', 'Rescue Service': 'ems_station',
    'Community Center': 'community_centre', 'Library': 'library', 'Homeless Shelter': 'shelter',
    'Church': 'place_of_worship', 'Mosque': 'place_of_worship', 'Synagogue': 'place_of_worship', 'Temple': 'place_of_worship',
    'Buddhist Temple': 'place_of_worship', 'Hindu Temple': 'place_of_worship', 'Sikh Temple': 'place_of_worship',
    'Kingdom Hall': 'place_of_worship', 'Spiritual Center': 'place_of_worship',
    'Primary and Secondary School': 'school', 'Elementary School': 'school', 'Middle School': 'school', 'High School': 'school',
    'Private School': 'school',
    'Nursing Home': 'nursing_home', 'Assisted Living': 'nursing_home', 'Retirement Home': 'nursing_home',
    'Post Office': 'post_office', 'City Hall': 'town_hall', 'Town Hall': 'town_hall',
    'Food Bank': 'food_bank', 'Food Pantry': 'food_bank', 'Soup Kitchen': 'food_bank',
    'Petroleum Supplier': 'fuel_depot',
    'Car Parts and Accessories': 'auto_parts',
    'Outdoor Supply Store': 'outdoor_store', 'Sporting Goods Retail': 'outdoor_store', 'Fishing Store': 'outdoor_store',
    'Hunting Supply Store': 'outdoor_store', 'Gun Store': 'gun_shop',
    'Garden Center': 'farm_supply', 'Farm Supply Store': 'farm_supply', 'Feed Store': 'farm_supply',
    'Equipment Rental Service': 'equipment_rental', 'Veterinarian': 'vet',
    'Farm': 'farm', 'Farmers Market': 'farmers_market', 'Campground': 'campground',
    'Lake': 'water_body', 'Reservoir': 'water_body', 'Dam': 'dam', 'Well': 'well',
    'Fishing Area': 'fishing_access', 'Boat Launch': 'fishing_access',
}
# Categories whose rows are mixed: keep a row only when its name fits (e.g. 'Petroleum Supplier' is mostly pipelines and
# oil exploration; 'Discount Store' includes Nordstrom Rack; 'Well' includes well drillers).
GATE = {
    'Discount Store': (re.compile(r'dollar|\b99\b|bargain|grocer|food|market|save|deal', re.I), None),
    'Spiritual Center': (re.compile(r'church|chapel|parish|cathedral|temple|mosque|masjid|synagogue|congregation|fellowship|ministr|abbey|gurdwara', re.I),
                         re.compile(r'cemet|festival|float|camp\b|school|thrift', re.I)),
    'Petroleum Supplier': (re.compile(r'fuel|\boil\b|propane|petroleum|heating|\bgas\b|diesel|bulk plant', re.I),
                           re.compile(r'pipe ?line|explor|geophys|mineral|production|operating|drilling|well serv|royalt|midstream|transmission|metering|'
                                      r'field|tools?\b|resources|service|equipment|land\b|lease', re.I)),
    'Well': (re.compile(r'\bwell\b|\bspring\b', re.I),
             re.compile(r'drill|service|water tower|sewage|pump|mechani|\boil\b|o&g|gas\b|museum|site\b|works|watering', re.I)),
    'Homeless Shelter': (re.compile(r'shelter|mission|rescue|homeless|haven|salvation army|samaritan|\binn\b|house of|refuge', re.I), None),
    'Lake': (re.compile(r'lake|pond|reservoir|lagoon', re.I), re.compile(r'apartment|condo|estates|village|subdivision|club|park\b|preserve|refuge', re.I)),
    'Reservoir': (re.compile(r'lake|reservoir|pond', re.I), None),
    'Garden Center': (re.compile(r'garden|nurser|greenhouse|feed|farm|seed|plant|landscape supply|orchard|grower', re.I), None),
    'Health Food Store': (re.compile(r'.'), re.compile(r'\bgnc\b|vitamin|nutrition|supplement|smoothie|juice|protein|cbd|kratom', re.I)),
    'Sporting Goods Retail': (re.compile(r'.'), re.compile(r'hockey|golf|champs|finish line|foot ?locker|footwear|shoe|sneaker|jersey|dance|skate|tennis|'
                                                         r'lacrosse|soccer|running|yoga|swim|bowling|nike|adidas|under armour|lululemon|\bfans?\b|team', re.I)),
}
# Every category of a class gets these names thrown out: car dealers and garages filed as fuel stations, contractors filed
# as hardware stores, offices filed as churches.
CLASS_BAD = {
    'fuel': re.compile(r'chevrolet|chevy|\bford\b|toyota|honda|mazda|porsche|nissan|dodge|jeep|chrysler|\bram\b|\bkia\b|hyundai|\bbmw\b|audi|lexus|'
                       r'subaru|buick|\bgmc\b|cadillac|volkswagen|\bvw\b|volvo|mercedes|infiniti|acura|lincoln|motors\b|auto (sales|mall|group)|'
                       r'dealer|midas|pep boys|lube|oil change|jiffy|valvoline|car wash|tire|repair|collision|body shop|automotive|meineke|'
                       r'firestone|goodyear|towing|rental', re.I),
    'hardware': re.compile(r'remodel|roofing|siding|contractor|renovation|kitchen (and|&) bath|cabinet|countertop|flooring|carpet|windows? (and|&) doors?', re.I),
    'place_of_worship': re.compile(r'financ|production|insurance|\bdept\b|services?$|realty|\bllc\b|consult', re.I),
    'auto_parts': re.compile(r'glass|tint|wheels? (and|&) tire|\brims?\b|audio|stereo|detail', re.I),
    'supermarket': re.compile(r'\bgnc\b|vitamin shoppe|\bpharmacy\b', re.I),
}
HOSPITAL_OK = re.compile(r'hospital|medical cent|emergency|\ber\b|health system', re.I)  # as NAME_OK['hospital'] in game/serve.py
CLINIC_OK = re.compile(r'urgent|clinic|medical cent|health cent|immediate care|express care|walk.?in|family (medicine|practice|health)', re.I)
# Clinic-like categories hold dentists, imaging and labs too; the game wants places that treat people (same idea as NAME_BAD
# in game/serve.py).
CLINIC_BAD = re.compile(r'radiolog|imaging|dermatolog|research|laborator|\blab\b|dental|dentist|orthodont|veterinar|animal|hormone|'
                        r'foot|podiatr|plastic surg|cosmetic|med ?spa|dialysis|davita|endoscop|blood|plasma|sleep|vein|weight loss|'
                        r'chiropract|physical therapy|billing|administrat|optom|vision|eye\b|hearing|lasik|fertility|surgery center|'
                        r'x-?ray|oncolog|cancer|wound|hyperbaric|occupational|rehab|urolog|\bent\b|ear,? nose|oral surg|detox|addiction|'
                        r'psych|\bph\.?d\b|counsel|therap|wellness|orthop|spine|cardiolog|neurolog|allerg|gastro|gyn|cranial|'
                        r'speech|audiolog|massage|acupunct|ketamine|revitalist|infusion|hospice|home health|aesthetic|botox|laser|'
                        r'patholog|diagnostic|\bmri\b|ultrasound|mammo|biopsy|sports medicine|pain (management|clinic|center)', re.I)
# A street address inside a name ('Dr Fritz 25500 Meadowbrook Rd Novi'): cut it and what follows.
ADDRESS_IN = re.compile(r'\s*(\bat\b)?[-,@]?\s*\b\d{3,6}\s+([\w.]+\s+){1,3}(st|street|rd|road|ave|avenue|dr|drive|blvd|hwy|highway|pkwy|'
                        r'freeway|fwy|tpke|turnpike|pike|ln|lane)\b.*$', re.I)
# Names that are only a street number and a word or two ('914 Hartford Tpke', '8840 W Sunset') or a room number.
BARE_NUMBER = re.compile(r'^(room\b|\d{3,6}\s+(?!.*(pharm|market|grocer|food|church|school|clinic|fire|police|gas|fuel|hardware|store|shop|mart|'
                         r'liquor|deli|farm|feed|library|post office|hospital|urgent))(\S+\s*){1,3}$)', re.I)
# Kinds Foursquare has no category for, found by name in any listing: food banks are filed as non-profits or churches,
# propane dealers as fuel stations or 'Miscellaneous Store', feed stores as hardware or pet stores.
BY_NAME = [('food_bank', re.compile(r'food (bank|pantry|pantries|shelf|shelves|closet)|soup kitchen', re.I), None),
           ('propane', re.compile(r'propane|\bLP gas\b|\bLPG\b', re.I), re.compile(r'grill|bbq|restaurant', re.I)),
           ('farm_supply', re.compile(r'\bfeeds?\b|feed (and|&) seed|farm (supply|store)|\bco-?op\b.*(farm|feed|grain|ag)', re.I),
            re.compile(r'feed ?back|news ?feed|feed (the|my|our|a|every|his)\b|hungry|restaurant|cafe|bar\b', re.I))]
BY_NAME_RE = '|'.join(f'({r.pattern})' for _, r, _ in BY_NAME)
# Virtual or non-place listings that carry a store category: pickup lockers, delivery-only kitchens, ATMs, kiosks.
NAME_BAD = re.compile(r'\b(pick ?up|delivery|deliveries|locker|atm|kiosk|redbox|coinstar|amazon hub|bitcoin|vending)\b', re.I)
# A bare street address as a name ('12345 Main St') is often someone's home; drop it.
ADDRESS = re.compile(r'^\d+[a-z]?\s+(\w+\s+){0,4}(st|street|rd|road|ave|avenue|dr|drive|ln|lane|ct|court|blvd|way|hwy|pl|place|cir|circle|trl|pkwy)\.?$', re.I)


# a farm open to the public says so; the rest are family farms, i.e. homes
FARM_PUBLIC = re.compile(r'market|stand\b|u-?pick|pick your own|\bpyo\b|orchard|store|shop\b|creamery|winery|vineyard|cider|berr|pumpkin|'
                         r'produce|\bcsa\b|farmers|nursery|greenhouse|garden|meats?\b|butcher|eggs\b|honey|apiar|maple|christmas|tree farm|'
                         r'organic|co-?op|corn maze|petting|agri|harvest|fresh|sugar ?house|bakery|cheese|dairy bar|ice cream|flower', re.I)
FAMILY = re.compile(r"^(the )?([A-Z][a-z'-]+\.? ){1,3}(family )?(farms?|ranch|homestead|acres|place|stables?|well)$|^([A-Z][a-z'-]+ ){0,2}[A-Z][a-z'-]+$")
LICENCE_FILES = [('https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/fused/fsq-os-places/README.md', 'README-mirror.md'),
                 ('https://www.apache.org/licenses/LICENSE-2.0.txt', 'LICENSE-2.0.txt')]


def private(cls, n):
    """Names that point at a person or their home rather than a place open to the public."""
    if cls in ('clinic', 'hospital'):
        return doctor_named(n)
    if cls == 'farm':
        return not FARM_PUBLIC.search(n)
    if cls in ('well', 'spring', 'water_body', 'campground', 'fishing_access'):
        return bool(FAMILY.match(n) and not re.search(r'lake|pond|spring|creek|river|park|public|state|county|city', n, re.I)) or bool(PERSON.match(n))
    return False


def tidy_name(n):
    """Same rules as game/serve.py's tidy_name: 'KROGER  632' -> 'Kroger', 'Walgreens #04512' -> 'Walgreens'."""
    n = re.sub(r'\s*#\s*\d+[A-Za-z]?$', '', ' '.join(n.split()))  # 'Súper Amigo #2'
    n = re.sub(r'(\s+(#\s*)?[A-Za-z]{0,3}-?\d{2,}[A-Za-z]?)+$', '', n).strip(' -#,|')
    if n.isupper() or n.islower():
        n = n.title()
    return re.sub(r"'S\b", "'s", re.sub(r'\s+(Inc|Llc|Co)\.?$', '', n, flags=re.I))


def cell(v):
    return int(v * 20) if v >= 0 else int(v * 20) - 1  # floor(v * 20): a grid of 0.05 degrees for nearby lookups


def fetch(release, path):
    """US rows of one release, only the columns used here, to a local parquet (about 2 GB, a few minutes)."""
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    tmp = path.with_suffix('.tmp')
    c.execute(f"""COPY (SELECT fsq_place_id, name, latitude, longitude, region, date_created, date_refreshed, date_closed,
                               fsq_category_ids, fsq_category_labels
                        FROM read_parquet('{MIRROR.format(release=release)}') WHERE country = 'US')
                  TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)""")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', default='2025-02-06')
    ap.add_argument('--refetch', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    for url, name in LICENCE_FILES:  # the licence and notice that must travel with the data
        if not (SRC_DIR / name).exists():
            with urllib.request.urlopen(url, timeout=60) as r:
                (SRC_DIR / name).write_bytes(r.read())
    src = SRC_DIR / f'fsq-us-{a.release}.parquet'
    if a.refetch or not src.exists():
        print(f'downloading US places of {a.release} to {src}', flush=True)
        fetch(a.release, src)
    c = duckdb.connect()
    c.execute('CREATE TEMP TABLE cat(leaf VARCHAR, cls VARCHAR)')
    c.executemany('INSERT INTO cat VALUES (?, ?)', list(CLASSES.items()))
    # first mapped label per place (labels look like 'Retail > Food and Beverage Retail > Grocery Store'), plus places of any
    # category whose name says food bank, propane or feed store
    cur = c.execute(f"""
        WITH p AS (SELECT fsq_place_id id, name, latitude lat, longitude lon, date_refreshed,
                          unnest(fsq_category_labels) AS lbl, generate_subscripts(fsq_category_labels, 1) AS i
                   FROM read_parquet('{src}')
                   WHERE date_closed IS NULL AND date_refreshed >= '2022-01-01' AND name IS NOT NULL
                     AND latitude BETWEEN 17 AND 72 AND (longitude BETWEEN -180 AND -64 OR longitude > 170))
        SELECT arg_min(cat.cls, CASE WHEN cat.cls IS NULL THEN NULL ELSE p.i END), arg_min(cat.leaf, CASE WHEN cat.cls IS NULL THEN NULL ELSE p.i END),
               any_value(p.name), round(any_value(p.lat), 6), round(any_value(p.lon), 6),
               CASE WHEN any_value(p.date_refreshed) >= '2024-01-01' THEN 0.8::DOUBLE ELSE 0.55::DOUBLE END
        FROM p LEFT JOIN cat ON cat.leaf = trim(regexp_extract(p.lbl, '[^>]+$'))
        GROUP BY p.id
        HAVING count(cat.cls) > 0 OR regexp_matches(any_value(p.name), ?)""", [BY_NAME_RE])
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    seen, total, dropped = set(), 0, 0
    while rows := cur.fetchmany(200_000):
        out = []
        for cls, leaf, name, la, lo, cf in rows:
            n = tidy_name(ADDRESS_IN.sub('', name))
            for c2, good, bad in BY_NAME:
                if good.search(n) and not (bad and bad.search(n)) and cls not in ('hospital', 'school', 'clinic'):
                    cls = c2
                    break
            else:
                if leaf in GATE and not (GATE[leaf][0].search(n) and not (GATE[leaf][1] and GATE[leaf][1].search(n))):
                    cls = None
            if cls == 'hospital' and not HOSPITAL_OK.search(n):
                cls = 'clinic' if CLINIC_OK.search(n) else None  # 'Beaumont Urgent Care', 'Ascension ... Internists' filed as hospitals
            if cls in ('clinic', 'hospital') and CLINIC_BAD.search(n) or cls in CLASS_BAD and CLASS_BAD[cls].search(n):
                cls = None
            if cls is None:
                dropped += 1
                continue
            key = (cls, n.lower(), round(la, 3), round(lo, 3))  # Foursquare often lists one place twice
            if len(n) < 2 or NAME_BAD.search(n) or ADDRESS.match(n) or BARE_NUMBER.match(n) or key in seen or private(cls, n):
                dropped += 1
                continue
            seen.add(key)
            out.append((cls, n, la, lo, cf, cell(lo), cell(la)))
        db.executemany('INSERT INTO place VALUES (?,?,?,?,?,?,?)', out)
        total += len(out)
        print(f'{total:,} places ({dropped:,} dropped), {time.time() - t0:.0f}s', flush=True)
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('count', str(total)), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
        ('source', f'Foursquare Open Source Places {a.release} (source.coop mirror), US, open, refreshed 2022+'),
        ('licence', 'Apache-2.0 (Copyright 2024 Foursquare Labs, Inc.); attribution: Foursquare Open Source Places; '
                    'ship with sources/fsq/LICENSE-2.0.txt and README-mirror.md')])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'done: {total:,} places in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
