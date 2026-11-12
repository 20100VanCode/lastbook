"""Downloads NOAA's 25 cm coastal orthophotos (Digital Coast id 13811, CC0) around a place, for tools/build_aerial_coast.py.

  derived/buildenv/bin/python tools/fetch_aerial_coast.py --lat 39.0997 --lon -94.5786 --miles 50

Source: NOAA NGS Coastal Mapping Program, "Laguna Point to Imperial Beach, CA" 2024-25 MHW 4-band mosaic,
https://coastalimagery.blob.core.windows.net/digitalcoast/LagunaPointCA_MHW_RGBN_2024_13811/ - 3 km Cloud-Optimized
GeoTIFFs in UTM 11N (EPSG 6340), named by their upper-left corner. It covers a strip along the coast (Point Mugu to
Imperial Beach, a few km inland). Keeps the files that reach into the circle under derived/geo/sources/noaa-coast/tif.
Resumable. The raw files are only needed while building and can be deleted afterwards.
"""
import argparse, math, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/sources/noaa-coast/tif'
BASE = 'https://coastalimagery.blob.core.windows.net/digitalcoast/LagunaPointCA_MHW_RGBN_2024_13811/'
UA = 'survival-guide-offline-map/1.0 (personal offline cache; contact hello@lastbook.org)'
SIDE = 3010  # metres per file (12040 px at 0.25 m)


def get(url, method='GET', timeout=600):
    return urllib.request.urlopen(urllib.request.Request(url, method=method, headers={'User-Agent': UA}), timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--miles', type=float, default=50)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    cx, cy = Transformer.from_crs(4326, 6340, always_xy=True).transform(a.lon, a.lat)
    radius = a.miles * 1609.344
    names = []
    for u in get(BASE + 'urllist13811.txt', timeout=120).read().decode().split():
        m = re.search(r'/((\d+)e(\d+)n\.tif)$', u)
        if m:
            e, n = int(m[2]), int(m[3])
            if math.hypot(max(e - cx, 0, cx - e - SIDE), max(n - SIDE - cy, 0, cy - n)) <= radius:
                names.append(m[1])
    OUT.mkdir(parents=True, exist_ok=True)
    print(f'{len(names)} files reach into {a.miles:g} miles', flush=True)

    failed = []

    def one(name):
        p = OUT / name
        if p.exists():  # only complete downloads are renamed into place
            return 0
        for attempt in range(6):
            try:
                tmp = p.with_suffix('.part')
                with get(BASE + name) as r, open(tmp, 'wb') as f:
                    want = int(r.headers.get('Content-Length') or 0)
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                if want and tmp.stat().st_size != want:
                    raise IOError(f'short download: {tmp.stat().st_size} of {want} bytes')
                tmp.replace(p)
                return p.stat().st_size
            except Exception as e:
                err = e
                time.sleep(min(60, 3 * 2 ** attempt))
        print(f'failed {name}: {err}', flush=True)
        failed.append(name)
        return 0

    t0, got = time.time(), 0
    with ThreadPoolExecutor(a.workers) as pool:
        for k, n in enumerate(pool.map(one, names), 1):
            got += n
            if k % 20 == 0:
                print(f'{k}/{len(names)} files, {got / 1e9:.1f} GB new, {time.time() - t0:.0f}s', flush=True)
    if failed:
        sys.exit(f'{len(failed)} files failed (run again to retry): ' + ' '.join(failed))
    print('done', flush=True)


if __name__ == '__main__':
    main()
