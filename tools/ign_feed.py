#!/usr/bin/env python3
"""The download address of each département's IGN layer, read from the Atom feeds.

  derived/buildenv/bin/python tools/ign_feed.py bdtopo --out derived/geo/ign-bdtopo.json
  derived/buildenv/bin/python tools/ign_feed.py bdalti --out derived/geo/ign-bdalti.json

data.geopf.fr lists every edition of a layer, oldest first, across many pages; this keeps
the newest entry whose file name carries the département (D972, D001, D2A...), and
verifies the download address with a HEAD request. The address is built from the title
(<download>/<layer>/<title>/<title>.7z); when that 404s the entry page is read for the
real link, so a format change does not silently break the batch.
"""
import argparse
import json
import re
import urllib.request
from pathlib import Path

FEEDS = {
    'bdtopo': 'https://data.geopf.fr/telechargement/resource/BDTOPO',
    'bdalti': 'https://data.geopf.fr/telechargement/resource/BDALTI',
    'rpg': 'https://data.geopf.fr/telechargement/resource/RPG',
}
DEP = re.compile(r'_D(\d{2,3}[AB]?)(?:_\d{4}-\d{2}-\d{2})?$')
REG = re.compile(r'_(R\d{2})_\d{4}-\d{2}-\d{2}$')


def dep_code(raw):
    """IGN writes D001, D02A, D972; the département keys are 01, 2A, 972."""
    return raw[1:] if raw.startswith('0') else raw
UA = {'User-Agent': 'relique-fr/1.0'}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def parse(root):
    """(title, resource address) for every entry of one feed page."""
    for block in re.findall(r'<entry>.*?</entry>', root, re.S):
        title = re.search(r'<title>([^<]+)</title>', block)
        link = re.search(r'<link href="([^"]+)"[^>]*type="application/atom\+xml"', block)
        if title and link:
            yield title.group(1), link.group(1)


def entries(feed, cache=None):
    """Every entry of the feed, from the network or from pages already on disk."""
    if cache:
        for path in sorted(Path(cache).glob(feed.rsplit('/', 1)[-1].lower() + '*.xml')):
            yield from parse(path.read_text(encoding='utf-8', errors='replace'))
        return
    page = 1
    while True:
        root = get(f'{feed}?page={page}').decode('utf-8', 'replace')
        found = list(parse(root))
        if not found:
            return
        yield from found
        page += 1
        if page > 500:
            return


def head(url, tries=3):
    for i in range(tries):
        try:
            urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers=UA), timeout=90).close()
            return True
        except Exception:
            if i == tries - 1:
                return False
    return False


def collect(feed, cache, pattern, key):
    """The newest edition of each code (département or region) in the feed."""
    best = {}
    for title, page in entries(feed, cache):
        m = pattern.search(title)
        if not m:
            continue
        date = re.search(r'_(\d{4}-\d{2}-\d{2})$', title)
        code = dep_code(m.group(1)) if pattern is DEP else m.group(1)
        if code not in best or (date and date.group(1) > best[code][2]):
            best[code] = (title, page, date.group(1) if date else '')
    return best


def resolve(layer, best):
    out = {}
    for code, (title, page, _) in sorted(best.items()):
        guess = f'https://data.geopf.fr/telechargement/download/{layer}/{title}/{title}.7z'
        if head(guess):
            out[code] = {'title': title, 'url': guess}
            continue
        try:
            block = get(page).decode('utf-8', 'replace')
            link = re.search(r'<link href="([^"]+\.(?:7z|zip))"', block)
            if link:
                out[code] = {'title': title, 'url': link.group(1)}
        except Exception as exc:
            print(f'  {code}: {exc}')
    return out


def pick(feed, layer, cache=None):
    """dep -> (title, download url) for the newest edition of each département."""
    return resolve(layer, collect(feed, cache, DEP, 'département'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('layer', choices=sorted(FEEDS))
    ap.add_argument('--out', required=True)
    ap.add_argument('--pages', help='directory of feed pages already downloaded, instead of the network')
    ap.add_argument('--regions-out', help='also write the regional editions, for départements published only as a region')
    a = ap.parse_args()
    layer = {'bdtopo': 'BDTOPO', 'rpg': 'RPG'}.get(a.layer, 'BDALTI')
    got = pick(FEEDS[a.layer], layer, a.pages)
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(got, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(got)} départements -> {path}')
    for dep, v in list(got.items())[:3]:
        print('  ', dep, v['title'])
    if a.regions_out:
        reg = resolve(layer, collect(FEEDS[a.layer], a.pages, REG, 'région'))
        rp = Path(a.regions_out)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding='utf-8')
        print(f'{len(reg)} régions -> {rp}')


if __name__ == '__main__':
    main()
