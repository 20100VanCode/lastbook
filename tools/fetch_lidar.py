"""Downloads USGS 3DEP 1-meter lidar elevation tiles (GeoTIFF, UTM) around a place, for tools/build_terrain_detail.py.

  derived/buildenv/bin/python tools/fetch_lidar.py --lat 39.0997 --lon -94.5786 --miles 50

Lists products from the TNM Access API (dataset "Digital Elevation Model (DEM) 1 meter"), keeps the 10 km tiles that
reach into the circle, and saves them under derived/geo/sources/lidar1m/<project>/ with manifest.json (bounds,
publication date). Several survey projects often cover the same tile; all are kept and the builder prefers the newest.
Resumable. The raw tiles are only needed while building and can be deleted afterwards.
"""
import argparse, json, math, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/sources/lidar1m'
API = 'https://tnmaccess.nationalmap.gov/api/v1/products?'
UA = 'survival-guide-offline-map/1.0 (personal offline cache; contact hello@lastbook.org)'


def get(url, timeout=600):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout)


def products(bbox):
    items, offset = [], 0
    while True:
        q = urllib.parse.urlencode({'datasets': 'Digital Elevation Model (DEM) 1 meter', 'bbox': ','.join(map(str, bbox)),
                                    'max': 500, 'offset': offset, 'outputFormat': 'JSON'})
        d = json.load(get(API + q, 120))
        items += d.get('items', [])
        offset += 500
        if offset >= d.get('total', 0):
            return items


def reaches(b, lat, lon, km):
    """Does the box get within km of the point?"""
    nx, ny = min(max(lon, b['minX']), b['maxX']), min(max(lat, b['minY']), b['maxY'])
    return math.hypot((nx - lon) * 111.32 * math.cos(math.radians(lat)), (ny - lat) * 111.32) <= km


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--miles', type=float, default=50)
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    km = a.miles * 1.609344
    dl, dg = km / 111.32, km / (111.32 * math.cos(math.radians(a.lat)))
    items = [i for i in products((a.lon - dg, a.lat - dl, a.lon + dg, a.lat + dl))
             if i.get('format') == 'GeoTIFF' and i.get('downloadURL', '').endswith('.tif') and reaches(i['boundingBox'], a.lat, a.lon, km)]
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in items:
        url = i['downloadURL']
        rel = url.split('/Projects/')[1].split('/')[0] + '/' + url.rsplit('/', 1)[1]
        manifest.append({'file': rel, 'url': url, 'bytes': i.get('sizeInBytes') or 0, 'published': i.get('publicationDate', ''),
                         'bbox': [i['boundingBox'][k] for k in ('minX', 'minY', 'maxX', 'maxY')], 'title': i.get('title', '')})
    (OUT / 'manifest.json').write_text(json.dumps({'lat': a.lat, 'lon': a.lon, 'miles': a.miles, 'tiles': manifest}, indent=0))
    total = sum(m['bytes'] for m in manifest)
    print(f'{len(manifest)} tiles reach into {a.miles:g} miles, {total / 1e9:.1f} GB', flush=True)

    def one(m):
        p = OUT / m['file']
        if p.exists():  # only complete downloads are renamed into place (the API's sizes are often out of date)
            return 0
        p.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(6):
            try:
                tmp = p.with_suffix('.part')
                with get(m['url']) as r, open(tmp, 'wb') as f:
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
        print(f'failed {m["file"]}: {err}', flush=True)
        return 0

    t0, got = time.time(), 0
    with ThreadPoolExecutor(a.workers) as pool:
        for k, n in enumerate(pool.map(one, manifest), 1):
            got += n
            if k % 20 == 0:
                print(f'{k}/{len(manifest)} tiles, {got / 1e9:.1f} GB new, {time.time() - t0:.0f}s', flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
