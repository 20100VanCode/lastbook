"""Writes derived/geo/socal-bldg-cells.json: the 0.05° Southern California cells where the OpenStreetMap map
(derived/geo/map.sqlite) already has at least half as many buildings as Microsoft's footprints. Only there does
tools/build_buildings.py leave Microsoft's outlines out of the 2D map (elsewhere OSM coverage is thin).

  derived/buildenv/bin/python tools/socal_bldg_cells.py
Needs the current derived/geo/buildings.sqlite (table bldg_socal) for Microsoft's per-cell counts.
"""
import json, math, sqlite3, zlib
from array import array
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CELL = 0.05


def cell(lon, lat):
    return int((lon + 180) / CELL) * 100000 + int((lat + 90) / CELL)


osm = Counter(cell((a + b) / 2, (c + d) / 2) for a, b, c, d in sqlite3.connect(f"file:{HERE / 'derived/geo/map.sqlite'}?mode=ro", uri=True).execute(
    "SELECT i.minx, i.maxx, i.miny, i.maxy FROM feat f JOIN feat_idx i ON i.id = f.id WHERE f.layer = 'bldg'"))
ms = Counter()
W = 2 ** 30
for (data,) in sqlite3.connect(f"file:{HERE / 'derived/geo/buildings.sqlite'}?mode=ro", uri=True).execute('SELECT data FROM bldg_socal'):
    a = array('i'); a.frombytes(zlib.decompress(data)); i = 0
    while i < len(a):
        n = a[i]; X, Y = a[i + 2], a[i + 3]; sx, sy, i = X, Y, i + 4
        for _ in range(n - 1):
            X += a[i]; Y += a[i + 1]; sx += X; sy += Y; i += 2
        lon = sx / n / W * 360 - 180
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * sy / n / W))))
        ms[cell(lon, lat)] += 1
good = sorted(c for c, k in ms.items() if osm.get(c, 0) >= 0.5 * k)
(HERE / 'derived/geo/socal-bldg-cells.json').write_text(json.dumps(good))
print(f'{len(ms)} SoCal cells with Microsoft buildings, {len(good)} where OSM has at least half as many '
      f'({sum(ms[c] for c in good):,} of {sum(ms.values()):,} Microsoft buildings skipped in 2D)')
