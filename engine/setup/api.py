"""/api/setup/*: the engine side of first-run setup and of Library → Library and local AI. Contract: docs/SETUP-API.md.

Two ways in, one module:
  - setup mode (no library yet): app/main.py makes a Bridge around SetupServer, whose Handler serves web/setup.html at /, the web
    folder at /ui/, and /api/setup/* here. Nothing else.
  - normal mode: server.py hands /api/setup/ to handle(). The app's main.py configures it first (configure(...)); a bare
    server.py gets a manage-mode Setup on first use, with no relaunch (finish then answers restart: true).

Only requests from this computer get an answer (the bridge's, or loopback): a phone the guide is shared with gets 403.
"""
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from . import download, hardware, install
from .manifest import Manifest

DATA_NAME = install.DATA_NAME
WORK_SUFFIX = '.setup'
SAVE_EVERY = 2.0
RECOMMEND_MARGIN = 5 * 10 ** 9     # beyond what the install needs, so the disk is not left full
RECOMMEND_MARGIN_MAX = 20 * 10 ** 9
MAX_BODY = 64 * 1024
ACTIVE = ('waiting', 'downloading', 'verifying', 'unpacking', 'activating')
MODEL_PLACES = ('Downloads', 'Documents', 'Desktop')


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def _gb(n):
    return f'{n / 1e9:.0f} GB' if n >= 10e9 else f'{n / 1e9:.1f} GB'


def _sha256(path, control, progress):
    h, done = hashlib.sha256(), 0
    total = os.path.getsize(path)
    with open(path, 'rb') as f:
        while True:
            control.check()
            b = f.read(8 * 1024 * 1024)
            if not b:
                break
            h.update(b)
            done += len(b)
            progress(done, total)
    return h.hexdigest()


def _same_disk(a, b):
    try:
        pa, pb = Path(a), Path(b)
        while not pa.exists():
            pa = pa.parent
        while not pb.exists():
            pb = pb.parent
        return os.stat(pa).st_dev == os.stat(pb).st_dev
    except OSError:
        return False


class _Item:
    """Progress of one item (the pack, or the model), with rate and time left."""

    def __init__(self, d):
        self.d = d
        self.t, self.at, self.rate = time.time(), d.get('bytes_done', 0), 0.0

    def progress(self, done, total, state=None):
        d = self.d
        if state and d['state'] != state:
            d['state'] = state
            self.t, self.at, self.rate = time.time(), done, 0.0
        d['bytes_done'], d['bytes_total'] = done, total
        now = time.time()
        if now - self.t >= 1.0:
            inst = max(done - self.at, 0) / (now - self.t)
            self.rate = inst if not self.rate else 0.6 * self.rate + 0.4 * inst
            self.t, self.at = now, done
            d['rate_bps'] = int(self.rate)
            d['eta_s'] = round((total - done) / self.rate) if self.rate > 0 else None


class Setup:
    def __init__(self, mode, settings_dir, default_parent, current=None, manifest=None, allowed=None, context=None,
                 on_finish=None, pick_folder=None, look_for_libraries=None, home=None, llm_local=None):
        """mode: 'first-run' or 'manage'. current: the open library (manage). on_finish(folder): the app opens that library
        (it relaunches). pick_folder(): a folder the person chose, or None. look_for_libraries(): LastbookData folders found."""
        self.mode, self.current = mode, Path(current) if current else None
        self.settings_dir, self.default_parent = Path(settings_dir), Path(default_parent)
        self.manifest = manifest or Manifest(allowed=allowed, context=context)
        self.allowed, self.context = allowed, context
        self.on_finish, self.pick_folder, self.look_for_libraries = on_finish, pick_folder, look_for_libraries
        self.home = Path(home) if home else Path.home()
        self._llm = llm_local
        self.lock = threading.RLock()
        self.job, self.control, self.thread = None, None, None
        self.sources = {}          # file name -> a file already on this computer the person chose with `use`
        self.ai_measure, self.measuring = None, False
        self.deleting = set()
        self.job = self._load_job()

    # ------------------------------------------------------------------------------------------------- saved state --
    def _settings(self):
        try:
            return json.loads((self.settings_dir / 'setup.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _save_settings(self, d):
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            install._write_json(self.settings_dir / 'setup.json', d)
        except OSError as e:
            print('setup: could not save setup.json:', e, flush=True)

    def _load_job(self):
        work = self._settings().get('work')
        if not work:
            return None
        try:
            job = json.loads((Path(work) / 'job.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if job.get('state') in ACTIVE:      # this program stopped while it ran: carry on only when the person says so
            job['state'] = 'paused'
            for it in job['items']:
                if it['state'] in ACTIVE:
                    it['state'] = 'paused'
                    it['bytes_done'] = self._on_disk(job['plan'], it)
                it['rate_bps'], it['eta_s'] = 0, None
        return job

    @staticmethod
    def _on_disk(plan, it):
        """Bytes of this item already downloaded, from the files themselves."""
        plan_files = plan['pack']['files'] if it['kind'] == 'pack' and plan.get('pack') else [{'name': plan['model']['file']}] if plan.get('model') else []
        n = 0
        for f in plan_files:
            for p in (Path(plan['work']) / 'downloads' / f['name'], Path(plan['work']) / 'downloads' / (f['name'] + '.part')):
                try:
                    n += p.stat().st_size
                except OSError:
                    pass
        return n

    def _save_job(self):
        job = self.job
        if not job:
            return
        try:
            work = Path(job['plan']['work'])
            work.mkdir(parents=True, exist_ok=True)
            install._write_json(work / 'job.json', job)
        except OSError as e:
            print('setup: could not save job.json:', e, flush=True)

    # --------------------------------------------------------------------------------------------------- the state --
    def llm(self):
        if self._llm is None:
            try:
                import llm_local
                self._llm = llm_local
            except Exception as e:
                print('setup: no llm_local:', type(e).__name__, e, flush=True)
                self._llm = False
        return self._llm or None

    def current_info(self):
        if not self.current:
            return None
        try:
            pack = json.loads((self.current / 'pack.json').read_text(encoding='utf-8')).get('name')
        except (OSError, ValueError, AttributeError):
            pack = None
        m = self.manifest.model()
        model = None
        if m:
            p = self.current / 'models' / m['file']
            if p.is_file() and p.stat().st_size == m['size']:
                model = m['id']
        return {'folder': str(self.current), 'pack': pack, 'model': model, 'old': self._settings().get('old', [])}

    def found(self):
        """Libraries, pack zips and the model file already on this computer. A file is offered when its size matches; its
        SHA-256 is checked when it is used."""
        out, seen = [], set()
        if self.look_for_libraries:
            try:
                for lib in self.look_for_libraries():
                    lib = Path(lib)
                    if str(lib) not in seen and lib != self.current and install.is_library(lib):
                        seen.add(str(lib))
                        out.append({'kind': 'library', 'path': str(lib), 'name': lib.name})
            except Exception:
                traceback.print_exc()
        files = {}
        for p in self.manifest.current['packs']:
            for f in p['files']:
                files[f['name']] = ('pack', p['id'], f['size'])
        m = self.manifest.model()
        if m:
            files[m['file']] = ('model', m['id'], m['size'])
        places = [self.home / x for x in MODEL_PLACES] + [self.default_parent]
        if self.current:
            places += [self.current / 'models', self.current.parent]
        for place in places:
            try:
                names = [c for c in place.iterdir() if c.name in files or (c.name.startswith('Lastbook-') and c.name.endswith('.zip'))]
            except OSError:
                continue
            for c in names:
                key = str(c.resolve())
                if key in seen or not c.is_file():
                    continue
                seen.add(key)
                kind, pid, size = files.get(c.name, ('pack', None, None))
                have = c.stat().st_size
                out.append({'kind': kind, 'path': str(c), 'name': c.name, 'id': pid, 'size': have, 'size_ok': size == have})
        return out

    def _model_path_here(self):
        m = self.manifest.model()
        if not m:
            return None
        for f in self.found():
            if f['kind'] == 'model' and f.get('size_ok'):
                return f['path']
        return None

    def ai_fit(self, hw):
        m = self.manifest.model()
        if not m:
            return {'fits': False, 'needs_bytes': None, 'estimate': True, 'why': 'No local AI is offered for this version.'}
        if self.ai_measure:
            return self.ai_measure
        path = self._model_path_here()
        if path and not self.measuring and self.llm():
            self.measuring = True
            threading.Thread(target=self._measure, args=(path,), daemon=True, name='setup-measure').start()
        return hardware.estimate_ai(hw['ram_bytes'], hw['gpus'], hw['unified_memory'], m['memory_bytes'])

    def _measure(self, path):
        try:
            r = hardware.measure_ai(self.llm(), path)
            if r:
                self.ai_measure = r
        except Exception:
            traceback.print_exc()

    def hardware(self):
        extra = [self.default_parent] + ([self.current.parent] if self.current else [])
        hw = hardware.detect(extra)
        hw['ai'] = self.ai_fit(hw)
        return hw

    def recommend(self, hw):
        packs = sorted((p for p in self.manifest.current['packs'] if p['available']), key=lambda p: p['installed_bytes'] or 0, reverse=True)
        parent = self.current.parent if self.current else self.default_parent
        free, total = hardware.disk_of(parent)
        model = self.manifest.model()
        need = {p['id']: install.need_bytes(p, None) for p in packs}
        if not packs:
            return {'pack': None, 'ai': False, 'folder': str(parent), 'need_bytes': need, 'why': 'No library is ready to download yet.'}
        margin = _margin(total)
        choice, folder, elsewhere = None, parent, None
        for p in packs:        # the disk that holds the home folder (or the open library) whenever anything fits there
            if free >= need[p['id']] + margin:
                choice = p
                break
        if not choice:         # only then another disk, for the largest library that fits on one
            for p in packs:
                for d in hw['disks']:
                    if not _same_disk(d['path'], parent) and d['free_bytes'] >= need[p['id']] + _margin(d['total_bytes']):
                        choice, folder, elsewhere = p, Path(d['path']), d
                        break
                if choice:
                    break
        if not choice:
            small = packs[-1]
            return {'pack': None, 'ai': False, 'folder': str(parent), 'need_bytes': need,
                    'why': f'The smallest library, {small["title"]}, needs {_gb(need[small["id"]])} free, and this computer has {_gb(free)} free.'}
        if elsewhere:
            home_free = free
            free, margin = elsewhere['free_bytes'], _margin(elsewhere['total_bytes'])
        left = free - need[choice['id']]
        ai = bool(model and hw['ai']['fits'] and left >= model['size'] + margin)
        if elsewhere:
            name = elsewhere.get('name') or Path(elsewhere['path']).name or elsewhere['path']
            why = (f'This computer’s own disk has {_gb(home_free)} free, not enough for any library, so {choice["title"]} goes on {name}. '
                   'Keep that disk connected: Lastbook reads the library from it.')
        elif choice is packs[0]:
            why = f'{choice["title"]} is the largest library that fits on this computer’s disk with room to spare.'
        else:
            why = f'{choice["title"]} fits on this computer’s disk with room to spare; {packs[0]["title"]} would need {_gb(need[packs[0]["id"]])} free.'
            roomy = next((d for d in hw['disks'] if not _same_disk(d['path'], parent)
                          and d['free_bytes'] >= need[packs[0]['id']] + _margin(d['total_bytes'])), None)
            if roomy:
                why += f' It would fit on {roomy.get("name") or roomy["path"]}, if you choose that disk.'
        if model and hw['ai']['fits'] and not ai:
            why += ' The local AI fits this computer’s memory, but not on the disk as well.'
        elif model and not hw['ai']['fits']:
            why += ' ' + hw['ai']['why']
        return {'pack': choice['id'], 'ai': ai, 'folder': str(folder), 'need_bytes': need, 'why': why}

    def state(self):
        self.manifest.fetch_once()
        hw = self.hardware()
        return {'mode': self.mode, 'hardware': hw, 'manifest': self.manifest.public(), 'current': self.current_info(),
                'found': self.found(), 'recommend': self.recommend(hw), 'job': self.public_job()}

    def public_job(self):
        with self.lock:
            if not self.job:
                return None
            return {k: v for k, v in json.loads(json.dumps(self.job)).items() if k != 'plan'}

    # -------------------------------------------------------------------------------------------------- the actions --
    def _parent_for(self, folder):
        if folder:
            p = Path(folder).expanduser()
            return p.parent if p.name == DATA_NAME else p
        return self.current.parent if self.current else self.default_parent

    def start(self, pack_id=None, ai=False, folder=None, sources=None, explicit=False, repair=False):
        if repair:
            return self._start_repair(ai)
        with self.lock:
            if self.job and self.job['state'] in ACTIVE + ('paused',):
                return {'error': 'A download is already under way. Pause or cancel it first.', 'code': 'busy'}
            pack = self.manifest.pack(pack_id) if pack_id else None
            if pack_id and (not pack or not pack['available']):
                return {'error': 'That library is not available yet.', 'code': 'unavailable'}
            cur = self.current_info() or {}
            if pack and self.mode == 'manage' and cur.get('pack') == pack['id'] and not folder:
                pack = None        # the same library again: only the AI is wanted
            model = self.manifest.model() if ai else None
            if ai and not model:
                return {'error': 'No local AI is offered for this version.', 'code': 'unavailable'}
            parent = self._parent_for(folder)
            if model and cur.get('model') and parent / DATA_NAME == self.current:
                model = None       # already here, and an upgrade in place carries it over
            if not pack and not model:
                if self.mode == 'first-run':
                    return {'error': 'Choose a library first.', 'code': 'nothing'}
                return {'error': 'Nothing to add: this library and the local AI are already here.', 'code': 'nothing'}
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return {'error': f'Lastbook cannot make a folder there ({type(e).__name__}).', 'code': 'folder'}
            if not os.access(parent, os.W_OK):
                return {'error': 'Lastbook cannot save in that folder. Choose another.', 'code': 'folder'}
            target = parent / DATA_NAME
            if self.mode == 'first-run' and target.exists() and not install.is_library(target):
                if any(target.iterdir()):
                    return {'error': f'There is already a folder called {DATA_NAME} there that is not a library. Choose another place.', 'code': 'folder'}
            work = parent / (DATA_NAME + WORK_SUFFIX)
            srcs = dict(self.sources)
            srcs.update(sources or {})
            for f in self.found():
                if f.get('size_ok') and f['name'] not in srcs and f['kind'] in ('pack', 'model'):
                    srcs[f['name']] = f['path']
            names = ([f['name'] for f in pack['files']] if pack else []) + ([model['file']] if model else [])
            have = set(srcs)
            need = install.need_bytes(pack, model, have)
            for name in names:     # what an earlier run already downloaded is on the disk already
                if name in have:
                    continue
                for done in (work / 'downloads' / (name + '.part'), work / 'downloads' / name):
                    try:
                        need -= os.path.getsize(done)
                    except OSError:
                        pass
            free, _ = hardware.disk_of(parent)
            if free < need:
                return {'error': f'This needs {_gb(need)} free on that disk, and it has {_gb(free)}. Free some space or choose another disk.',
                        'code': 'no_space', 'need_bytes': need, 'free_bytes': free}
            items = []
            if pack:
                items.append({'id': pack['id'], 'kind': 'pack', 'title': pack['title'], 'state': 'waiting', 'bytes_done': 0,
                              'bytes_total': pack['download_bytes'], 'rate_bps': 0, 'eta_s': None, 'error': None})
            if model:
                items.append({'id': model['id'], 'kind': 'model', 'title': model['title'], 'state': 'waiting', 'bytes_done': 0,
                              'bytes_total': model['size'], 'rate_bps': 0, 'eta_s': None, 'error': None})
            self.job = {'id': uuid.uuid4().hex[:12], 'state': 'waiting', 'items': items, 'error': None, 'started': _now(),
                        'folder': str(target),
                        'plan': {'pack': pack, 'model': model, 'parent': str(parent), 'target': str(target), 'work': str(work),
                                 'sources': {k: v for k, v in srcs.items() if k in names}, 'explicit': explicit,
                                 'retried': {}, 'switch': bool(pack)}}
            s = self._settings()
            s['work'] = str(work)
            self._save_settings(s)
            self._save_job()
            self._run()
            return self.public_job()

    def _start_repair(self, ai):
        """Re-check the open library's files (pack-manifest.tsv) and the model's SHA-256. What is wrong is fetched again: the pack is
        downloaded and switched to as in an upgrade, the model replaced in place. Nothing is downloaded if all is well."""
        with self.lock:
            if self.job and self.job['state'] in ACTIVE + ('paused',):
                return {'error': 'A download is already under way. Pause or cancel it first.', 'code': 'busy'}
            cur = self.current_info()
            if self.mode != 'manage' or not cur:
                return {'error': 'There is no library to repair yet.', 'code': 'nothing'}
            pack = self.manifest.pack(cur['pack']) if cur['pack'] else None
            if not pack or not pack['available']:
                return {'error': 'Lastbook cannot tell which library this is, so it cannot repair it. Download a library instead.', 'code': 'unavailable'}
            model = self.manifest.model() if (ai or cur['model']) else None
            parent, target = self.current.parent, self.current
            work = parent / (DATA_NAME + WORK_SUFFIX)
            srcs = {f['name']: f['path'] for f in self.found() if f.get('size_ok') and f['kind'] in ('pack', 'model')}
            items = [{'id': pack['id'], 'kind': 'pack', 'title': pack['title'], 'state': 'waiting', 'bytes_done': 0,
                      'bytes_total': pack['installed_bytes'], 'rate_bps': 0, 'eta_s': None, 'error': None}]
            if model:
                items.append({'id': model['id'], 'kind': 'model', 'title': model['title'], 'state': 'waiting', 'bytes_done': 0,
                              'bytes_total': model['size'], 'rate_bps': 0, 'eta_s': None, 'error': None})
            names = [f['name'] for f in pack['files']] + ([model['file']] if model else [])
            self.job = {'id': uuid.uuid4().hex[:12], 'state': 'waiting', 'items': items, 'error': None, 'started': _now(), 'folder': str(target),
                        'repair': True,
                        'plan': {'pack': pack, 'model': model, 'parent': str(parent), 'target': str(target), 'work': str(work),
                                 'sources': {k: v for k, v in srcs.items() if k in names}, 'explicit': False, 'retried': {},
                                 'switch': True, 'repair': True}}
            s = self._settings()
            s['work'] = str(work)
            self._save_settings(s)
            self._save_job()
            self._run()
            return self.public_job()

    def _check_library(self, it, lib, control):
        """Files of the open library that are missing or differ from its pack-manifest.tsv (path, bytes, sha256)."""
        try:
            rows = [l.split('\t') for l in (lib / 'pack-manifest.tsv').read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
            rows = [(r[0], int(r[1]), r[2]) for r in rows]
        except (OSError, ValueError, IndexError):
            return ['pack-manifest.tsv']
        total = sum(r[1] for r in rows) or 1
        tracker, done, bad = _Item(it), 0, []
        self._set(it, 'verifying', bytes_done=0, bytes_total=total)
        for rel, size, digest in rows:
            p = lib / rel
            if '..' in Path(rel).parts or Path(rel).is_absolute() or not p.is_file() or p.stat().st_size != size:
                bad.append(rel)
                done += size
                tracker.progress(done, total, 'verifying')
                continue
            base = done
            if _sha256(p, control, lambda d, t: tracker.progress(base + d, total, 'verifying')) != digest:
                bad.append(rel)
            done = base + size
        return bad

    def _run(self):
        self.control = download.Control()
        self.thread = threading.Thread(target=self._work, args=(self.control,), daemon=True, name='setup-job')
        self.thread.start()

    def pause(self):
        with self.lock:
            if self.job and self.job['state'] in ACTIVE and self.control:
                self.control.stop('paused')
        self._join()
        return self.public_job()

    def resume(self):
        with self.lock:
            if self.job and self.job['state'] == 'paused':
                self.job['state'] = 'waiting'
                self._save_job()
                self._run()
        return self.public_job()

    def retry(self):
        with self.lock:
            if self.job and self.job['state'] == 'failed':
                self.job['state'], self.job['error'] = 'waiting', None
                self.job['plan']['retried'] = {}
                for it in self.job['items']:
                    if it['state'] != 'done':
                        it['state'], it['error'] = 'waiting', None
                self._save_job()
                self._run()
        return self.public_job()

    def cancel(self):
        with self.lock:
            job = self.job
            if not job:
                return None
            if job['state'] in ACTIVE and self.control:
                self.control.stop('cancelled')
        self._join()
        with self.lock:
            if job['state'] != 'done' or job['plan'].get('switch'):     # a staged library not yet switched to can still be dropped
                self._clean(job)
                try:
                    (Path(job['plan']['work']) / install.PENDING).unlink()
                except OSError:
                    pass
                job['state'] = 'failed'
                job['error'] = {'code': 'cancelled', 'message': 'Cancelled. Nothing was changed.'}
                for it in job['items']:
                    if it['state'] != 'done':
                        it['state'] = 'failed'
                self._save_job()
        return self.public_job()

    def _join(self):
        t = self.thread
        if t and t is not threading.current_thread():
            t.join(30)

    def _clean(self, job):
        """What the job made in its work folder goes; the person's own files and any library stay."""
        work = Path(job['plan']['work'])
        for sub in ('downloads', 'unpack'):
            shutil.rmtree(work / sub, ignore_errors=True)

    def use(self, path):
        p = Path(path or '').expanduser()
        if not str(path or '').strip() or not p.exists():
            return {'error': 'Lastbook cannot find that file or folder.', 'code': 'missing'}
        if p.is_dir():
            lib = p if install.is_library(p) else p / DATA_NAME
            if not install.is_library(lib):
                known = {f['name'] for pk in self.manifest.current['packs'] for f in pk['files']}
                inside = sorted(c for c in p.iterdir() if c.name in known and c.is_file()) if p.is_dir() else []
                if inside:          # a folder holding a pack's zip: the picker chooses folders
                    return self.use(str(inside[0]))
                return {'error': f'“{p.name}” is not a Lastbook library. Choose the folder called {DATA_NAME}.', 'code': 'not_library'}
            if not os.access(lib, os.W_OK):
                return {'error': f'Lastbook cannot save in “{lib.name}”. Move it somewhere you can save to, then choose it there.', 'code': 'folder'}
            with self.lock:
                if self.job and self.job['state'] in ACTIVE:
                    return {'error': 'A download is under way. Pause or cancel it first.', 'code': 'busy'}
                self.job = {'id': uuid.uuid4().hex[:12], 'state': 'done', 'error': None, 'started': _now(), 'folder': str(lib),
                            'items': [{'id': 'library', 'kind': 'pack', 'title': lib.name, 'state': 'done', 'bytes_done': 0, 'bytes_total': 0,
                                       'rate_bps': 0, 'eta_s': None, 'error': None}],
                            'plan': {'use_library': str(lib), 'work': str(lib.parent / (DATA_NAME + WORK_SUFFIX)), 'target': str(lib)}}
                return self.public_job()
        name = p.name
        for pk in self.manifest.current['packs']:
            for f in pk['files']:
                if f['name'] == name:
                    if p.stat().st_size != f['size']:
                        return {'error': f'That file is {_gb(p.stat().st_size)}, not the {_gb(f["size"])} of the published {name}. The download may not have finished.', 'code': 'size'}
                    if not pk['available']:
                        return {'error': 'That library is not available in this version.', 'code': 'unavailable'}
                    return self.start(pk['id'], False, None, {name: str(p)}, explicit=True)
        m = self.manifest.model()
        if m and name == m['file']:
            if p.stat().st_size != m['size']:
                return {'error': f'That file is {_gb(p.stat().st_size)}, not the {_gb(m["size"])} of the model. The download may not have finished.', 'code': 'size'}
            self.sources[name] = str(p)
            if self.mode == 'manage':
                return self.start(None, True, None, {name: str(p)}, explicit=True)
            return self.public_job() or {'job': None, 'noted': True}
        return {'error': 'That is not a file Lastbook knows. Choose a Lastbook library zip or the model file.', 'code': 'unknown'}

    def finish(self):
        with self.lock:
            job = self.job
            if not job or job['state'] != 'done':
                return {'error': 'Setup has not finished yet.', 'code': 'not_done'}
            plan = job['plan']
            folder = plan.get('use_library') or plan['target']
        if not self.on_finish:
            return {'ok': True, 'restart': True, 'folder': folder}
        threading.Timer(0.4, self.on_finish, [folder]).start()     # after this answer has reached the window
        return {'ok': True, 'folder': folder}

    def pick(self):
        """{path, free_bytes, disk}, or {path: null, cancelled: true}."""
        path = None
        if self.pick_folder:
            try:
                path = self.pick_folder() or None
            except Exception:
                traceback.print_exc()
        if not path:
            return {'path': None, 'cancelled': True}
        try:
            free, _ = hardware.disk_of(path)
        except OSError:
            free = None
        return {'path': path, 'free_bytes': free, 'disk': hardware.disk_name(path)}

    def remove_ai(self):
        """Manage mode: the model file goes from the open library. The library itself is not touched."""
        m = self.manifest.model()
        if self.mode != 'manage' or not self.current or not m:
            return {'error': 'There is no local AI in this library to remove.', 'code': 'nothing'}
        with self.lock:
            if self.job and self.job['state'] in ACTIVE:
                return {'error': 'A download is under way. Pause or cancel it first.', 'code': 'busy'}
        p = self.current / 'models' / m['file']
        if not p.is_file():
            return {'error': 'There is no local AI in this library to remove.', 'code': 'nothing'}
        llm = self.llm()
        local = getattr(llm, 'LOCAL', None) if llm else None
        try:
            if local is not None and hasattr(local, 'stop'):
                local.stop('removed')
        except Exception:
            traceback.print_exc()
        size = p.stat().st_size
        try:
            p.unlink()
        except OSError as e:
            return {'error': f'Lastbook could not remove the model file ({type(e).__name__}). Quit anything using it, then try again.', 'code': 'folder'}
        if local is not None and getattr(local, '_started', False):
            threading.Thread(target=local.discover, daemon=True).start()
        return {'ok': True, 'freed_bytes': size}

    def delete_old(self, path):
        s = self._settings()
        olds = s.get('old', [])
        if path not in olds:
            return {'error': 'Lastbook only deletes an old library it moved aside itself.', 'code': 'unknown'}
        p = Path(path)
        if not p.name.startswith(DATA_NAME + '.old-'):
            return {'error': 'That is not an old library.', 'code': 'unknown'}

        def gone():
            shutil.rmtree(p, ignore_errors=True)
            s2 = self._settings()
            s2['old'] = [o for o in s2.get('old', []) if o != path or Path(o).exists()]
            self._save_settings(s2)
            self.deleting.discard(path)
        self.deleting.add(path)
        threading.Thread(target=gone, daemon=True, name='setup-delete-old').start()
        return {'ok': True, 'deleting': path}

    # ------------------------------------------------------------------------------------------------------ the work --
    def _set(self, it, state, **kw):
        with self.lock:
            if it is not None:
                it['state'] = state
                it.update(kw)
            self.job['state'] = state
            self._save_job()

    def _fail(self, it, code, message):
        with self.lock:
            err = {'code': code, 'message': message}
            if it is not None:
                it['state'], it['error'], it['rate_bps'], it['eta_s'] = 'failed', err, 0, None
            self.job['state'], self.job['error'] = 'failed', err
            self._save_job()
        print(f'setup: failed ({code}): {message}', flush=True)

    def _work(self, control):
        job = self.job
        plan = job['plan']
        it = None
        try:
            work = Path(plan['work'])
            (work / 'downloads').mkdir(parents=True, exist_ok=True)
            for it in job['items']:
                if it['state'] == 'done':
                    continue
                if it['kind'] == 'pack':
                    self._do_pack(it, plan, work, control)
                else:
                    self._do_model(it, plan, work, control)
                with self.lock:
                    it['state'], it['rate_bps'], it['eta_s'] = 'done', 0, None
                    self._save_job()
            it = None
            self._finish_job(plan, work)
        except download.Stopped as s:
            with self.lock:
                if s.why == 'paused':
                    if it is not None:
                        it['state'], it['rate_bps'], it['eta_s'] = 'paused', 0, None
                    job['state'] = 'paused'
                self._save_job()
        except download.Failed as e:
            self._fail(it, e.code, e.message)
        except install.Refused as e:
            self._fail(it, e.code, e.message)
        except OSError as e:
            if download.disk_full(e):
                self._fail(it, 'no_space', 'The disk filled up. Free some space, then try again.')
            else:
                traceback.print_exc()
                self._fail(it, 'unpack' if it and job['state'] == 'unpacking' else 'network', f'Lastbook could not write a file ({type(e).__name__}: {e.strerror or e}).')
        except Exception as e:
            traceback.print_exc()
            self._fail(it, 'activate', f'Setup stopped on an internal error ({type(e).__name__}).')

    def _get_file(self, it, f, plan, work, control, offset):
        """The file, checked against its SHA-256: one already on this computer, or a download. Returns its path."""
        tracker = _Item(it)
        name, src = f['name'], plan['sources'].get(f['name'])
        if src and os.path.isfile(src) and name in plan.setdefault('verified', []):
            return src, False
        if src and os.path.isfile(src):
            self._set(it, 'verifying')
            digest = _sha256(src, control, lambda d, t: tracker.progress(offset + d, it['bytes_total'], 'verifying'))
            if digest == f['sha256']:
                plan['verified'].append(name)
                return src, False
            if plan.get('explicit'):
                raise download.Failed('checksum', f'The file {name} on this computer is not the published one. Download it instead.')
            print(f'setup: {src} does not match; downloading instead', flush=True)
            plan['sources'].pop(name, None)
        dest = work / 'downloads' / name
        while True:
            self._set(it, 'downloading')
            d = download.Download(f['url'], dest, f['size'], f['sha256'], control,
                                  lambda done, total, phase: tracker.progress(offset + done, it['bytes_total'], phase),
                                  allowed=self.allowed, context=self.context)
            try:
                return d.run(), True
            except download.BadChecksum:
                tries = plan['retried'].get(name, 0)
                if tries >= 1:
                    raise download.Failed('checksum', f'{name} did not match its published checksum twice. The file on the server may be damaged; try again later.')
                plan['retried'][name] = tries + 1
                print(f'setup: {name} failed its checksum; downloading it once more', flush=True)

    def _do_pack(self, it, plan, work, control):
        pack = plan['pack']
        if plan.get('repair') and 'damaged' not in plan:
            bad = self._check_library(it, Path(plan['target']), control)
            plan['damaged'] = bad
            print(f'setup: repair found {len(bad)} damaged or missing files', flush=True)
            if not bad:
                plan['switch'] = False
                return
            need = install.need_bytes(pack, None, set(plan['sources']))
            free, _ = hardware.disk_of(work.parent)
            if free < need:
                raise download.Failed('no_space', f'{len(bad)} files need fetching again. That needs {_gb(need)} free, and the disk has {_gb(free)}.')
            with self.lock:
                it['bytes_total'], it['bytes_done'] = pack['download_bytes'], 0
        staged = work / 'unpack'
        got, offset = [], 0
        for f in pack['files']:
            path, ours = self._get_file(it, f, plan, work, control, offset)
            got.append((path, ours))
            offset += f['size']
        tracker = _Item(it)
        self._set(it, 'unpacking', bytes_done=0, bytes_total=pack['installed_bytes'])
        total = sum(install.check_zip(path, pack['installed_bytes'])[1] for path, _ in got)   # every member checked before any is written
        still = max(total - _tree_size(staged), 0)
        free, _ = hardware.disk_of(work)
        if free < still + 512 * 2 ** 20:
            raise download.Failed('no_space', f'Unpacking needs {_gb(still)} free, and the disk has {_gb(free)}. Free some space, then try again.')
        for path, _ in got:
            lib = install.unpack(path, staged, pack['installed_bytes'], control, lambda d, t: tracker.progress(d, t, 'unpacking'))
        install._write_json(lib / 'setup-pack.json', {'pack': pack['id'], 'installed': _now(), 'files': [f['name'] for f in pack['files']]})
        for path, ours in got:
            if ours:
                os.unlink(path)

    def _do_model(self, it, plan, work, control):
        m = plan['model']
        path, ours = self._get_file(it, {'name': m['file'], 'url': m['url'], 'size': m['size'], 'sha256': m['sha256']}, plan, work, control, 0)
        lib = (work / 'unpack' / DATA_NAME) if plan['switch'] else Path(self.current or plan['target'])
        dest = lib / 'models' / m['file']
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._set(it, 'activating')
        if ours or _same_disk(path, dest):
            os.replace(path, dest)
        else:
            tmp = dest.with_name(dest.name + '.partial')
            shutil.copyfile(path, tmp)
            os.replace(tmp, dest)
        plan['model_file'] = str(Path(plan['target']) / 'models' / m['file']) if plan['switch'] else str(dest)
        if not plan['switch'] and self.current:      # the library open now: the AI can use it at once
            self._mark_checked(dest)

    def _mark_checked(self, path):
        llm = self.llm()
        if not llm:
            return
        try:
            llm.mark_checked(path)
            if getattr(llm, 'LOCAL', None) and getattr(llm.LOCAL, '_started', False):
                threading.Thread(target=llm.LOCAL.discover, daemon=True).start()
        except Exception as e:
            print('setup: mark_checked:', type(e).__name__, e, flush=True)

    def _finish_job(self, plan, work):
        with self.lock:
            if plan['switch']:
                lib = work / 'unpack' / DATA_NAME
                if not install.is_library(lib):
                    raise install.Refused('activate', 'The new library is not complete.')
                install.stage_switch(work, lib, plan['target'], plan.get('model_file'))
            self.job['state'] = 'done'
            for it in self.job['items']:
                it['rate_bps'], it['eta_s'] = 0, None
            self._save_job()


def _margin(total):
    """Room left free beyond what an install needs: 5% of the disk, at least 5 GB and at most 20 GB (5% of an 8 TB disk would
    rule out every library)."""
    return max(RECOMMEND_MARGIN, min(int((total or 0) * 0.05), RECOMMEND_MARGIN_MAX))


def _tree_size(p):
    n = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


# ------------------------------------------------------------------------------------------------ startup and the app --
def startup(settings_dir):
    """app/main.py calls this first: a staged switch is made now, before the engine opens anything. Returns the library to open
    (or None to look as usual) and a note: {target, old, model_file, error}."""
    settings_dir = Path(settings_dir)
    try:
        s = json.loads((settings_dir / 'setup.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, None
    work = s.get('work')
    if not work:
        return None, None
    lib, note = install.apply_pending(work)
    return lib, note


def opened(settings_dir, data, note):
    """The library opened. Record the old one for deleting later, mark the model checked, and clear the work folder."""
    settings_dir = Path(settings_dir)
    try:
        s = json.loads((settings_dir / 'setup.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        s = {}
    work = Path(s['work']) if s.get('work') else None
    if note and note.get('model_file') and os.path.isfile(note['model_file']):
        try:
            import llm_local      # imported here, after LASTBOOK_DATA names the library: its state file lives there
            llm_local.mark_checked(note['model_file'])
        except Exception as e:
            print('setup: mark_checked:', type(e).__name__, e, flush=True)
    if note and note.get('old') and note['old'] not in s.get('old', []):
        s.setdefault('old', []).append(note['old'])
    if work:
        install.confirm(work)
        try:
            job = json.loads((work / 'job.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            job = None
        if note or (job and job.get('state') == 'done'):
            shutil.rmtree(work, ignore_errors=True)
            s.pop('work', None)
    s['old'] = [o for o in s.get('old', []) if Path(o).exists()]
    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
        install._write_json(settings_dir / 'setup.json', s)
    except OSError:
        pass


SETUP = None


def configure(**kw):
    global SETUP
    SETUP = Setup(**kw)
    return SETUP


def _default():
    global SETUP
    if SETUP is None:
        from engine import paths
        if sys.platform == 'win32':
            settings = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming') / 'Lastbook'
        else:
            settings = Path.home() / 'Library' / 'Application Support' / 'Lastbook'
        SETUP = Setup('manage', settings, paths.DATA.parent, current=paths.DATA)
    return SETUP


ROUTES = {
    ('GET', 'state'): lambda s, b: s.state(),
    ('GET', 'job'): lambda s, b: s.public_job(),
    ('POST', 'start'): lambda s, b: s.start(b.get('pack'), bool(b.get('ai')), b.get('folder'), repair=bool(b.get('repair'))),
    ('POST', 'pause'): lambda s, b: s.pause(),
    ('POST', 'resume'): lambda s, b: s.resume(),
    ('POST', 'cancel'): lambda s, b: s.cancel(),
    ('POST', 'retry'): lambda s, b: s.retry(),
    ('POST', 'use'): lambda s, b: s.use(b.get('path')),
    ('POST', 'finish'): lambda s, b: s.finish(),
    ('POST', 'pick'): lambda s, b: s.pick(),
    ('POST', 'delete-old'): lambda s, b: s.delete_old(b.get('path')),
    ('POST', 'remove-ai'): lambda s, b: s.remove_ai(),
}


def _send_json(h, obj, status=200):
    data = json.dumps(obj, separators=(',', ':')).encode()
    h.send_response(status)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    if h.command != 'HEAD':
        h.wfile.write(data)


def handle(h, method, path):
    """Answers one /api/setup/ request on a BaseHTTPRequestHandler h."""
    if h.client_address[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
        return _send_json(h, {'error': 'Setup is only open on this computer.'}, 403)
    name = path[len('/api/setup/'):].strip('/')
    fn = ROUTES.get(('GET' if method == 'HEAD' else method, name))
    if not fn:
        return _send_json(h, {'error': 'not found'}, 404)
    body = {}
    if method == 'POST':
        try:
            n = int(h.headers.get('Content-Length') or 0)
            if n < 0 or n > MAX_BODY:
                return _send_json(h, {'error': 'request too large'}, 413)
            body = json.loads(h.rfile.read(n) or b'{}') if n else {}
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return _send_json(h, {'error': 'bad request'}, 400)
    try:
        out = fn(SETUP or _default(), body)
    except Exception as e:
        traceback.print_exc()
        return _send_json(h, {'error': f'Setup stopped on an internal error ({type(e).__name__}).'}, 500)
    status = 200
    if isinstance(out, dict) and out.get('error') and 'code' in out:
        status = 409 if out['code'] in ('busy', 'not_done') else 400 if out['code'] != 'no_space' else 507
    return _send_json(h, out, status)


# ------------------------------------------------------------------------------------------------ setup mode's Handler --
def web_dir():
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'web'
    return Path(__file__).resolve().parents[2] / 'web'


TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml',
         '.png': 'image/png', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.woff2': 'font/woff2'}


class SetupHandler(BaseHTTPRequestHandler):
    """All there is in setup mode: the setup page, the app's web files, and /api/setup/*."""
    server_version = 'Lastbook'
    sys_version = ''
    NO_CODE_CSP = ("default-src 'none'; script-src 'none'; connect-src 'none'; worker-src 'none'; object-src 'none'; manifest-src 'none'; "
                   "base-uri 'none'; form-action 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:")
    SAVED_PAGE_CSP = 'sandbox; ' + NO_CODE_CSP

    def log_message(self, *a):
        pass

    def _path(self):
        import urllib.parse
        return urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)

    def _static(self, p):
        try:
            data = p.read_bytes()
        except OSError:
            return _send_json(self, {'error': 'not found'}, 404)
        self.send_response(200)
        self.send_header('Content-Type', TYPES.get(p.suffix, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def do_GET(self):
        path = self._path()
        if '\0' in path or '/..' in path or '\\' in path:
            return _send_json(self, {'error': 'not found'}, 404)
        web = web_dir()
        if path in ('/', '/index.html', '/ui/setup.html'):
            return self._static(web / 'setup.html')
        if path.startswith('/ui/'):
            p = (web / path[4:]).resolve()
            if web.resolve() in p.parents and p.is_file():
                return self._static(p)
            return _send_json(self, {'error': 'not found'}, 404)
        if path.startswith('/api/setup/'):
            return handle(self, self.command, path)
        return _send_json(self, {'error': 'not found'}, 404)

    do_HEAD = do_GET

    def do_POST(self):
        path = self._path()
        if path.startswith('/api/setup/'):
            return handle(self, 'POST', path)
        return _send_json(self, {'error': 'not found'}, 404)


class SetupServer:
    """What app/bridge.py needs of an engine module: its Handler."""
    Handler = SetupHandler
