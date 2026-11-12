"""Buried fuel and gun dealers from two federal registries: derived/geo/places-fuel.sqlite.

  derived/buildenv/bin/python tools/build_places_fuel.py [--refresh]

When the power is out, the fuel that is left sits in underground tanks, and far more places have them than gas
stations: city public works yards, school bus garages, fuel distributors, fleet and construction yards, hospitals'
generator diesel. EPA's UST Finder (public domain, a US federal work; data from about 2018-2021) lists every
regulated underground storage tank facility. We keep the 186,000 or so with open (in-use) tanks: names that look like
a retail station become `fuel`, the rest `fuel_depot`. Facilities with a shell-company name and nothing else to go on
(most of which are corner gas stations run by an "Inc") are kept as `fuel` called "Gas Station" at lower confidence.

ATF's Federal Firearms Licensee list (public domain, geocoded by the ArcGIS layer below) gives `gun_shop`: dealers
(type 01), pawnbrokers (02) and ammunition makers (06), plus manufacturers and importers whose name says guns. Many
licensees work from home; we drop every licence geocoded to a residential building, and every one without a
business-sounding name, so the game never points players at a private house. Only licences that the geocoder put on a
commercial building are kept (a blank building type, about a third of all licences, is not known to be a shop, so it is
left out too), and only rooftop or parcel matches (not a ZIP code centre). Owner-named family farms and ranches with
their own fuel tank are left out of the UST rows for the same reason. Owner names, addresses and phone numbers are not
stored. Several owners at one identical point (a geocoder fallback) keep one row, the brand if there is one.

Raw pages are cached under derived/geo/sources/fuel/{ust,ffl}/ (pass --refresh to download them again). Same table as
tools/build_places_overture.py so game/serve.py can merge them.
"""
import argparse, json, re, sqlite3, time, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RAW = HERE / 'derived/geo/sources/fuel'
OUT = HERE / 'derived/geo/places-fuel.sqlite'
UST = ('https://services.arcgis.com/cJ9YHowT8TU7DUyn/ArcGIS/rest/services/UST_Finder_Feature_Layer_2eb/FeatureServer/0/query',
       'Open_USTs>0', 'OBJECTID', 'OBJECTID,Name,Latitude,Longitude,Open_USTs,LandUse')
FFL = ('https://services6.arcgis.com/PrP5ZtrES07DmVmv/arcgis/rest/services/Federal_Firearm_Licensees_locations/FeatureServer/0/query',
       '1=1', 'ObjectID', 'ObjectID,USER_LIC_TYPE,USER_LICENSE_NAME,USER_BUSINESS_NAME,StrucType,Addr_type,Score')

# --- fuel --------------------------------------------------------------------------------------------------------
BRANDS = [  # (pattern, name players see); first match wins
    (r'speedway', 'Speedway'), (r'marath[ao]n', 'Marathon'), (r'\bshell\b', 'Shell'), (r'\bbp\b|\bamoco\b', 'BP'),
    (r'sunoco', 'Sunoco'), (r'exxon', 'Exxon'), (r'\bmobil\b', 'Mobil'), (r'chevron', 'Chevron'), (r'texaco', 'Texaco'),
    (r'citgo', 'Citgo'), (r'valero', 'Valero'), (r'phillips ?66', 'Phillips 66'), (r'\bconoco', 'Conoco'), (r'sinclair', 'Sinclair'),
    (r'\bgulf\b', 'Gulf'), (r'circle ?k\b', 'Circle K'), (r'7[- ]?eleven', '7-Eleven'), (r'\bwawa\b', 'Wawa'), (r'sheetz', 'Sheetz'),
    (r'quik ?trip|\bqt\b', 'QuikTrip'), (r'race ?trac', 'RaceTrac'), (r"casey'?s", "Casey's"), (r'kwik ?trip|kwik ?star', 'Kwik Trip'),
    (r'kum ?(&|and) ?go', 'Kum & Go'), (r'\bpilot\b', 'Pilot'), (r'flying ?j', 'Flying J'), (r"\blove'?s (travel|country)", "Love's"),
    (r'travel ?cent(er|re)s? of america|\bta travel|travelcenters', 'TA Travel Center'), (r'\bholiday (station|stationstore)', 'Holiday'),
    (r'cenex', 'Cenex'), (r'\barco\b', 'Arco'), (r'murphy ?(usa|express|oil usa)', 'Murphy USA'), (r'costc?o', 'Costco Gas'),
    (r"sam'?s club", "Sam's Club Gas"), (r'kroger', 'Kroger Fuel'), (r'meijer', 'Meijer Gas'), (r'wal-?mart', 'Walmart Fuel'),
    (r'safeway', 'Safeway Fuel'), (r'fred meyer', 'Fred Meyer Fuel'), (r'hy-?vee', 'Hy-Vee Gas'), (r'get ?go\b', 'GetGo'),
    (r'cumberland farms', 'Cumberland Farms'), (r"stewart'?s shop", "Stewart's Shops"), (r'thorntons', 'Thorntons'),
    (r'maverik', 'Maverik'), (r'loaf ?n ?jug', "Loaf 'N Jug"), (r'mapco', 'Mapco'), (r'royal farms', 'Royal Farms'),
    (r"buc-?ee'?s", "Buc-ee's"), (r'\bstripes\b', 'Stripes'), (r"allsup'?s", "Allsup's"), (r'\bclark\b', 'Clark'),
    (r'\bbj\'?s', "BJ's Gas"), (r'\bheb\b|h-e-b', 'H-E-B Gas'), (r'giant eagle', 'GetGo'), (r'\bam ?pm\b', 'ampm'), (r'\bvalero\b', 'Valero'),
    (r'\bloves\b', "Love's"), (r'\bpetro\b.*stopping|petro stopping', 'Petro'), (r'\bkwik ?fill', 'Kwik Fill'), (r'\bspeedy', 'Speedy'),
    (r'\bucky', 'Rutter\'s'), (r'rutter', "Rutter's"), (r'\bsheetz', 'Sheetz'), (r'\bweigel', "Weigel's"), (r'\bpantry\b', 'The Pantry'),
    (r'united dairy farmers', 'United Dairy Farmers'), (r'flash foods', 'Flash Foods'), (r'\bcefco\b', 'Cefco'),
    (r"han-?dee hugo", "Han-Dee Hugo's"), (r'toot ?n ?totum', "Toot'n Totum"), (r'turkey hill', 'Turkey Hill'), (r'country fair', 'Country Fair'),
    (r'sudden service', 'Sudden Service'), (r'pacific pride', 'Pacific Pride'), (r'zip ?trip', 'Zip Trip'), (r'\bhop-?in\b', 'Hop-In'),
    (r'mega ?saver', 'Mega Saver'), (r'handi ?plus', 'Handi Plus'), (r'\bmarkette\b', 'Markette'), (r'lukoil', 'Lukoil'),
    (r'\braceway\b', 'Raceway'), (r'super ?america', 'Speedway'), (r'\byesway\b', 'Yesway'), (r'little general', 'Little General'),
    (r'\bspinx\b', 'Spinx'), (r'\bscotchman\b', 'Scotchman'), (r'terrible herbst', 'Terrible Herbst'), (r'\bhucks?\b', "Huck's"),
    (r'\bstinker\b', 'Stinker'), (r'\bjacksons\b', 'Jacksons'), (r'\bpar ?mar\b', 'Par Mar'), (r'mirabito', 'Mirabito'),
    (r'\boncue\b', 'OnCue'), (r'admiral petroleum|\badmiral\b', 'Admiral'), (r'kangaroo', 'Kangaroo Express'), (r'\bduchess\b', 'Duchess'),
    (r'\bstop ?(&|n|and) ?go\b', 'Stop & Go'), (r'\bxtra ?mart', 'Xtra Mart'), (r'\bgetty\b', 'Getty'), (r'\bsprint ?mart', 'Sprint Mart'),
]
# building owners, co-ops and condos with heating-oil tanks (most of the UST sites in New York City): homes, so left out
RESID = re.compile(r'realty|owners|tenants|housing|\bhouses\b|apartment|\bapts?\b|condo|residen|\bco-?op|cooperative|\bhoa\b|homeowner|'
                   r'\bmanor\b|\btowers?\b|\bterrace\b|\bgardens\b|\bmansion|\bdwelling|^\d+[-\d\s]*(\w+ )?(w|e|n|s|west|east|north|south)?\.? ?'
                   r'(\d+(st|nd|rd|th)|[a-z]+) (st|street|ave|avenue|av|pl|place|road|rd|blvd|boulevard|dr|drive|lane|ln|ct|court|terr?|pkwy|parkway)\b(?!.*&)', re.I)
BRANDS = [(re.compile(p, re.I), n) for p, n in BRANDS]
RETAIL = re.compile(r'\bgas\b|gasoline|\bfuel stop|fill.?up|food.?(&|and|n).?(gas|fuel)|\bmart\b|\bmarket\b|\bstation\b|\bpetro\b|'
                    r'quick ?stop|kwik|quik|\bstop\b|truck ?stop|travel (plaza|center|centre)|c-?store|convenience|service (station|center)|'
                    r'\bretail\b|\bfood ?store|\bexpress\b|\bfuel (center|centre|mart|station)|gas ?n|\bauto ?care\b', re.I)  # not 'tire': tyre shops' own tanks
DEPOT = re.compile(
    r'school|\bisd\b|\busd\b|transportation|\bbus\b|\bdpw\b|public (works|service)|\bcity of\b|\bcounty\b|\btownship\b|\btwp\b|village of|'
    r'town of|\bborough\b|state of|department|\bdept\b|\bdot\b|highway|road commission|hospital|medical|health|university|college|'
    r'academy|airport|aviation|\bair (base|national guard)|air force|\bafb\b|\bengine\b|\bladder\b|firehouse|fdny|nypd|police|sheriff|\bfire\b|\bems\b|ambulance|\bpark|golf|maintenance|garage|'
    r'fleet|depot|\byard|transit|utilit|electric|\bpower\b|energy|water|sewer|wastewater|sanitation|landfill|waste|construction|'
    r'contract|cement|concrete|asphalt|paving|excavat|aggregate|materials|quarry|gravel|\bsand\b|trucking|freight|logistic|transport|'
    r'\bcartage|\blines\b|express lines|moving|crane|rental|equipment|tractor|machinery|implement|mfg|manufactur|industr|plant\b|'
    r'products|steel|metal|chemical|refin|terminal|bulk|distribut|wholesale|jobber|\bfuels?\b|\boil\b|petroleum|propane|\bgas co|'
    r'farm|ranch|dairy|orchard|nursery|greenhouse|cooperative|\bco-?op\b|grain|elevator|feed|telephone|\bbell\b|verizon|at ?& ?t|'
    r'communicat|wireless|cellular|tower|postal|post office|usps|\bups\b|parcel|fedex|leasing|\brent|carmax|first student|student transport|centurylink|\bmci\b|fairpoint|frontier|qwest|windstream|army|navy|marine|national guard|armory|federal|\bu\.? ?s\.? |'
    r'government|courthouse|jail|correction|prison|tribe|tribal|\bnation\b|church|cemetery|dealer|motors|chevrolet|\bford\b|'
    r'toyota|honda|nissan|dodge|chrysler|jeep|subaru|hyundai|\bkia\b|buick|gmc|cadillac|lincoln|volkswagen|bmw|mercedes|imports|auto group|'
    r'automotive|collision|body shop|research|laborator|data ?cent|\bbank\b|hotel|resort|casino|marina|boat|harbor|port of|railroad|railway|'
    r'\brr\b|amtrak|bnsf|union pacific|csx|norfolk|landscap|lawn|\btree|forest|lumber|\bmill\b|\bmine\b|mining|cleaners|laundry|bakery|foods\b|'
    r'dairy|beverage|bottling|coca|pepsi|brewing|distill|packing|cold storage|warehouse|storage|center\b|facility|office|building|'
    r'apartments|condo|plaza|mall|club\b|country club|camp\b|\bski\b', re.I)
SHELL = re.compile(r'\b(inc|llc|l\.l\.c|corp|corporation|co|company|ltd|enterprises?|ventures?|group|holdings?|investments?|'
                   r'partners|properties|associates|brothers|bros|petroleum|management|mgmt|dba|lp|llp)\b\.?|&|\band\b|\bmile\b|^\d', re.I)
PERSON = re.compile(r"^[A-Z][a-z'.-]+,? [A-Z][a-z'.-]*\.?( [A-Z][a-z'.-]*\.?)?$")  # "John Smith", "Smith, John A": maybe a person
NAMED = re.compile(r"^[A-Z][a-z'-]+(,| [A-Z]\.? )")  # "Smith, John" or "John A Smith": surely a person
# a farm, ranch or orchard's own tank is nearly always at the family's home ('Brent Brooks Farm', 'Zutavern Ranch'): left out
# unless the name says it is a co-op, elevator or farm store open to the public
FARMISH = re.compile(r'\bfarms?\b|\branch(es)?\b|\bdair(y|ies)\b|\borchards?\b|\bnursery|\bgreenhouses?\b|\bvineyards?\b|\bacres\b|\bcattle\b|'
                     r'\bfeedlot|\bhogs?\b|\bpoultry\b|\blivestock\b', re.I)
FARM_BIZ = re.compile(r'co-?op|cooperative|elevator|grain|\bfeed|supply|store|market|center|equipment|implement|bureau|association|'
                      r'service|\bag\b|agri|chs\b|cenex|landus|\bmfa\b|southern states|country mark|growmark', re.I)


def tidy(n):
    """'KROGER  632' -> 'Kroger', "Sam'S Club #6657" -> "Sam's Club": game/serve.py's tidy_name plus a few UST/FFL habits."""
    n = re.sub(r'\((loc(ation)?|site|store|unit|fac(ility)?|id)\.?\s*(no\.?|#)?\s*[\w-]*\)', '', ' '.join(n.split()), flags=re.I)
    n = re.sub(r'\((lessee|lessor|owner|operator|former|closed|old)\)', '', n, flags=re.I)
    n = re.sub(r'\s*\((?=[^)]*\d)[^)]*\)', '', n)                          # "(M64252)"
    n = re.sub(r'_+\d*$', '', n).replace('_', ' ')                            # "Farmington_34"
    n = ' '.join(re.sub(r'\b(llc|inc|corp|co|ltd)\.?\s*[-/]\s*', ' ', n, flags=re.I).split())  # "Fuelco Us LLC-Farmington"
    n = re.sub(r'\s+(store|unit|site|loc(ation)?|no\.?|fac(ility)?)?\s*#\s*[\w-]+', '', n, flags=re.I)  # "Unit #2827", "# 8744"
    for _ in range(2):
        n = re.sub(r'(\s+(#\s*)?[A-Za-z]{0,3}-?\d{2,}[A-Za-z]?)+$', '', n).strip(' -#,.')
        n = re.sub(r'\s*-\s*(site|store|facility|location|loc)$|\s+no\.?$', '', n, flags=re.I)
        n = re.sub(r',?\s+(inc|llc|l\.l\.c|co|corp|corporation|ltd|lp|llp|pllc|pc)\.?$', '', n, flags=re.I).strip(' -#,.')
    if n.isupper() or n.islower():
        n = n.title()
    n = re.sub(r"'S\b", "'s", re.sub(r'(\d)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), n))
    return re.sub(r'\b(Dpw|Usa|Isd|Usd|Bp|Ii|Iii|Llc|Ems|Va|Ymca|Dot|Fdny|Nypd|Afb|Ups|Dps)\b', lambda m: m.group(0).upper(), n).strip()


def fuel_place(name, landuse=None):
    """(cls, name, conf) for a UST facility, or None to skip it."""
    raw = ' '.join((name or '').replace("''", "'").split())
    if not raw or raw.lower() in ('unknown', 'n/a', 'none', 'vacant'):
        return None
    dba = re.search(r'\bd/?b/?a\)?:?\s+(.+)', raw, re.I)  # "R A Davis Inc (dba) Davis BP (Lessee)" -> "Davis BP"
    shown = dba.group(1) if dba else raw
    for pat, brand in BRANDS:
        if pat.search(raw):
            return 'fuel', brand, 0.9
    if RESID.search(raw) or (FARMISH.search(raw) and not FARM_BIZ.search(raw)):
        return None
    numbered = re.search(r'#\s*\d|\b\d{3,}\s*$|\bstore\b', raw, re.I)  # chain stores carry a store number
    if re.search(r'\bretail\b', raw, re.I) or (RETAIL.search(raw) and not re.search(r'\bfuels\b|\boil\b|distribut|wholesale|bulk|terminal|school|county|city of|dpw|transport', raw, re.I)):
        n = tidy(shown)
        return 'fuel', (n if len(n) > 2 else 'Gas Station'), 0.9
    if re.match(r'^\d+(-\d+)?[a-z]?\s+[A-Za-z]', raw) and not re.search(r'&|\band\b|\bmile\b', raw, re.I):
        return None                                # named by its street address ("361 Central Park West"): often a home
    if DEPOT.search(raw):
        if re.match(r'(engine|ladder)( co(mpany)?\.?)? #?\d', raw, re.I):  # New York's firehouses go by their company number
            return 'fuel_depot', 'Firehouse, ' + ' '.join(re.findall(r'[A-Za-z]+|\d+', raw)).title(), 0.9
        return 'fuel_depot', tidy(shown), 0.9
    if numbered:                                   # "Knight #332": a small chain's station
        return 'fuel', tidy(shown), 0.75
    if SHELL.search(raw) or len(tidy(shown)) < 3:  # "Eight Mile & Taft Inc", "Dillip Corp.": nearly always a corner station
        return 'fuel', 'Gas Station', 0.6
    if NAMED.match(raw) or (PERSON.match(tidy(raw)) and landuse in (None, 'Non-Developed', 'Developed, Open Space', 'Developed, Low Intensity')):
        return None                                # a person's name, likely their farm or home: leave it out
    return 'fuel_depot', tidy(shown), 0.6        # some business's own tanks: "Finatech", "Aramco Services"


# --- guns --------------------------------------------------------------------------------------------------------
GUNNY = re.compile(r'\b(arms|armory|armoury|firearms?|guns?|gunsmith\w*|ammo|ammunition|ordnance|tactical|rifles?|pistols?|'
                   r'shooting|range|outfitters?|sporting|sports?|outdoors?|pawn|hunting|trading post|defen[cs]e|ballistics?|'
                   r'armament|munitions|reloading|bullets?|holsters?)\b', re.I)
COMPANY = re.compile(r'\b(llc|inc|corp|corporation|co|company|ltd|lp|enterprises?|stores?|shops?|supply|hardware|mart|center|'
                     r'trading|wholesale|exchange|jewelry|jewelers|marine|feed|farm)\b', re.I)


GOOD_MATCH = {'PointAddress', 'Subaddress', 'StreetAddress', 'StreetAddressExt'}
# a person's name as the business name ('Robert L Dennis &', 'L L Cote', 'Kane', 'Chad Koepke Gun & Ammo')
OWNER = re.compile(r"^([A-Z]\.? ){1,3}[A-Z][a-z'-]+$|^[A-Z][a-z'-]+ ([A-Z]\.? )?[A-Z][a-z'-]+ ?(&|and\b|,)")
INDIVIDUAL = re.compile(r"^([A-Z][A-Za-z'-]+),\s*([A-Z][A-Za-z'-]+)")  # the licence is in a person's own name: "KOEPKE, CHAD"


def owner_named(n, lic):
    """'Chad Koepke Gun & Ammo' under the licence 'KOEPKE, CHAD': a business named after its owner, usually run from home."""
    m = INDIVIDUAL.match(lic)
    words = set(re.findall(r"[a-z'-]+", n.lower()))
    return bool(OWNER.match(n) or (m and any(w.lower() in words for w in m.groups() if len(w) > 2)))


def gun_place(a):
    """(name, conf) for a licensee, or None to leave it out."""
    t, struc = a.get('USER_LIC_TYPE'), (a.get('StrucType') or '').strip()
    biz, lic = (a.get('USER_BUSINESS_NAME') or '').strip(), (a.get('USER_LICENSE_NAME') or '').strip()
    if struc != 'Commercial' or (a.get('Score') or 0) < 90 or a.get('Addr_type') not in GOOD_MATCH:
        return None  # a home, or not known not to be one; or only placed at a ZIP code centre
    name = biz or lic
    if t not in (1, 2, 6) and not GUNNY.search(name):  # manufacturers/importers only when the name says guns
        return None
    if not biz:
        # licence name only: a commercial building with a company name, or anywhere with a gun-shop name
        if not (GUNNY.search(lic) or (struc == 'Commercial' and COMPANY.search(lic))) or ',' in lic:
            return None
    n = tidy(name)
    person = PERSON.match(n) or PERSON.match(tidy(name.strip(' &,')))
    if len(n) < 3 or (person and not (GUNNY.search(n) or COMPANY.search(n))) or owner_named(n, lic):
        return None
    return n, 0.9


# --- download ----------------------------------------------------------------------------------------------------
def pages(src, kind, refresh):
    """Yield features of an ArcGIS FeatureServer layer, 2,000 at a time, caching each page as JSON."""
    url, where, oid, fields = src
    d = RAW / kind
    d.mkdir(parents=True, exist_ok=True)
    off = 0
    while True:
        f = d / f'page-{off // 2000:04d}.json'
        if refresh or not f.exists():
            q = urllib.parse.urlencode({'where': where, 'outFields': fields, 'orderByFields': oid, 'resultOffset': off,
                                        'resultRecordCount': 2000, 'outSR': 4326, 'f': 'json'})
            for attempt in range(6):
                try:
                    with urllib.request.urlopen(f'{url}?{q}', timeout=120) as r:
                        body = json.load(r)
                    if 'error' in body:
                        raise RuntimeError(body['error'])
                    break
                except Exception as e:
                    print(f'  {kind} offset {off}: {e}, retrying', flush=True)
                    time.sleep(5 * (attempt + 1))
            else:
                raise SystemExit(f'{kind}: gave up at offset {off}')
            f.with_suffix('.tmp').write_text(json.dumps(body))
            f.with_suffix('.tmp').replace(f)
            print(f'  {kind} {off + len(body["features"]):,}', flush=True)
        body = json.loads(f.read_text())
        yield from body['features']
        if len(body['features']) < 2000 and not body.get('exceededTransferLimit'):
            return
        off += 2000


BRAND_NAMES = {n for _, n in BRANDS}


def one_per_point(rows, why):
    """Several UST owners at one identical point (a geocoder's fallback, or a station's owner and operator): one row,
    the brand if any, else the surer and better named one."""
    best = {}
    for r in rows:
        k = (r[0], round(r[2], 4), round(r[3], 4))
        rank = (r[1] in BRAND_NAMES, r[4], r[1] != 'Gas Station')
        if k not in best or rank > best[k][0]:
            best[k] = (rank, r)
    why['ust same point'] += len(rows) - len(best)
    return [r for _, r in best.values()]


def cell(v):
    return int(v * 20) if v >= 0 else int(v * 20) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true', help='download the raw pages again')
    a = ap.parse_args()
    rows, seen, why = [], set(), Counter()
    for f in pages(UST, 'ust', a.refresh):
        p, g = f['attributes'], f.get('geometry') or {}
        la, lo = g.get('y', p.get('Latitude')), g.get('x', p.get('Longitude'))
        if not la or not lo or not (17 < la < 72) or not (-180 < lo < -60):
            why['ust bad coords'] += 1; continue
        r = fuel_place(p.get('Name'), p.get('LandUse'))
        if not r:
            why['ust no usable name'] += 1; continue
        rows.append((r[0], r[1], round(la, 6), round(lo, 6), r[2]))
    rows = one_per_point(rows, why)
    for f in pages(FFL, 'ffl', a.refresh):
        p, g = f['attributes'], f.get('geometry') or {}
        la, lo = g.get('y'), g.get('x')
        if not la or not lo or not (17 < la < 72) or not (-180 < lo < -60):
            why['ffl bad coords'] += 1; continue
        r = gun_place(p)
        if not r:
            why['ffl residential/unnamed/not a shop'] += 1; continue
        k = (r[0].lower(), round(la, 4), round(lo, 4))  # one licensee often holds several licences at one shop
        if k in seen:
            why['ffl duplicate licence'] += 1; continue
        seen.add(k)
        rows.append(('gun_shop', r[0], round(la, 6), round(lo, 6), r[1]))
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    db.executemany('INSERT INTO place VALUES (?,?,?,?,?,?,?)', ((c, n, la, lo, cf, cell(lo), cell(la)) for c, n, la, lo, cf in rows))
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    n = db.execute('SELECT count(*) FROM place').fetchone()[0]
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('count', str(n)),
        ('source', 'EPA UST Finder facilities with open tanks (services.arcgis.com/cJ9YHowT8TU7DUyn UST_Finder_Feature_Layer_2eb); '
                   'ATF Federal Firearms Licensees, geocoded (services6.arcgis.com/PrP5ZtrES07DmVmv Federal_Firearm_Licensees_locations)'),
        ('licence', 'Public domain (US federal works: EPA, ATF)'),
        ('built', time.strftime('%Y-%m-%d'))])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'{n:,} places:', dict(Counter(r[0] for r in rows)), 'skipped:', dict(why))


if __name__ == '__main__':
    main()
