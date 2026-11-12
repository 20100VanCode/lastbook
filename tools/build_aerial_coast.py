"""Sharp coastal aerial photos: derived/geo/aerial-coast.sqlite, web-mercator zoom 17-19 JPEG tiles.

  derived/buildenv/bin/python tools/build_aerial_coast.py [--workers 14]

Reads NOAA's 25 cm coastal orthophotos fetched by tools/fetch_aerial_coast.py (UTM 11N GeoTIFFs with an alpha band)
and resamples them (bilinear) onto zoom-19 tiles, then halves down to 17. Work goes by zoom-14 tile (32 x 32 tiles at
zoom 19). Only tiles the photos cover completely are kept, so at the edge of the coverage the map falls back to the
general photos (aerial-detail.sqlite / aerial.sqlite) a whole tile at a time. The server prefers these for z17+.
Resumable: finished zoom-14 tiles are recorded.
"""
import argparse, math, sqlite3, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import imagecodecs
import tifffile
from pyproj import Transformer

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/noaa-coast/tif'
OUT = HERE / 'derived/geo/aerial-coast.sqlite'
R = 20037508.342789244
GZ, TOP = 14, 19
N = 256 * 2 ** (TOP - GZ)  # pixels per group edge at zoom 19
STRIP = 1024  # rows resampled at a time
STEP = 128  # spacing of the exactly projected grid; positions in between are interpolated (error well under 1 mm)
# Colour: the NOAA flights (winter, low sun) are bluer and much more contrasty than the USDA photos around them. Each
# channel is moved halfway to the USDA mean and standard deviation (measured on 500 land tiles both cover), which keeps
# the sharpness but avoids a glaring seam where the coverage ends. A full match looked hazy.
MEAN_NOAA, STD_NOAA = np.array([126.2, 123.1, 135.7]), np.array([60.7, 54.9, 46.1])
MEAN_USDA, STD_USDA = np.array([131.5, 131.8, 119.1]), np.array([36.3, 32.3, 34.1])
GAIN, MID = np.sqrt(STD_USDA / STD_NOAA), (MEAN_NOAA + MEAN_USDA) / 2


def index():
    """[(name, x0, y0, width, height, pixel)] in UTM metres: upper-left corner of the upper-left pixel."""
    out = []
    for p in sorted(SRC.glob('*.tif')):
        with tifffile.TiffFile(p) as t:
            pg = t.pages[0]
            sx = pg.tags['ModelPixelScaleTag'].value[0]
            tp = pg.tags['ModelTiepointTag'].value
            out.append((p.name, tp[3] - tp[0] * sx, tp[4] + tp[1] * sx, pg.shape[1], pg.shape[0], sx))
    return out


def merc_box(z, x, y):
    t = 2 * R / 2 ** z
    return -R + x * t, R - (y + 1) * t, -R + (x + 1) * t, R - y * t


def groups(files):
    """Zoom-14 tiles that touch any file, with the files each touches (bounding boxes compared in UTM)."""
    to_m = Transformer.from_crs(6340, 3857, always_xy=True)
    to_u = Transformer.from_crs(3857, 6340, always_xy=True)
    cells = {}
    for k, (name, x0, y0, w, h, s) in enumerate(files):
        xs, ys = to_m.transform([x0, x0 + w * s, x0, x0 + w * s], [y0, y0, y0 - h * s, y0 - h * s])
        t = 2 * R / 2 ** GZ
        for gx in range(int((min(xs) + R) // t), int((max(xs) + R) // t) + 1):
            for gy in range(int((R - max(ys)) // t), int((R - min(ys)) // t) + 1):
                cells.setdefault((gx, gy), []).append(k)
    out = []
    for (gx, gy), ks in cells.items():
        a, b, c, d = merc_box(GZ, gx, gy)
        ux, uy = to_u.transform([a, c, a, c], [b, b, d, d])
        hit = [files[k] for k in ks if files[k][1] < max(ux) and files[k][1] + files[k][3] * files[k][5] > min(ux)
               and files[k][2] - files[k][4] * files[k][5] < max(uy) and files[k][2] > min(uy)]
        if hit:
            out.append((gx, gy, hit))
    out.sort(key=lambda g: (g[0], g[1]))  # neighbours share files: keep them close in the work order
    return out


def used(g):
    return ','.join(sorted(h[0] for h in g[2]))


_cache, _to_u = {}, None


def raster(name):
    if name not in _cache:
        if len(_cache) >= 6:
            _cache.pop(next(iter(_cache)))
        _cache[name] = tifffile.imread(SRC / name)
    a = _cache.pop(name)
    _cache[name] = a  # most recently used last
    return a


def utm_grid(gx, gy):
    """UTM easting/northing of every zoom-19 pixel centre in the group, from an exactly projected coarse grid."""
    global _to_u
    _to_u = _to_u or Transformer.from_crs(3857, 6340, always_xy=True)
    a, b, c, d = merc_box(GZ, gx, gy)
    px = (c - a) / N
    g = np.arange(0, N + 1, STEP, dtype=np.float64)
    mx, my = np.meshgrid(a + g * px, d - g * px)
    ux, uy = _to_u.transform(mx, my)
    return ux, uy, px


def interp(grid, rows):
    """Bilinear interpolation of a (N/STEP+1)^2 grid at pixel centres for the given rows, all columns."""
    f = (np.arange(N) + 0.5) / STEP
    i = np.minimum(f.astype(int), grid.shape[1] - 2)
    t = f - i
    fr = (rows + 0.5) / STEP
    j = np.minimum(fr.astype(int), grid.shape[0] - 2)
    u = (fr - j)[:, None]
    top = grid[j][:, i] * (1 - t) + grid[j][:, i + 1] * t
    bot = grid[j + 1][:, i] * (1 - t) + grid[j + 1][:, i + 1] * t
    return top * (1 - u) + bot * u


def task(g):
    gx, gy, hit = g
    gux, guy, _ = utm_grid(gx, gy)
    img = np.zeros((N, N, 3), np.uint8)
    have = np.zeros((N, N), bool)
    for r0 in range(0, N, STRIP):
        rows = np.arange(r0, r0 + STRIP)
        ux, uy = interp(gux, rows), interp(guy, rows)
        for name, x0, y0, w, h, s in hit:
            fx, fy = (ux - x0) / s - 0.5, (y0 - uy) / s - 0.5
            m = ~have[r0:r0 + STRIP] & (fx >= 0) & (fy >= 0) & (fx < w - 1) & (fy < h - 1)
            if not m.any():
                continue
            a = raster(name)
            X, Y = fx[m], fy[m]
            i, j = X.astype(np.int64), Y.astype(np.int64)
            tx, ty = (X - i)[:, None], (Y - j)[:, None]
            p00, p10, p01, p11 = a[j, i], a[j, i + 1], a[j + 1, i], a[j + 1, i + 1]
            ok = np.minimum(np.minimum(p00[:, 4], p10[:, 4]), np.minimum(p01[:, 4], p11[:, 4])) == 255
            v = (p00[:, :3] * (1 - tx) + p10[:, :3] * tx) * (1 - ty) + (p01[:, :3] * (1 - tx) + p11[:, :3] * tx) * ty
            rr, cc = np.nonzero(m)
            rr, cc = rr[ok] + r0, cc[ok]
            img[rr, cc] = np.clip(v[ok] + 0.5, 0, 255).astype(np.uint8)
            have[rr, cc] = True
    rows = []
    if not have.any():
        return gx, gy, rows
    f = ((img - MEAN_NOAA) * GAIN + MID).astype(np.float32)
    for z in range(TOP, 16, -1):
        n = f.shape[0] // 256
        for j in range(n):
            for i in range(n):
                if have[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256].all():
                    t = np.ascontiguousarray(np.clip(f[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] + 0.5, 0, 255).astype(np.uint8))
                    rows.append((z, (gx << (z - GZ)) + i, (gy << (z - GZ)) + j, imagecodecs.jpeg8_encode(t, level=85)))
        if z > 17:
            f = f.reshape(n * 128, 2, n * 128, 2, 3).mean(axis=(1, 3))
            have = have.reshape(n * 128, 2, n * 128, 2).all(axis=(1, 3))
    return gx, gy, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=14)
    a = ap.parse_args()
    if list(SRC.glob('*.part')):
        sys.exit('unfinished downloads in ' + str(SRC) + ': run tools/fetch_aerial_coast.py again first')
    files = index()
    todo = groups(files)
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
                     'CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, jpg BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);')
    if 'files' not in [r[1] for r in db.execute('PRAGMA table_info(done)')]:
        db.execute('DROP TABLE IF EXISTS done')  # from before the source files were recorded: rebuild everything
    db.execute('CREATE TABLE IF NOT EXISTS done(x INT, y INT, files TEXT, PRIMARY KEY(x,y)) WITHOUT ROWID')
    db.execute("DELETE FROM meta WHERE key='built'")  # the map treats the layer as unfinished until the end
    db.execute("INSERT OR REPLACE INTO meta VALUES ('rev', ?)", (time.strftime('%Y%m%d%H%M%S'),))  # new photo URLs for this run
    db.executemany('INSERT OR REPLACE INTO meta VALUES (?,?)', [
        ('attribution', 'Coastal imagery: NOAA NGS Coastal Mapping Program, Laguna Point to Imperial Beach CA 2024-25, 25 cm (CC0)'),
        ('area', f'Coast from Point Mugu to Long Beach, a few km inland ({len(files)} source files)')])
    db.commit()
    done = {(x, y): f for x, y, f in db.execute('SELECT x,y,files FROM done')}
    todo = [g for g in todo if done.get((g[0], g[1])) != used(g)]  # redone when its source files changed
    print(f'{len(files)} source files, {len(todo):,} zoom-{GZ} tiles to build ({len(done):,} built before)', flush=True)
    t0, nt = time.time(), 0
    with Pool(a.workers) as pool:
        for k, (g, (gx, gy, rows)) in enumerate(zip(todo, pool.imap(task, todo, chunksize=2)), 1):
            db.executemany('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', rows)
            db.execute('INSERT OR REPLACE INTO done VALUES (?,?,?)', (gx, gy, used(g)))
            nt += len(rows)
            if k % 20 == 0 or k == len(todo):
                db.commit()
                el = time.time() - t0
                print(f'{k:,}/{len(todo):,} groups, {nt:,} tiles, {el / 60:.1f} min, ~{(len(todo) - k) * el / k / 60:.0f} min left', flush=True)
    xs = db.execute('SELECT min(x), max(x), min(y), max(y) FROM tile WHERE z=17').fetchone()
    if xs[0] is not None:
        n = 2 ** 17
        lon = lambda x: x / n * 360 - 180
        lat = lambda y: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        db.execute("INSERT OR REPLACE INTO meta VALUES ('bbox', ?)", (f'{lon(xs[0]):.4f},{lat(xs[3] + 1):.4f},{lon(xs[1] + 1):.4f},{lat(xs[2]):.4f}',))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    db.commit()
    print(f'done: {nt:,} tiles in {(time.time() - t0) / 60:.1f} min', flush=True)


if __name__ == '__main__':
    main()
