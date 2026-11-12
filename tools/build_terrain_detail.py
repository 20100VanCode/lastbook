"""Builds derived/geo/terrain-detail.sqlite: 1-meter lidar elevation tiles (zoom 13-17) around a place.

  derived/buildenv/bin/python tools/build_terrain_detail.py [--workers 12]

Source: USGS 3DEP 1 m bare-earth DEMs fetched by tools/fetch_lidar.py (derived/geo/sources/lidar1m, manifest.json).
Same terrain-RGB PNG encoding as derived/geo/terrain.sqlite (height_m = -10000 + (R*65536 + G*256 + B) * 0.1),
so the map's relief, contours, elevation readout and 3D view use it unchanged. Where several surveys cover a spot
the newest wins; spots no survey covers are filled from the national 30 m tiles, so there are no holes.
Work is done per zoom-12 tile (resumable); zoom 13 is assembled at the end.
"""
import argparse, json, math, re, sqlite3, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import numpy as np
import tifffile
import imagecodecs
import pyproj

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'tools'))
from build_terrain import png, down  # noqa: E402
from fetch_aerial_detail import Land, km, tile_lonlat  # noqa: E402

SRC = HERE / 'derived/geo/sources/lidar1m'
OUT = HERE / 'derived/geo/terrain-detail.sqlite'
NATIONAL = HERE / 'derived/geo/terrain.sqlite'
R = 20037508.342789244
TOP, JOB = 17, 14  # finest zoom; each job is one z14 tile = 2048 px at z17

SOURCES = None


def flown(t):
    """Survey year from the project name (CA_LosAngeles_2016, ..._B23 = 2023, ..._C25 = 2025), else the publication year.
    Publication dates are no guide: several older surveys were all republished on the same day."""
    project = t['file'].split('/')[0]
    m = re.search(r'(?<!\d)(20\d\d)(?!\d)', project) or re.search(r'_[A-Z](\d\d)$', project)
    year = int(m[1]) if m else int(t['published'][:4] or 0)
    return (year + 2000 if year < 100 else year), t['published']


def init():
    global SOURCES
    m = json.loads((SRC / 'manifest.json').read_text())
    SOURCES = sorted([t for t in m['tiles'] if (SRC / t['file']).exists()], key=flown, reverse=True)


@lru_cache(maxsize=6)
def raster(rel):
    """Heights (NaN = no data), UTM origin/scale and EPSG code of one source tile."""
    with tifffile.TiffFile(SRC / rel) as tf:
        p = tf.pages[0]
        a = p.asarray().astype(np.float32)
        tie, scale = p.tags['ModelTiepointTag'].value, p.tags['ModelPixelScaleTag'].value
        epsg = int(tf.geotiff_metadata.get('ProjectedCSTypeGeoKey'))
    a[(a < -1000) | (a > 9000)] = np.nan
    return a, tie[3], tie[4], scale[0], scale[1], epsg


@lru_cache(maxsize=8)
def transformer(epsg):
    return pyproj.Transformer.from_crs(3857, epsg, always_xy=True)


@lru_cache(maxsize=4)
def national(x12, y12):
    db = sqlite3.connect(f'file:{NATIONAL}?mode=ro', uri=True)
    r = db.execute('SELECT png FROM tile WHERE z=12 AND x=? AND y=?', (x12, y12)).fetchone()
    if r is None:
        return np.zeros((256, 256), np.float32)
    a = imagecodecs.png_decode(r[0]).astype(np.int64)
    return (-10000 + (a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]) * 0.1).astype(np.float32)


def job(x14, y14):
    """2048 x 2048 heights at z17 resolution for z14 tile x14/y14, and how much came from lidar."""
    n = 2048
    t = 2 * R / 2 ** JOB
    mx = -R + x14 * t + (np.arange(n) + .5) * t / n
    my = R - y14 * t - (np.arange(n) + .5) * t / n
    MX, MY = np.meshgrid(mx, my)
    lon0, lat1 = tile_lonlat(JOB, x14, y14)
    lon1, lat0 = tile_lonlat(JOB, x14 + 1, y14 + 1)
    H = np.full((n, n), np.nan, np.float32)
    for s in SOURCES:  # newest first; older surveys only fill what is still missing
        b = s['bbox']
        if b[2] < lon0 or b[0] > lon1 or b[3] < lat0 or b[1] > lat1:
            continue
        todo = np.isnan(H)
        if not todo.any():
            break
        a, ox, oy, sx, sy, epsg = raster(s['file'])
        E, N = transformer(epsg).transform(MX[todo], MY[todo])
        fc = (E - ox) / sx - .5
        fr = (oy - N) / sy - .5
        ok = (fc >= 0) & (fr >= 0) & (fc < a.shape[1] - 1) & (fr < a.shape[0] - 1)
        if not ok.any():
            continue
        c0, r0 = fc[ok].astype(np.int64), fr[ok].astype(np.int64)
        wc, wr = (fc[ok] - c0).astype(np.float32), (fr[ok] - r0).astype(np.float32)
        v = (a[r0, c0] * (1 - wr) * (1 - wc) + a[r0, c0 + 1] * (1 - wr) * wc + a[r0 + 1, c0] * wr * (1 - wc) + a[r0 + 1, c0 + 1] * wr * wc)
        idx = np.flatnonzero(todo)[ok]
        H.flat[idx] = v  # NaN where any corner was no-data: left for the next survey / the 30 m fill
    lidar = float(np.isfinite(H).mean())
    if lidar < 1:  # national 30 m tiles fill the rest (bilinear, in z12 pixel space)
        gx = (x14 * n + np.arange(n) + .5) / 32 - .5
        gy = (y14 * n + np.arange(n) + .5) / 32 - .5
        x12, y12 = x14 // 4, y14 // 4
        big = np.zeros((258, 258), np.float32)  # this z12 tile plus a one-pixel border from its neighbours
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nb = national(x12 + dx, y12 + dy)
                ys = slice(1, 257) if dy == 0 else (slice(0, 1) if dy < 0 else slice(257, 258))
                xs = slice(1, 257) if dx == 0 else (slice(0, 1) if dx < 0 else slice(257, 258))
                big[ys, xs] = nb[(slice(None) if dy == 0 else (slice(255, 256) if dy < 0 else slice(0, 1))),
                                 (slice(None) if dx == 0 else (slice(255, 256) if dx < 0 else slice(0, 1)))]
        lx, ly = gx - x12 * 256 + 1, gy - y12 * 256 + 1
        X, Y = np.meshgrid(lx, ly)
        miss = np.isnan(H)
        xs, ys = X[miss], Y[miss]
        c0, r0 = np.floor(xs).astype(np.int64), np.floor(ys).astype(np.int64)
        wc, wr = (xs - c0).astype(np.float32), (ys - r0).astype(np.float32)
        H[miss] = (big[r0, c0] * (1 - wr) * (1 - wc) + big[r0, c0 + 1] * (1 - wr) * wc
                   + big[r0 + 1, c0] * wr * (1 - wc) + big[r0 + 1, c0 + 1] * wr * wc)
    return H, lidar


def task(key):
    """Every z14 job inside one z12 tile -> (key, list of (z, x, y, png), z14 heights, lidar share per job)."""
    x12, y12, jobs = key
    out, low, share = [], {}, []
    for x14, y14 in jobs:
        H, lidar = job(x14, y14)
        share.append(lidar)
        for z in range(TOP, JOB - 1, -1):
            k = 2 ** (z - JOB)
            for j in range(k):
                for i in range(k):
                    out.append((z, x14 * k + i, y14 * k + j, png(H[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256])))
            if z > JOB:
                H = down(H)
        low[(x14, y14)] = H
    return (x12, y12), out, low, share


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    a = ap.parse_args()
    m = json.loads((SRC / 'manifest.json').read_text())
    lat, lon, radius = m['lat'], m['lon'], m['miles'] * 1.609344
    land = Land()
    n = 2 ** JOB
    dg = radius / (111.32 * math.cos(math.radians(lat)))
    x0, x1 = int((lon - dg + 180) / 360 * n), int((lon + dg + 180) / 360 * n)
    s = lambda la: int((0.5 - math.log((1 + math.sin(math.radians(la))) / (1 - math.sin(math.radians(la)))) / (4 * math.pi)) * n)
    y0, y1 = s(lat + radius / 111), s(lat - radius / 111)
    groups = {}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            clon, clat = tile_lonlat(JOB, x + .5, y + .5)
            if km(lat, lon, clat, clon) <= radius + 1.5 and land.any(JOB, x, y):
                groups.setdefault((x // 4, y // 4), []).append((x, y))
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
                     'CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS done(x INT, y INT, h BLOB, PRIMARY KEY(x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);')
    rk, ck = radius / 111.32, math.cos(math.radians(lat))  # the map starts using finished parts right away
    db.execute("INSERT OR REPLACE INTO meta VALUES ('bbox', ?)", (f'{lon - rk / ck:.4f},{lat - rk:.4f},{lon + rk / ck:.4f},{lat + rk:.4f}',))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('area', ?)", (f"{m['miles']:g} miles around {lat},{lon}",))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('circle', ?)", (f'{lat},{lon},{radius:.2f}',))  # lat, lon, km: the map uses lidar zooms only inside
    db.commit()
    done = {(x, y) for x, y in db.execute('SELECT x,y FROM done')}
    todo = [(x, y, jobs) for (x, y), jobs in sorted(groups.items(), key=lambda g: (g[0][1], g[0][0])) if (x, y) not in done]
    print(f'{sum(len(j) for j in groups.values()):,} z14 tiles in {len(groups)} z12 groups; {len(todo)} groups to build', flush=True)
    t0, k, shares = time.time(), 0, []
    with ProcessPoolExecutor(a.workers, initializer=init) as pool:
        for fut in as_completed([pool.submit(task, g) for g in todo]):
            key, rows, low, share = fut.result()
            db.executemany('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', rows)
            db.execute('INSERT OR REPLACE INTO done VALUES (?,?,?)', (*key, np.array(share, np.float32).tobytes()))
            db.commit()
            shares += share; k += 1
            if k % 10 == 0 or k == len(todo):
                el = time.time() - t0
                print(f'{k}/{len(todo)} groups, {el / 60:.0f} min, ~{(len(todo) - k) * el / k / 60:.0f} min left, '
                      f'lidar covers {np.mean(shares) * 100:.0f}% so far', flush=True)
    # zoom 13 from zoom 14
    z14 = {}
    for x, y, b in db.execute('SELECT x,y,png FROM tile WHERE z=?', (JOB,)):
        v = imagecodecs.png_decode(b).astype(np.int64)
        z14[(x, y)] = (-10000 + (v[..., 0] * 65536 + v[..., 1] * 256 + v[..., 2]) * 0.1).astype(np.float32)
    for (px, py) in {(x // 2, y // 2) for x, y in z14}:
        q = np.full((512, 512), np.nan, np.float32)
        for dy in (0, 1):
            for dx in (0, 1):
                h = z14.get((2 * px + dx, 2 * py + dy))
                if h is not None:
                    q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = h
        for dy in (0, 1):  # a quarter with no lidar job (sea, or outside the circle): the national 30 m heights, enlarged
            for dx in (0, 1):
                if np.isnan(q[dy * 256, dx * 256]):
                    x14, y14 = 2 * px + dx, 2 * py + dy
                    nat = national(x14 // 4, y14 // 4)[(y14 % 4) * 64:(y14 % 4 + 1) * 64, (x14 % 4) * 64:(x14 % 4 + 1) * 64]
                    q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = np.kron(nat, np.ones((4, 4), np.float32))
        db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (JOB - 1, px, py, png(down(q))))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('source', 'USGS 3DEP 1 m lidar DEMs (newest survey wins), 30 m fill')",)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    db.commit()
    print(f'done in {(time.time() - t0) / 60:.0f} min; lidar covered {np.mean(shares) * 100:.0f}% of the area', flush=True)


if __name__ == '__main__':
    main()
