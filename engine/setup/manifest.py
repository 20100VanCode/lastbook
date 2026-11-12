"""What can be installed: manifest-v1.json, bundled with the app at build time (packaging/release_manifest.py), or fetched once
from the download site when setup is opened. A fetched one is used only if it parses, says version 1 and every address in it is
allowed (download.url_allowed)."""
import json
import re
import sys
import threading
from pathlib import Path

from . import download

REMOTE = 'https://downloads.lastbook.org/manifest-v1.json'
SHA = re.compile(r'^[0-9a-f]{64}$')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$')


def bundled_paths():
    if getattr(sys, 'frozen', False):
        base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        return [base / 'setup' / 'manifest-v1.json']
    root = Path(__file__).resolve().parents[2]
    return [root / 'setup' / 'manifest-v1.json', root / 'derived' / 'release' / 'setup' / 'manifest-v1.json']


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def validate(m, allowed=None):
    """The manifest, cleaned to the fields setup uses, or None if anything in it is wrong."""
    if not isinstance(m, dict) or m.get('version') != 1:
        return None
    packs, models = [], []
    for p in m.get('packs') or []:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not NAME.match(p['id']):
            return None
        files = []
        for f in p.get('files') or []:
            if not (isinstance(f, dict) and isinstance(f.get('name'), str) and NAME.match(f['name']) and _int(f.get('size'))
                    and isinstance(f.get('sha256'), str) and SHA.match(f['sha256']) and download.url_allowed(f.get('url'), allowed)):
                return None
            files.append({'name': f['name'], 'url': f['url'], 'size': f['size'], 'sha256': f['sha256'], 'kind': f.get('kind') or 'zip'})
        available = bool(p.get('available')) and bool(files)
        if available and not _int(p.get('installed_bytes')):
            return None
        packs.append({'id': p['id'], 'title': str(p.get('title') or p['id']), 'summary': str(p.get('summary') or ''),
                      'records': p.get('records') if _int(p.get('records')) else None,
                      'installed_bytes': p.get('installed_bytes') if _int(p.get('installed_bytes')) else None,
                      'download_bytes': sum(f['size'] for f in files), 'available': available, 'files': files})
    for x in m.get('models') or []:
        if not (isinstance(x, dict) and isinstance(x.get('id'), str) and NAME.match(x['id']) and isinstance(x.get('file'), str)
                and NAME.match(x['file']) and _int(x.get('size')) and isinstance(x.get('sha256'), str) and SHA.match(x['sha256'])
                and download.url_allowed(x.get('url'), allowed) and _int(x.get('memory_bytes'))):
            return None
        models.append({'id': x['id'], 'title': str(x.get('title') or x['id']), 'file': x['file'], 'url': x['url'], 'size': x['size'],
                       'sha256': x['sha256'], 'memory_bytes': x['memory_bytes'], 'available': bool(x.get('available', True))})
    return {'version': 1, 'published': str(m.get('published') or ''), 'packs': packs, 'models': models}


def load_bundled(paths=None):
    for p in paths or bundled_paths():
        try:
            m = validate(json.loads(Path(p).read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
        if m:
            return m
    return {'version': 1, 'published': '', 'packs': [], 'models': []}


def merge(bundled, fetched):
    """The fetched manifest, plus any pack or model of the bundled one it leaves out (matched by id): one bad publish must not
    take away an option the app was built with. An entry in both comes from the fetched copy."""
    out = dict(fetched)
    for key in ('packs', 'models'):
        have = {x['id'] for x in fetched[key]}
        out[key] = list(fetched[key]) + [x for x in bundled[key] if x['id'] not in have]
    return out


class Manifest:
    """The bundled manifest at once; a fetched one replaces it when it arrives and is newer or the same date."""

    def __init__(self, bundled=None, remote=REMOTE, allowed=None, context=None):
        self.current = bundled or load_bundled()
        self.source = 'bundled'
        self.remote, self.allowed, self.context = remote, allowed, context
        self.fetching = None

    def fetch_once(self):
        if self.fetching or not self.remote:
            return
        self.fetching = threading.Thread(target=self._fetch, daemon=True, name='setup-manifest')
        self.fetching.start()

    def _fetch(self):
        data = download.fetch_small(self.remote, allowed=self.allowed, context=self.context)
        if not data:
            return
        try:
            m = validate(json.loads(data.decode('utf-8')), self.allowed)
        except ValueError:
            m = None
        if m and m['published'] >= self.current.get('published', ''):
            self.current, self.source = merge(self.current, m), 'fetched'

    def pack(self, pid):
        return next((p for p in self.current['packs'] if p['id'] == pid), None)

    def model(self, mid=None):
        ms = [m for m in self.current['models'] if m['available']]
        return next((m for m in ms if mid in (None, m['id'])), None)

    def public(self):
        strip = lambda f: {k: v for k, v in f.items() if k != 'url'}
        return {'source': self.source, 'published': self.current['published'],
                'packs': [{**p, 'files': [strip(f) for f in p['files']]} for p in self.current['packs']],
                'models': [strip(m) for m in self.current['models']]}
