"""Full-detail aerial photos around a place: derived/geo/aerial-detail.sqlite, zoom 17 up to 18 (or 19).

  derived/buildenv/bin/python tools/fetch_aerial_detail.py --lat 39.0997 --lon -94.5786 --miles 50 [--maxz 18] [--dry-run]

Source: USGS NAIP Plus image service (NAIP and high-resolution orthoimagery, ~30-60 cm, public domain):
https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer. Each request renders one
2048 px web-mercator block (8 x 8 tiles at the top zoom); lower zooms down to 17 are made by halving.
Blocks over open sea (no land in the USGS elevation tiles) are skipped. Resumable: finished blocks are recorded.
The general-zoom photos (z0-16) come from tools/fetch_aerial.py; the server uses these for z17+.
"""
import argparse, math, queue, sqlite3, struct, sys, threading, time, urllib.parse, urllib.request, zlib
from pathlib import Path

import numpy as np
import imagecodecs

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/aerial-detail.sqlite'
TERRAIN = HERE / 'derived/geo/terrain.sqlite'
URL = 'https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage?'
UA = 'survival-guide-offline-map/1.0 (personal offline cache; contact hello@lastbook.org)'
R = 20037508.342789244
BLOCK = 8  # tiles per block edge at the top zoom (2048 px)


def tile_xy(lon, lat, z):
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * 2 ** z, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * 2 ** z


def tile_lonlat(z, x, y):
    n = 2 ** z
    return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


class Land:
    """Is there land in a block? From the zoom-12 USGS elevation tiles (open sea has no tile or height exactly 0)."""
    def __init__(self):
        self.db = sqlite3.connect(f'file:{TERRAIN}?mode=ro', uri=True)
        self.cache = {}

    def heights(self, x, y):
        if (x, y) not in self.cache:
            r = self.db.execute('SELECT png FROM tile WHERE z=12 AND x=? AND y=?', (x, y)).fetchone()
            self.cache[(x, y)] = None if r is None else imagecodecs.png_decode(r[0])
        return self.cache[(x, y)]

    def any(self, bz, bx, by):
        f = 2 ** (bz - 12)  # blocks per z12 tile edge
        a = self.heights(bx // f, by // f)
        if a is None:
            return False
        s = 256 // f
        px = a[(by % f) * s:(by % f + 1) * s, (bx % f) * s:(bx % f + 1) * s].astype(np.int64)
        v = px[..., 0] * 65536 + px[..., 1] * 256 + px[..., 2]
        return bool((v != 100000).any())  # 100000 encodes exactly 0 m: sea


def blocks(lat, lon, miles, maxz):
    bz = maxz - 3
    radius = miles * 1.609344
    x0, y0 = tile_xy(lon - radius / 85, lat + radius / 111 + .01, bz)
    x1, y1 = tile_xy(lon + radius / 85, lat - radius / 111 - .01, bz)
    land = Land()
    out = []
    for by in range(int(y0), int(y1) + 1):
        for bx in range(int(x0), int(x1) + 1):
            clon, clat = tile_lonlat(bz, bx + .5, by + .5)
            if km(lat, lon, clat, clon) <= radius and land.any(bz, bx, by):
                out.append((bx, by))
    cx, cy = tile_xy(lon, lat, bz)
    out.sort(key=lambda b: (b[0] + .5 - cx) ** 2 + (b[1] + .5 - cy) ** 2)  # home first
    return bz, out


def fetch(bz, bx, by):
    t = 2 * R / 2 ** bz
    xmin, ymax = -R + bx * t, R - by * t
    q = urllib.parse.urlencode(dict(bbox=f'{xmin},{ymax - t},{xmin + t},{ymax}', bboxSR=3857, imageSR=3857, size='2048,2048',
                                    format='jpg', compressionQuality=92, interpolation='RSP_BilinearInterpolation', f='image'))
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + q, headers={'User-Agent': UA}), timeout=180) as r:
                body = r.read()
            if body[:3] == b'\xff\xd8\xff':
                return imagecodecs.jpeg8_decode(body)
        except Exception:
            pass
        time.sleep(min(120, 5 * 2 ** attempt))
    return None


def tiles_of(img, z, x0, y0):
    """Cut a square image into 256 px tiles at zoom z; skip empty (flat no-data) ones."""
    n = img.shape[0] // 256
    for j in range(n):
        for i in range(n):
            t = np.ascontiguousarray(img[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256, :3])
            if t.std() < 1.5:
                continue
            yield z, x0 + i, y0 + j, imagecodecs.jpeg8_encode(t, level=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--miles', type=float, default=50)
    ap.add_argument('--maxz', type=int, default=18, choices=(18, 19))
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    bz, todo = blocks(a.lat, a.lon, a.miles, a.maxz)
    print(f'{len(todo):,} land blocks within {a.miles:g} miles; up to {len(todo) * 64:,} tiles at z{a.maxz}', flush=True)
    if a.dry_run:
        return
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
                     'CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, jpg BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS done(z INT, x INT, y INT, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);')
    db.execute("INSERT OR REPLACE INTO meta VALUES ('attribution', 'High-resolution imagery: USGS The National Map NAIP Plus (USDA NAIP and HRO)')")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('area', ?)", (f'{a.miles:g} miles around {a.lat},{a.lon}, zoom 17-{a.maxz}',))
    rk, ck = a.miles * 1.609344 / 111.32, math.cos(math.radians(a.lat))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('bbox', ?)", (f'{a.lon - rk / ck:.4f},{a.lat - rk:.4f},{a.lon + rk / ck:.4f},{a.lat + rk:.4f}',))  # the map asks for z17+ only inside
    db.commit()
    done = {(x, y) for x, y in db.execute('SELECT x,y FROM done WHERE z=?', (bz,))}
    todo = [b for b in todo if b not in done]
    print(f'{len(done):,} blocks already done, {len(todo):,} to fetch', flush=True)
    q, res = queue.Queue(), queue.Queue()
    for b in todo:
        q.put(b)

    def worker():
        while True:
            try:
                bx, by = q.get_nowait()
            except queue.Empty:
                return
            res.put((bx, by, fetch(bz, bx, by)))

    for _ in range(a.workers):
        threading.Thread(target=worker, daemon=True).start()
    t0, ntiles = time.time(), 0
    for k in range(1, len(todo) + 1):
        bx, by, img = res.get()
        if img is None:
            print(f'gave up on block {bz}/{bx}/{by} (will retry on the next run)', flush=True)
            continue
        img = img[..., :3].astype(np.float32)
        rows, zs = [], range(a.maxz, 16, -1)  # the top zoom, then halved down to 17
        for z in zs:
            f = 2 ** (a.maxz - z)
            rows += tiles_of(img.round().astype(np.uint8), z, bx * BLOCK // f, by * BLOCK // f)
            if z > 17:
                img = img.reshape(img.shape[0] // 2, 2, img.shape[1] // 2, 2, 3).mean(axis=(1, 3))
        db.executemany('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', rows)
        db.execute('INSERT OR REPLACE INTO done VALUES (?,?,?)', (bz, bx, by))
        ntiles += len(rows)
        if k % 20 == 0:
            db.commit()
            el = time.time() - t0
            print(f'{k:,}/{len(todo):,} blocks, {ntiles:,} tiles, {el / 60:.0f} min, ~{(len(todo) - k) * el / k / 3600:.1f} h left', flush=True)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    db.commit()
    print(f'done: {ntiles:,} tiles in {(time.time() - t0) / 3600:.1f} h', flush=True)


if __name__ == '__main__':
    main()
