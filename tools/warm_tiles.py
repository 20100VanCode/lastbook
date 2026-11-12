"""Pre-builds the zoomed-out street-map tiles (zoom 5-8, US) into derived/geo/tilecache, outside the web server.

  library-data/runtime/macos-arm64/python/bin/python3 tools/warm_tiles.py
"""
import math, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def tiles():
    tx = lambda lon, z: int((lon + 180) / 360 * 2 ** z)
    ty = lambda lat, z: int((0.5 - math.log((1 + math.sin(math.radians(lat))) / (1 - math.sin(math.radians(lat)))) / (4 * math.pi)) * 2 ** z)
    for z in range(5, 9):
        for w, s, e, n in [(-125, 24, -66, 50), (-170, 51, -129, 72), (-161, 18.5, -154, 22.5)]:
            for x in range(tx(w, z), tx(e, z) + 1):
                for y in range(ty(n, z), ty(s, z) + 1):
                    yield z, x, y


def one(t):
    import server
    server.map_tile(*t)  # writes the disk cache as a side effect
    return t


if __name__ == '__main__':
    todo = list(tiles())
    with ProcessPoolExecutor(12) as pool:
        for i, _ in enumerate(pool.map(one, todo, chunksize=8), 1):
            if i % 200 == 0:
                print(f'{i}/{len(todo)}', flush=True)
    print('done', len(todo), flush=True)
