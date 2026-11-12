"""Builds derived/geo/aerial.sqlite: aerial photo tiles for the whole US from the USGS National Map imagery cache.

  derived/buildenv/bin/python tools/fetch_aerial.py [--workers 12] [--maxz 16]

Source: https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer (public domain;
USDA NAIP and other orthoimagery, NASA Blue Marble/Landsat at small scales). 256 px web-mercator tiles,
served z/y/x, as JPEG or (at coasts and coverage edges) PNG.
Zooms: z0-12 over every US region's bounding box; above that only children of tiles that exist, up to z15
(z14 in Alaska, where the cache is mostly upsampled satellite filler), and z16 for California plus every
z14 tile with at least 60 Microsoft building footprints (towns and cities). The cache has no z9-11 tiles
outside the lower 48; those are assembled from z12 at the end. Resumable: tiles and misses are recorded.
"""
import argparse, http.client, json, math, os, queue, shutil, sqlite3, sys, threading, time
from pathlib import Path

import numpy as np
import imagecodecs

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/aerial.sqlite'
BLDG = HERE / 'derived/geo/buildings.sqlite'
HOST, PATH = 'basemap.nationalmap.gov', '/arcgis/rest/services/USGSImageryOnly/MapServer'
UA = 'survival-guide-offline-map/1.0 (personal offline cache; contact hello@lastbook.org)'
MIN_FREE = 1.1e12  # stop if the disk gets this full
# (name, south, north, west, east, max zoom)
REGIONS = [('conus', 24.3, 49.5, -125.0, -66.8, 15), ('ak', 51.0, 71.6, -180.0, -129.5, 14),
           ('ak-aleutians-east', 51.0, 53.5, 172.0, 180.0, 14), ('hi', 18.8, 22.4, -160.6, -154.6, 15),
           ('pr-vi', 17.6, 18.6, -68.0, -64.5, 15), ('guam-cnmi', 13.2, 20.6, 144.5, 146.1, 15),
           ('samoa', -14.6, -11.0, -171.2, -168.1, 15)]
# rough California outline (lon, lat): z16 is fetched inside it, not across western Nevada
CALIFORNIA = [(-124.6, 42.0), (-120.0, 42.0), (-120.0, 39.0), (-114.6, 35.0), (-114.1, 34.3), (-114.5, 33.4),
              (-114.7, 32.7), (-117.1, 32.5), (-124.6, 32.5)]


def in_california(lon, lat):
    inside, poly = False, CALIFORNIA
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def tx(lon, z): return int((lon + 180) / 360 * 2 ** z)
def ty(lat, z):
    s = math.sin(math.radians(max(-85, min(85, lat))))
    return int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * 2 ** z)
def lonlat(z, x, y):
    n = 2 ** z
    return (x + .5) / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + .5) / n))))


def region_maxz(z, x, y):
    lon, lat = lonlat(z, x, y)
    best = 0
    for _, s, n, w, e, mz in REGIONS:
        if s - .5 <= lat <= n + .5 and w - .5 <= lon <= e + .5:
            best = max(best, mz)
    return best


def town_tiles():
    """z14 tiles with >= 60 building footprints (they get z16)."""
    db = sqlite3.connect(f'file:{BLDG}?mode=ro', uri=True)
    return {(x, y) for x, y in db.execute('SELECT x,y FROM bldg GROUP BY x,y HAVING sum(n) >= 60')}


class Fetcher:
    def __init__(self):
        self.conn = None

    def get(self, z, x, y):
        """-> (status, content_type, bytes). Retries network errors and 5xx/429 with backoff."""
        for attempt in range(8):
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPSConnection(HOST, timeout=30)
                self.conn.request('GET', f'{PATH}/tile/{z}/{y}/{x}', headers={'User-Agent': UA, 'Accept': 'image/jpeg,image/png'})
                r = self.conn.getresponse(); body = r.read()
                if r.status == 200 or r.status == 404:
                    return r.status, r.getheader('Content-Type', ''), body
                if r.status not in (429, 500, 502, 503, 504):
                    return r.status, '', b''
            except (OSError, http.client.HTTPException):
                try:
                    self.conn and self.conn.close()
                except Exception:
                    pass
                self.conn = None
            time.sleep(min(60, 2 ** attempt))
        return -1, '', b''


def is_blank(a):
    return a.size > 0 and int(a.min()) >= 250


def tidy(ctype, body):
    """Keep JPEGs byte-for-byte; drop empty PNGs; turn fully opaque PNGs into JPEG; keep partial PNGs (coasts)."""
    if body[:3] == b'\xff\xd8\xff':
        # outside the US the service fills land with a small plain-white JPEG: that is "no photo", not a photo
        if len(body) < 6000 and is_blank(imagecodecs.jpeg8_decode(body)):
            return None
        return body
    if body[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    try:
        a = imagecodecs.png_decode(body)
    except Exception:
        return None
    if a.ndim == 3 and a.shape[2] == 4:
        alpha = a[..., 3]
        if not alpha.any():
            return None
        if alpha.min() == 255:
            return imagecodecs.jpeg8_encode(np.ascontiguousarray(a[..., :3]), level=85)
        return body
    if a.ndim == 2:
        a = np.stack([a] * 3, -1)
    return imagecodecs.jpeg8_encode(np.ascontiguousarray(a[..., :3]), level=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--maxz', type=int, default=16)
    a = ap.parse_args()
    c = http.client.HTTPSConnection(HOST, timeout=30)
    c.request('GET', PATH + '?f=json', headers={'User-Agent': UA})
    meta = json.loads(c.getresponse().read())
    lods = {l['level']: l['resolution'] for l in meta['tileInfo']['lods']}
    if abs(meta['tileInfo']['origin']['x'] + 20037508.342787) > 1 or abs(lods.get(16, 0) - 2.388657133974) > 0.01:
        sys.exit('the imagery service changed its tiling; not fetching')
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA page_size=65536; PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
                     'CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, jpg BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS miss(z INT, x INT, y INT, why INT, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);')
    db.execute("INSERT OR REPLACE INTO meta VALUES ('copyright', ?)", (meta.get('copyrightText', ''),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('attribution', 'Imagery: USGS The National Map (USDA NAIP and other orthoimagery; NASA Blue Marble/Landsat at small scales)')")
    db.commit()
    towns = town_tiles() if a.maxz >= 16 else set()
    print(f'{len(towns):,} town tiles get z16', flush=True)

    todo_q, done_q = queue.Queue(maxsize=4000), queue.Queue()
    stop = threading.Event()

    def worker():
        f = Fetcher()
        while True:
            item = todo_q.get()
            if item is None:
                return
            st, ct, body = f.get(*item)
            data = tidy(ct, body) if st == 200 else None
            done_q.put((item, st, data))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(a.workers)]
    for t in threads:
        t.start()

    def run(level_tiles, z):
        have = {(x, y) for x, y in db.execute('SELECT x,y FROM tile WHERE z=?', (z,))}
        have |= {(x, y) for x, y in db.execute('SELECT x,y FROM miss WHERE z=?', (z,))}
        pending = [(z, x, y) for x, y in level_tiles if (x, y) not in have]
        print(f'z{z}: {len(level_tiles):,} candidate tiles, {len(pending):,} to fetch', flush=True)
        t0, n, got, it = time.time(), 0, 0, iter(pending)
        inflight = 0
        while True:
            while inflight < 2000:
                nxt = next(it, None)
                if nxt is None:
                    break
                todo_q.put(nxt); inflight += 1
            if not inflight:
                break
            (zz, x, y), st, data = done_q.get(); inflight -= 1; n += 1
            if data:
                db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (zz, x, y, data)); got += 1
            elif st in (200, 404):
                db.execute('INSERT OR REPLACE INTO miss VALUES (?,?,?,?)', (zz, x, y, 404 if st == 404 else 1))
            # network failures (-1) are not recorded, so a rerun tries them again
            if n % 2000 == 0:
                db.commit()
                if shutil.disk_usage(OUT.parent).free < MIN_FREE:
                    print('stopping: disk nearly full', flush=True); stop.set(); return False
                if n % 20000 == 0:
                    rate = n / (time.time() - t0)
                    print(f'  z{z}: {n:,}/{len(pending):,} ({got:,} tiles) {rate:.0f}/s, ~{(len(pending) - n) / max(rate, 1) / 3600:.1f} h left', flush=True)
        db.commit()
        return True

    # z0-12: every tile in each region's box
    for z in range(0, 13):
        tiles = set()
        for _, s, n, w, e, _ in REGIONS:
            for x in range(tx(w, z), tx(e - 1e-9, z) + 1):
                for y in range(ty(n, z), ty(s, z) + 1):
                    tiles.add((x, y))
        if not run(sorted(tiles), z):
            return
    # z13+: children of tiles that exist, within each region's zoom limit
    for z in range(13, a.maxz + 1):
        parents = [(x, y) for x, y in db.execute('SELECT x,y FROM tile WHERE z=?', (z - 1,))]
        tiles = []
        for px, py in parents:
            for cx in (2 * px, 2 * px + 1):
                for cy in (2 * py, 2 * py + 1):
                    if z <= 15:
                        ok = z <= region_maxz(z, cx, cy)
                    else:
                        lon, lat = lonlat(z, cx, cy)
                        ok = in_california(lon, lat) or (cx >> 2, cy >> 2) in towns
                    if ok:
                        tiles.append((cx, cy))
        tiles.sort(key=lambda t: (t[1] >> 4, t[0] >> 4, t))
        if not run(tiles, z):
            return
    for _ in threads:
        todo_q.put(None)
    fill_gaps(db)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    db.commit()
    print('done', flush=True)


def fill_gaps(db):
    """The cache has no z9-11 tiles over Alaska, Hawaii and the islands: build them from the four children."""
    for z in (11, 10, 9):
        have = {(x, y) for x, y in db.execute('SELECT x,y FROM tile WHERE z=?', (z,))}
        parents = {(x // 2, y // 2) for x, y in db.execute('SELECT x,y FROM tile WHERE z=?', (z + 1,))} - have
        made = 0
        for px, py in sorted(parents):
            canvas = np.zeros((512, 512, 4), np.uint8)
            for dx in (0, 1):
                for dy in (0, 1):
                    r = db.execute('SELECT jpg FROM tile WHERE z=? AND x=? AND y=?', (z + 1, 2 * px + dx, 2 * py + dy)).fetchone()
                    if not r:
                        continue
                    b = r[0]
                    img = imagecodecs.jpeg8_decode(b) if b[:3] == b'\xff\xd8\xff' else imagecodecs.png_decode(b)
                    if img.ndim == 2:
                        img = np.stack([img] * 3, -1)
                    if img.shape[2] == 3:
                        img = np.concatenate([img, np.full(img.shape[:2] + (1,), 255, np.uint8)], -1)
                    canvas[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = img[..., :4]
            # alpha-weighted mean, so transparent (black) pixels don't darken coasts and coverage edges
            c = canvas.reshape(256, 2, 256, 2, 4).astype(np.float32)
            a = c[..., 3:4]
            rgb = (c[..., :3] * a).sum(axis=(1, 3)) / np.maximum(a.sum(axis=(1, 3)), 1)
            small = np.concatenate([rgb, a.mean(axis=(1, 3))], -1).round().astype(np.uint8)
            if not small[..., 3].any():
                continue
            data = imagecodecs.jpeg8_encode(np.ascontiguousarray(small[..., :3]), level=85) if small[..., 3].min() == 255 else imagecodecs.png_encode(small)
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, px, py, data)); made += 1
        db.commit()
        print(f'z{z}: assembled {made} tiles from z{z + 1}', flush=True)


if __name__ == '__main__':
    main()
