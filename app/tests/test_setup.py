#!/usr/bin/env python3
"""First-run setup, engine side (engine/setup/), against a local HTTPS test server. No real internet, never the real home folder.

  derived/app-build/mac-venv/bin/python -B app/tests/test_setup.py [-v] [Class.test_name]
  LASTBOOK_FULL_DISK=1 ...   also runs the full-disk case on a small disk image (hdiutil, macOS only)

The test server lives only in this file: it serves a small fake pack and model over HTTPS on 127.0.0.1 with a certificate made
for the run, and can cut the connection mid-file, send wrong bytes, change the file's ETag, ignore Range, or redirect anywhere.
The product's allowlist is not touched: tests pass their own `allowed` and TLS context to the downloader. Never packaged.
"""
import hashlib, http.server, io, json, os, shutil, signal, socketserver, ssl, subprocess, sys, tempfile, threading, time, unittest, zipfile
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE.parent), str(ROOT)]
from engine.setup import api, download, hardware, install, manifest  # noqa: E402

ALLOWED = {'localhost'}
MiB = 1024 * 1024


# ------------------------------------------------------------------------------------------------------------ test data --
def make_pack(path, files=None, extra=None):
    """A zip shaped like a real pack: everything under LastbookData/, stored."""
    files = files or {'library-data/catalog.json': b'{"records": []}', 'pack.json': b'{"name": "small"}',
                      'library-data/big.bin': os.urandom(3 * MiB), 'derived/geo/map.sqlite': os.urandom(MiB)}
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('LastbookData/', b'')
        for name, data in files.items():
            z.writestr('LastbookData/' + name, data)
        for info, data in (extra or []):
            z.writestr(info, data)
    return sum(len(v) for v in files.values()) + sum(len(d) for _, d in (extra or []))


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Files:
    """What the test server serves, and how it misbehaves. name -> bytes."""

    def __init__(self):
        self.data, self.etag, self.log = {}, {}, []
        self.cut_after = {}       # name -> bytes after which the next answer is cut (once per entry in the list)
        self.corrupt = {}         # name -> how many more answers carry a flipped byte
        self.ignore_range = set()
        self.redirect = {}        # name -> Location
        self.pace = 0             # seconds to sleep per 64 KiB
        self.lock = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def do_GET(self):
        F = self.server.files
        name = self.path.split('?')[0].lstrip('/')
        with F.lock:
            F.log.append((name, self.headers.get('Range'), self.headers.get('If-Range')))
        if name in F.redirect:
            self.send_response(302)
            self.send_header('Location', F.redirect[name])
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if name not in F.data:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        body = F.data[name]
        with F.lock:
            if F.corrupt.get(name):
                F.corrupt[name] -= 1
                body = bytes([body[0] ^ 0xff]) + body[1:]
        start, rng = 0, self.headers.get('Range')
        if rng and name not in F.ignore_range:     # like R2: If-Range is ignored
            start = int(rng.split('=')[1].split('-')[0])
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{len(body) - 1}/{len(body)}')
        else:
            self.send_response(200)
        self.send_header('Content-Length', str(len(body) - start))
        self.send_header('ETag', F.etag.get(name, '"e1"'))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        cut = None
        with F.lock:
            if F.cut_after.get(name):
                cut = F.cut_after[name].pop(0)
        sent = start
        try:
            while sent < len(body):
                n = min(64 * 1024, len(body) - sent)
                if cut is not None and sent + n > cut:
                    self.wfile.write(body[sent:cut])
                    self.wfile.flush()
                    self.close_connection = True
                    self.connection.shutdown(2)
                    return
                self.wfile.write(body[sent:sent + n])
                sent += n
                if F.pace:
                    time.sleep(F.pace)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


class TLSServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def certificate(folder):
    key, crt = folder / 'key.pem', folder / 'cert.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                    '-addext', 'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(crt)],
                   check=True, capture_output=True)
    return key, crt


def start_server(folder, files):
    key, crt = certificate(folder)
    srv = TLSServer(('127.0.0.1', 0), Handler)
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(crt, key)
    srv.socket = sctx.wrap_socket(srv.socket, server_side=True)
    srv.files = files
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cctx = ssl.create_default_context(cafile=str(crt))
    return srv, cctx, f'https://localhost:{srv.server_address[1]}'


class Control:
    def __init__(self):
        self.ev = threading.Event()

    def check(self):
        pass


# ------------------------------------------------------------------------------------------------------------- base --
class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_class = Path(tempfile.mkdtemp(prefix='lastbook-setup-srv-'))
        cls.files = Files()
        cls.srv, cls.ctx, cls.base = start_server(cls.tmp_class, cls.files)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp_class, ignore_errors=True)

    def setUp(self):
        F = self.files
        F.data.clear(); F.etag.clear(); F.log.clear(); F.cut_after.clear(); F.corrupt.clear(); F.ignore_range.clear(); F.redirect.clear()
        F.pace = 0
        self.tmp = Path(tempfile.mkdtemp(prefix='lastbook-setup-')).resolve()
        self.home = self.tmp / 'home'
        for d in ('Downloads', 'Documents', 'Desktop'):
            (self.home / d).mkdir(parents=True)
        self.settings = self.tmp / 'settings'
        self.parent = self.tmp / 'place'
        zpath = self.tmp / 'Lastbook-Small.zip'
        self.installed = make_pack(zpath)
        self.zip = zpath.read_bytes()
        self.model = os.urandom(2 * MiB + 123)
        F.data['Lastbook-Small.zip'] = self.zip
        F.data['model.gguf'] = self.model
        self.marked = []
        self.llm = mock.Mock()
        self.llm.mark_checked = lambda p: self.marked.append(str(p))
        self.llm.LOCAL = None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def manifest(self, zip_sha=None, model_sha=None):
        m = {'version': 1, 'published': '2026-11-12',
             'packs': [{'id': 'small', 'title': 'Small', 'summary': 's', 'records': 3, 'installed_bytes': self.installed, 'available': True,
                        'files': [{'name': 'Lastbook-Small.zip', 'url': f'{self.base}/Lastbook-Small.zip', 'size': len(self.zip),
                                   'sha256': zip_sha or sha(self.zip), 'kind': 'zip'}]},
                       {'id': 'all', 'title': 'All', 'available': False, 'files': []}],
             'models': [{'id': 'gemma', 'title': 'Gemma', 'file': 'model.gguf', 'url': f'{self.base}/model.gguf', 'size': len(self.model),
                         'sha256': model_sha or sha(self.model), 'memory_bytes': 19_027_384_256, 'available': True}]}
        v = manifest.validate(m, ALLOWED)
        self.assertIsNotNone(v)
        return manifest.Manifest(bundled=v, remote=None, allowed=ALLOWED, context=self.ctx)

    def setup(self, mode='first-run', current=None, **kw):
        kw.setdefault('manifest', self.manifest())
        return api.Setup(mode, self.settings, self.parent, current=current, allowed=ALLOWED, context=self.ctx, home=self.home,
                         llm_local=self.llm, **kw)

    def wait(self, s, states=('done', 'failed', 'paused'), timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = s.public_job()
            if j and j['state'] in states:
                if s.thread:
                    s.thread.join(10)
                return s.public_job()
            time.sleep(0.02)
        self.fail(f'job never reached {states}: {s.public_job()}')


def fast_backoff():
    return mock.patch.object(download, 'BACKOFF', (0.05,) * 6)


# ----------------------------------------------------------------------------------------------------------- tests --
class Allowlist(unittest.TestCase):
    def test_product_hosts(self):
        ok = ['https://downloads.lastbook.org/1.0.0/Lastbook-Small.zip', 'https://pub-28c3cc06eb774c5cac057e6c9343efbd.r2.dev/x.zip',
              'https://huggingface.co/unsloth/x/resolve/abc/f.gguf?download=true', 'https://cas-bridge.xethub.hf.co/xet-bridge-us/abc?X-Amz=1',
              'https://us.gcp.cdn.hf.co/x']
        bad = ['http://downloads.lastbook.org/x', 'https://downloads.lastbook.org:8443/x', 'https://evil.com/x', 'https://hf.co.evil.com/x',
               'https://user:pw@downloads.lastbook.org/x', 'https://lastbook.org/x', 'https://other.r2.dev/x', 'ftp://huggingface.co/x',
               'https://.hf.co/x', 'https://localhost/x', 'https://127.0.0.1/x', 'file:///etc/passwd', 'https://downloads.lastbook.org.evil.com/x']
        for u in ok:
            self.assertTrue(download.url_allowed(u), u)
        for u in bad:
            self.assertFalse(download.url_allowed(u), u)

    def test_no_proxy(self):
        """http.client takes no proxy from the environment: a request with HTTPS_PROXY set still goes to the host named."""
        import inspect
        src = inspect.getsource(download)
        self.assertNotIn('urllib.request', src)
        self.assertNotIn('ProxyHandler', src)
        self.assertNotIn('set_tunnel', src)

    def test_only_module_with_connections(self):
        """In engine/setup/, only download.py touches http.client, socket connections or urllib.request."""
        for p in (ROOT / 'engine' / 'setup').glob('*.py'):
            if p.name == 'download.py':
                continue
            t = p.read_text()
            for word in ('http.client', 'urllib.request', 'socket.create_connection', 'HTTPSConnection', 'import socket'):
                self.assertNotIn(word, t, f'{p.name}: {word}')

    def test_bundled_manifest_urls(self):
        p = ROOT / 'derived' / 'release' / 'setup' / 'manifest-v1.json'
        if not p.is_file():
            self.skipTest('no bundled manifest built yet (packaging/release_manifest.py)')
        m = manifest.validate(json.loads(p.read_text()))
        self.assertIsNotNone(m)
        self.assertTrue(m['models'] and m['packs'])

    def test_fetched_manifest_keeps_bundled_entries(self):
        bundled = manifest.validate({'version': 1, 'published': '2026-11-12', 'packs': [
            {'id': 'small', 'available': True, 'installed_bytes': 5, 'files': [{'name': 'a.zip', 'url': 'https://downloads.lastbook.org/a.zip', 'size': 1, 'sha256': '0' * 64}]}],
            'models': [{'id': 'gemma', 'file': 'm.gguf', 'url': 'https://huggingface.co/m', 'size': 1, 'sha256': '1' * 64, 'memory_bytes': 1}]})
        fetched = manifest.validate({'version': 1, 'published': '2026-11-13', 'packs': [
            {'id': 'medium', 'available': True, 'installed_bytes': 9, 'files': [{'name': 'b.zip', 'url': 'https://downloads.lastbook.org/b.zip', 'size': 2, 'sha256': '2' * 64}]},
            {'id': 'small', 'title': 'Small v2', 'available': True, 'installed_bytes': 6, 'files': [{'name': 'a.zip', 'url': 'https://downloads.lastbook.org/a.zip', 'size': 3, 'sha256': '3' * 64}]}],
            'models': []})
        m = manifest.Manifest(bundled=bundled, remote='https://downloads.lastbook.org/manifest-v1.json')
        with mock.patch.object(download, 'fetch_small', lambda *a, **k: json.dumps(fetched).encode()):
            m._fetch()
        self.assertEqual(m.source, 'fetched')
        self.assertEqual([p['id'] for p in m.current['packs']], ['medium', 'small'])
        self.assertEqual(m.pack('small')['title'], 'Small v2')          # in both: the fetched entry
        self.assertEqual(m.model()['id'], 'gemma')                        # fetched had none: the bundled one stays

    def test_fetched_manifest_rules(self):
        m = {'version': 1, 'packs': [{'id': 'small', 'available': True, 'installed_bytes': 5,
                                      'files': [{'name': 'a.zip', 'url': 'https://evil.com/a.zip', 'size': 1, 'sha256': '0' * 64}]}], 'models': []}
        self.assertIsNone(manifest.validate(m))
        m['packs'][0]['files'][0]['url'] = 'https://downloads.lastbook.org/a.zip'
        self.assertIsNotNone(manifest.validate(m))
        self.assertIsNone(manifest.validate({**m, 'version': 2}))
        m['packs'][0]['files'][0]['name'] = '../a.zip'
        self.assertIsNone(manifest.validate(m))


class Downloads(Base):
    def dl(self, name, sha256=None, size=None, control=None):
        data = self.files.data[name]
        return download.Download(f'{self.base}/{name}', self.tmp / 'dl' / name, size or len(data), sha256 or sha(data),
                                 control or download.Control(), allowed=ALLOWED, context=self.ctx)

    def test_plain(self):
        p = self.dl('model.gguf').run()
        self.assertEqual(Path(p).read_bytes(), self.model)
        self.assertFalse(Path(p + '.part').exists())

    def test_cut_mid_file_resumes_with_range(self):
        self.files.cut_after['model.gguf'] = [700_000, 1_500_000]
        with fast_backoff():
            p = self.dl('model.gguf').run()
        self.assertEqual(sha(Path(p).read_bytes()), sha(self.model))
        ranges = [r for n, r, _ in self.files.log if n == 'model.gguf']
        self.assertEqual(ranges[0], None)
        self.assertTrue(all(r and r.startswith('bytes=') for r in ranges[1:]), ranges)
        self.assertEqual(len(ranges), 3)

    def test_etag_changed_starts_over(self):
        """R2 answers 206 whatever If-Range says, so the ETag is compared here."""
        d = self.dl('model.gguf')
        os.makedirs(os.path.dirname(d.part), exist_ok=True)
        Path(d.part).write_bytes(b'x' * 600_000)          # bytes of an older copy of the file
        Path(d.meta).write_text(json.dumps({'url': d.url, 'size': d.size, 'sha256': d.sha256, 'etag': '"old"', 'bytes_done': 600_000}))
        self.files.etag['model.gguf'] = '"new"'
        d.run()
        self.assertEqual(Path(d.dest).read_bytes(), self.model)
        self.assertEqual([r for _, r, _ in self.files.log], ['bytes=600000-', None])   # tried to resume, then started over

    def test_server_ignores_range(self):
        self.files.cut_after['model.gguf'] = [500_000]
        self.files.ignore_range.add('model.gguf')
        with fast_backoff():
            p = self.dl('model.gguf').run()
        self.assertEqual(Path(p).read_bytes(), self.model)

    def test_wrong_checksum(self):
        d = self.dl('model.gguf', sha256='0' * 64)
        with self.assertRaises(download.BadChecksum):
            d.run()
        self.assertFalse(Path(d.part).exists())

    def test_redirects(self):
        self.files.redirect['a'] = f'{self.base}/model.gguf'
        d = download.Download(f'{self.base}/a', self.tmp / 'x', len(self.model), sha(self.model), download.Control(), allowed=ALLOWED, context=self.ctx)
        self.assertEqual(Path(d.run()).read_bytes(), self.model)
        for where in ('https://evil.example/model.gguf', f'http://localhost:{self.srv.server_address[1]}/model.gguf'):
            self.files.redirect['b'] = where
            d = download.Download(f'{self.base}/b', self.tmp / 'y', 10, '0' * 64, download.Control(), allowed=ALLOWED, context=self.ctx)
            with self.assertRaises(download.Failed) as e:
                d.run()
            self.assertEqual(e.exception.code, 'network')
        self.files.redirect['c'] = f'{self.base}/c'
        d = download.Download(f'{self.base}/c', self.tmp / 'z', 10, '0' * 64, download.Control(), allowed=ALLOWED, context=self.ctx)
        with self.assertRaises(download.Failed):
            d.run()

    def test_refuses_unknown_host_before_connecting(self):
        d = download.Download('https://example.com/x', self.tmp / 'x', 10, '0' * 64, download.Control())
        with self.assertRaises(download.Failed):
            d.run()

    def test_untrusted_certificate(self):
        d = download.Download(f'{self.base}/model.gguf', self.tmp / 'x', len(self.model), sha(self.model), download.Control(), allowed=ALLOWED,
                              context=ssl.create_default_context())
        with fast_backoff(), self.assertRaises(download.Failed) as e:
            d.run()
        self.assertEqual(e.exception.code, 'network')

    def test_pause_mid_file(self):
        self.files.pace = 0.01
        c = download.Control()
        d = self.dl('model.gguf', control=c)
        threading.Timer(0.1, c.stop, ['paused']).start()
        with self.assertRaises(download.Stopped):
            d.run()
        self.assertGreater(d.done_bytes(), 0)
        self.assertLess(d.done_bytes(), len(self.model))
        self.files.pace = 0
        d.control = download.Control()
        self.assertEqual(Path(d.run()).read_bytes(), self.model)


class Unpacking(Base):
    def bad_zip(self, info, data=b'x'):
        p = self.tmp / 'bad.zip'
        make_pack(p, {'library-data/catalog.json': b'{}'}, [(info, data)])
        return p

    def test_guards(self):
        cases = ['LastbookData/../../escape.txt', '/etc/evil', 'Other/x', 'LastbookData\\..\\x', 'C:/x']
        link = zipfile.ZipInfo('LastbookData/link')
        link.external_attr = (0o120777 << 16)
        for case in cases + [link]:
            p = self.bad_zip(case)
            with self.assertRaises(install.Refused, msg=str(case)):
                install.unpack(p, self.tmp / 'out', 10 * MiB, Control(), lambda d, t: None)
        self.assertFalse((self.tmp / 'escape.txt').exists())
        self.assertFalse((self.tmp / 'out' / 'LastbookData' / 'library-data').exists())   # nothing written: every member is checked first

    def test_size_check(self):
        p = self.tmp / 'Lastbook-Small.zip'
        with self.assertRaises(install.Refused):
            install.unpack(p, self.tmp / 'out', self.installed // 2, Control(), lambda d, t: None)

    def test_resume_skips_whole_files(self):
        p = self.tmp / 'Lastbook-Small.zip'
        out = self.tmp / 'out'
        lib = install.unpack(p, out, self.installed, Control(), lambda d, t: None)
        big = lib / 'library-data' / 'big.bin'
        t = big.stat().st_mtime_ns
        (lib / 'derived' / 'geo' / 'map.sqlite').unlink()
        (lib / 'derived' / 'geo' / 'map.sqlite.partial').write_bytes(b'half')
        install.unpack(p, out, self.installed, Control(), lambda d, t: None)
        self.assertEqual(big.stat().st_mtime_ns, t)
        self.assertEqual((lib / 'derived' / 'geo' / 'map.sqlite').stat().st_size, MiB)


class Jobs(Base):
    def test_first_run_end_to_end(self):
        s = self.setup()
        st = s.state()
        self.assertEqual(st['mode'], 'first-run')
        self.assertEqual(st['recommend']['pack'], 'small')
        self.assertNotIn('url', json.dumps(st['manifest']))
        j = s.start('small', True)
        self.assertIsNone(j.get('error'), j)
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertEqual([i['state'] for i in j['items']], ['done', 'done'])
        work = self.parent / 'LastbookData.setup'
        self.assertTrue((work / install.PENDING).is_file())
        self.assertFalse((work / 'downloads' / 'Lastbook-Small.zip').exists())   # deleted once unpacked
        self.assertFalse((self.parent / 'LastbookData').exists())               # nothing in place until the switch
        finished = []
        s.on_finish = finished.append
        self.assertEqual(s.finish()['folder'], str(self.parent / 'LastbookData'))
        time.sleep(0.6)
        self.assertEqual(finished, [str(self.parent / 'LastbookData')])
        lib, note = api.startup(self.settings)                     # what main.py does on the next start
        self.assertEqual(lib, self.parent / 'LastbookData')
        self.assertTrue((lib / 'library-data' / 'catalog.json').is_file())
        self.assertEqual((lib / 'models' / 'model.gguf').read_bytes(), self.model)
        self.assertEqual(note['model_file'], str(lib / 'models' / 'model.gguf'))
        with mock.patch.dict(sys.modules, {'llm_local': self.llm}):
            api.opened(self.settings, lib, note)
        self.assertEqual(self.marked, [str(lib / 'models' / 'model.gguf')])
        self.assertFalse(work.exists())
        self.assertEqual(json.loads((lib / 'setup-pack.json').read_text())['pack'], 'small')

    def test_corrupt_once_then_good(self):
        self.files.corrupt['Lastbook-Small.zip'] = 1
        s = self.setup()
        s.start('small', False)
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertEqual(len([1 for n, _, _ in self.files.log if n == 'Lastbook-Small.zip']), 2)

    def test_corrupt_twice_fails_checksum(self):
        s = self.setup(manifest=self.manifest(zip_sha='1' * 64))
        s.start('small', False)
        j = self.wait(s)
        self.assertEqual(j['state'], 'failed')
        self.assertEqual(j['error']['code'], 'checksum')
        self.assertEqual(len([1 for n, _, _ in self.files.log if n == 'Lastbook-Small.zip']), 2)
        self.assertFalse((self.parent / 'LastbookData').exists())

    def test_network_failure_then_retry(self):
        self.files.data.pop('model.gguf')
        s = self.setup()
        s.start('small', True)
        j = self.wait(s)
        self.assertEqual(j['state'], 'failed')
        self.assertEqual(j['error']['code'], 'network')
        self.assertEqual([i['state'] for i in j['items']], ['done', 'failed'])
        self.files.data['model.gguf'] = self.model
        s.retry()
        self.assertEqual(self.wait(s)['state'], 'done')

    def test_pause_resume_cancel(self):
        self.files.pace = 0.01
        s = self.setup()
        s.start('small', False)
        time.sleep(0.3)
        j = s.pause()
        self.assertEqual(j['state'], 'paused')
        done = j['items'][0]['bytes_done']
        self.assertGreater(done, 0)
        s.resume()
        time.sleep(0.3)
        j = s.public_job()
        self.assertEqual(j['state'], 'downloading')
        self.assertGreater(j['items'][0]['bytes_done'], done)
        self.assertIn(self.files.log[-1][1].split('-')[0], [f'bytes={n}' for n in range(done - 10 ** 6, done + 10 ** 7)])
        j = s.cancel()
        self.assertEqual(j['error']['code'], 'cancelled')
        self.assertFalse((self.parent / 'LastbookData.setup' / 'downloads').exists())
        self.assertFalse((self.parent / 'LastbookData').exists())

    def test_rate_and_eta(self):
        self.files.pace = 0.06
        s = self.setup()
        s.start('small', False)
        time.sleep(1.8)
        it = s.public_job()['items'][0]
        s.cancel()
        self.assertGreater(it['rate_bps'], 0)
        self.assertIsNotNone(it['eta_s'])

    def test_no_space_refusal(self):
        s = self.setup()
        with mock.patch.object(hardware, 'disk_of', lambda p: (10 ** 9, 10 ** 12)):
            r = s.start('small', True)
        self.assertEqual(r['code'], 'no_space')
        self.assertGreater(r['need_bytes'], r['free_bytes'])
        self.assertIn('GB', r['error'])
        self.assertIsNone(s.public_job())

    def test_found_zip_is_used_without_network(self):
        (self.home / 'Downloads' / 'Lastbook-Small.zip').write_bytes(self.zip)
        s = self.setup()
        f = [x for x in s.found() if x['kind'] == 'pack']
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0]['size_ok'])
        j = s.use(f[0]['path'])
        self.assertIsNone(j.get('error'), j)
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertEqual(self.files.log, [])
        self.assertTrue((self.home / 'Downloads' / 'Lastbook-Small.zip').exists())   # the person's own file stays

    def test_found_zip_wrong_contents_downloads_instead(self):
        bad = bytearray(self.zip)
        bad[100] ^= 0xff
        (self.home / 'Downloads' / 'Lastbook-Small.zip').write_bytes(bad)
        s = self.setup()
        s.start('small', False)
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertEqual(len(self.files.log), 1)
        bad_explicit = self.setup()
        (self.parent / 'LastbookData.setup').exists() and shutil.rmtree(self.parent / 'LastbookData.setup')
        bad_explicit.use(str(self.home / 'Downloads' / 'Lastbook-Small.zip'))
        j = self.wait(bad_explicit)
        self.assertEqual(j['error']['code'], 'checksum')

    def test_use_existing_library(self):
        lib = self.tmp / 'elsewhere' / 'LastbookData'
        (lib / 'library-data').mkdir(parents=True)
        (lib / 'library-data' / 'catalog.json').write_text('{}')
        s = self.setup(look_for_libraries=lambda: [lib])
        self.assertIn(str(lib), [f['path'] for f in s.found() if f['kind'] == 'library'])
        self.assertEqual(s.use(str(lib.parent))['state'], 'done')
        self.assertEqual(s.finish()['folder'], str(lib))
        (self.tmp / 'empty').mkdir()
        self.assertEqual(s.use(str(self.tmp / 'empty'))['code'], 'not_library')
        s.job = None
        self.assertEqual(s.use(str(self.tmp))['items'][0]['kind'], 'pack')     # a folder holding a pack zip: that zip is used
        self.wait(s)

    def test_restart_mid_download(self):
        """A child process downloads and is killed; a new Setup finds the job paused and resumes with Range."""
        self.files.pace = 0.01
        work = self.parent / 'LastbookData.setup' / 'downloads'
        child = subprocess.Popen([sys.executable, '-B', __file__, '--child', json.dumps(self.child_config())], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            t0 = time.time()
            while time.time() - t0 < 30:
                p = work / 'Lastbook-Small.zip.part'
                if p.exists() and p.stat().st_size > 512 * 1024:
                    break
                time.sleep(0.05)
            else:
                self.fail('the child never started downloading: ' + child.stderr.read1(4000).decode())
        finally:
            child.kill()                      # SIGKILL on a Mac, TerminateProcess on Windows
            child.wait()
        had = (work / 'Lastbook-Small.zip.part').stat().st_size
        self.files.pace = 0
        self.files.log.clear()
        s = self.setup()
        j = s.public_job()
        self.assertEqual(j['state'], 'paused')
        self.assertGreaterEqual(j['items'][0]['bytes_done'], had)
        s.resume()
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertTrue(self.files.log[0][1].startswith('bytes='), self.files.log)

    def test_restart_mid_unpack(self):
        """Killed while unpacking: the new run carries on and the result is whole."""
        big = {f'library-data/f{i}.bin': os.urandom(4 * MiB) for i in range(12)}
        big['library-data/catalog.json'] = b'{}'
        zpath = self.tmp / 'Lastbook-Small.zip'
        self.installed = make_pack(zpath, big)
        self.zip = zpath.read_bytes()
        self.files.data['Lastbook-Small.zip'] = self.zip
        cfg = self.child_config()
        cfg['slow_unpack'] = True
        child = subprocess.Popen([sys.executable, '-B', __file__, '--child', json.dumps(cfg)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        unpacked = self.parent / 'LastbookData.setup' / 'unpack' / 'LastbookData' / 'library-data'
        try:
            t0 = time.time()
            while time.time() - t0 < 60:
                if unpacked.exists() and len(list(unpacked.glob('f*.bin'))) >= 3:
                    break
                time.sleep(0.02)
            else:
                self.fail('the child never unpacked: ' + child.stderr.read1(4000).decode())
        finally:
            child.kill()                      # SIGKILL on a Mac, TerminateProcess on Windows
            child.wait()
        s = self.setup(manifest=self.manifest())
        self.assertEqual(s.public_job()['state'], 'paused')
        s.resume()
        self.assertEqual(self.wait(s)['state'], 'done')
        lib, _ = api.startup(self.settings)
        for name, data in big.items():
            self.assertEqual(sha((lib / name).read_bytes()), sha(data), name)
        self.assertEqual(list(lib.rglob('*.partial')), [])

    def child_config(self):
        return {'settings': str(self.settings), 'parent': str(self.parent), 'home': str(self.home), 'manifest': self.manifest().current,
                'cert': str(self.tmp_class / 'cert.pem')}


class Switching(Base):
    def lib(self, where, marker):
        (where / 'library-data').mkdir(parents=True)
        (where / 'library-data' / 'catalog.json').write_text(marker)
        return where

    def test_upgrade_keeps_old_and_carries_the_model(self):
        cur = self.lib(self.parent / 'LastbookData', 'old')
        (cur / 'models').mkdir()
        (cur / 'models' / 'model.gguf').write_bytes(self.model)
        s = self.setup('manage', current=cur)
        self.assertEqual(s.current_info()['model'], 'gemma')
        s.start('small', True)          # the model is here already: only the pack is fetched
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertEqual([i['kind'] for i in j['items']], ['pack'])
        self.assertEqual((cur / 'library-data' / 'catalog.json').read_text(), 'old')   # untouched until the restart
        lib, note = api.startup(self.settings)
        self.assertEqual((lib / 'library-data' / 'catalog.json').read_text(), '{"records": []}')
        self.assertTrue((lib / 'models' / 'model.gguf').is_file())
        old = Path(note['old'])
        self.assertTrue(old.name.startswith('LastbookData.old-'))
        self.assertEqual((old / 'library-data' / 'catalog.json').read_text(), 'old')
        api.opened(self.settings, lib, note)
        s2 = self.setup('manage', current=lib)
        self.assertEqual(s2.current_info()['old'], [str(old)])
        self.assertEqual(s2.delete_old('/etc')['code'], 'unknown')
        s2.delete_old(str(old))
        time.sleep(0.5)
        self.assertFalse(old.exists())

    def test_new_library_that_does_not_open_is_rolled_back(self):
        cur = self.lib(self.parent / 'LastbookData', 'old')
        new = self.lib(self.parent / 'LastbookData.setup' / 'unpack' / 'LastbookData', 'new')
        install.stage_switch(self.parent / 'LastbookData.setup', new, cur)
        self.settings.mkdir(parents=True)
        (self.settings / 'setup.json').write_text(json.dumps({'work': str(self.parent / 'LastbookData.setup')}))
        real = install.is_library
        calls = []

        def flaky(folder):      # the new one goes missing after the rename: it "does not open"
            calls.append(folder)
            if Path(folder) == cur and len(calls) > 2:
                return False
            return real(folder)
        with mock.patch.object(install, 'is_library', flaky):
            lib, note = api.startup(self.settings)
        self.assertEqual((cur / 'library-data' / 'catalog.json').read_text(), 'old')
        self.assertIn('error', note)

    def test_failed_switch_leaves_library(self):
        cur = self.lib(self.parent / 'LastbookData', 'old')
        incomplete = self.parent / 'LastbookData.setup' / 'unpack' / 'LastbookData'
        incomplete.mkdir(parents=True)
        with self.assertRaises(install.Refused):
            install.switch(incomplete, cur)
        self.assertEqual((cur / 'library-data' / 'catalog.json').read_text(), 'old')
        self.assertEqual(sorted(p.name for p in self.parent.iterdir()), ['LastbookData', 'LastbookData.setup'])

    def test_ai_only_in_manage_mode(self):
        cur = self.lib(self.parent / 'LastbookData', '{}')
        (cur / 'pack.json').write_text('{"name": "small"}')
        s = self.setup('manage', current=cur)
        j = s.start('small', True)      # the same library: only the AI
        self.assertEqual([i['kind'] for i in j['items']], ['model'])
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertEqual(self.marked, [str(cur / 'models' / 'model.gguf')])
        self.assertEqual(s.start('small', True)['code'], 'nothing')


class Manage(Base):
    """Repair, removing the AI, and the folder picker's answer."""

    def installed_library(self):
        """A library as setup installs it: the test pack unpacked, with a pack-manifest.tsv of its files, and the model."""
        files = {'library-data/catalog.json': b'{"records": []}', 'pack.json': b'{"name": "small"}', 'library-data/big.bin': os.urandom(MiB)}
        rows = ['path\tbytes\tsha256\thow\tchanges'] + [f'{k}\t{len(v)}\t{sha(v)}\tclone\t' for k, v in files.items()]
        files['pack-manifest.tsv'] = ('\n'.join(rows) + '\n').encode()
        zpath = self.tmp / 'Lastbook-Small.zip'
        self.installed = make_pack(zpath, files)
        self.zip = zpath.read_bytes()
        self.files.data['Lastbook-Small.zip'] = self.zip
        lib = install.unpack(zpath, self.parent, self.installed, Control(), lambda d, t: None)
        (lib / 'models').mkdir()
        (lib / 'models' / 'model.gguf').write_bytes(self.model)
        zpath.unlink()
        return lib

    def test_repair_all_well_fetches_nothing(self):
        lib = self.installed_library()
        s = self.setup('manage', current=lib)
        j = s.start(repair=True)
        self.assertEqual([i['kind'] for i in j['items']], ['pack', 'model'])
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertEqual(self.files.log, [])
        self.assertFalse((self.parent / 'LastbookData.setup' / install.PENDING).exists())
        self.assertTrue((lib / 'models' / 'model.gguf').is_file())

    def test_repair_damaged_file_and_model(self):
        lib = self.installed_library()
        big = lib / 'library-data' / 'big.bin'
        big.write_bytes(b'\0' + big.read_bytes()[1:])
        (lib / 'models' / 'model.gguf').write_bytes(b'\0' + self.model[1:])
        s = self.setup('manage', current=lib)
        s.start(repair=True)
        j = self.wait(s)
        self.assertEqual(j['state'], 'done', j)
        self.assertEqual(sorted(n for n, _, _ in self.files.log), ['Lastbook-Small.zip', 'model.gguf'])
        new, note = api.startup(self.settings)
        self.assertEqual(sha((new / 'models' / 'model.gguf').read_bytes()), sha(self.model))
        self.assertEqual(s._check_library({'state': '', 'bytes_done': 0}, new, Control()), [])
        self.assertTrue(Path(note['old']).exists())        # the damaged copy is kept aside until deleted

    def test_repair_needs_a_known_pack(self):
        lib = self.parent / 'LastbookData'
        (lib / 'library-data').mkdir(parents=True)
        (lib / 'library-data' / 'catalog.json').write_text('{}')
        self.assertEqual(self.setup('manage', current=lib).start(repair=True)['code'], 'unavailable')
        self.assertEqual(self.setup().start(repair=True)['code'], 'nothing')

    def test_remove_ai(self):
        lib = self.installed_library()
        s = self.setup('manage', current=lib)
        self.assertEqual(s.remove_ai()['freed_bytes'], len(self.model))
        self.assertFalse((lib / 'models' / 'model.gguf').exists())
        self.assertTrue((lib / 'library-data' / 'catalog.json').exists())
        self.assertEqual(s.remove_ai()['code'], 'nothing')
        self.assertEqual(self.setup().remove_ai()['code'], 'nothing')

    def test_pick_answer(self):
        s = self.setup(pick_folder=lambda: str(self.tmp))
        r = s.pick()
        self.assertEqual(r['path'], str(self.tmp))
        self.assertGreater(r['free_bytes'], 0)
        if sys.platform == 'darwin':
            self.assertTrue(r['disk'])
        self.assertEqual(self.setup(pick_folder=lambda: None).pick(), {'path': None, 'cancelled': True})
        self.assertTrue(all('name' in d for d in hardware.detect()['disks']))


class Recommend(Base):
    def hw(self, ram, free, gpus=(), unified=True):
        return {'ram_bytes': ram, 'gpus': list(gpus), 'unified_memory': unified, 'disks': [{'path': str(self.parent), 'free_bytes': free, 'total_bytes': 10 ** 12}],
                'ai': hardware.estimate_ai(ram, list(gpus), unified, 19_027_384_256)}

    def test_estimates(self):
        self.assertFalse(hardware.estimate_ai(16 * 2 ** 30, [], True, 19_027_384_256)['fits'])
        self.assertTrue(hardware.estimate_ai(24 * 2 ** 30, [], True, 19_027_384_256)['fits'])        # no blanket 32 GB floor
        self.assertFalse(hardware.estimate_ai(16 * 2 ** 30, [], False, 19_027_384_256)['fits'])
        self.assertTrue(hardware.estimate_ai(16 * 2 ** 30, [{'name': 'RTX', 'vram_bytes': 12 * 2 ** 30}], False, 19_027_384_256)['fits'])
        self.assertTrue(hardware.estimate_ai(32 * 2 ** 30, [], True, 19_027_384_256)['estimate'])

    def test_pack_and_ai_by_space(self):
        s = self.setup()
        with mock.patch.object(hardware, 'disk_of', lambda p: (10 ** 12, 2 * 10 ** 12)):
            r = s.recommend(self.hw(64 * 2 ** 30, 10 ** 12))
        self.assertEqual((r['pack'], r['ai']), ('small', True))
        with mock.patch.object(hardware, 'disk_of', lambda p: (10 ** 8, 10 ** 11)):
            r = s.recommend(self.hw(64 * 2 ** 30, 10 ** 8))
        self.assertIsNone(r['pack'])
        self.assertIn('free', r['why'])
        with mock.patch.object(hardware, 'disk_of', lambda p: (10 ** 12, 2 * 10 ** 12)):
            r = s.recommend(self.hw(8 * 2 ** 30, 10 ** 12))
        self.assertEqual((r['pack'], r['ai']), ('small', False))

    def test_home_disk_first(self):
        """Fresh-user test, 12 Nov: an 8 TB home disk with 137 GB free and an external drive with 605 GB. The library stays on the home disk."""
        m = self.manifest().current
        medium = {**m['packs'][0], 'id': 'medium', 'title': 'Medium', 'installed_bytes': 67 * 10 ** 9, 'download_bytes': 67 * 10 ** 9,
                  'files': [{**m['packs'][0]['files'][0], 'name': 'Lastbook-Medium.zip', 'size': 67 * 10 ** 9}]}
        small = {**m['packs'][0], 'installed_bytes': 8 * 10 ** 9, 'download_bytes': 8 * 10 ** 9,
                 'files': [{**m['packs'][0]['files'][0], 'size': 8 * 10 ** 9}]}
        s = self.setup(manifest=manifest.Manifest(bundled={**m, 'packs': [small, medium]}, remote=None))
        ext = {'path': '/Volumes/Ext', 'name': 'Ext', 'free_bytes': 605 * 10 ** 9, 'total_bytes': 10 ** 12}
        hw = {**self.hw(512 * 2 ** 30, 137 * 10 ** 9), 'disks': [{'path': str(self.home), 'free_bytes': 137 * 10 ** 9, 'total_bytes': 8 * 10 ** 12}, ext]}
        same = lambda a, b: not str(a).startswith('/Volumes/')
        with mock.patch.object(hardware, 'disk_of', lambda p: (137 * 10 ** 9, 8 * 10 ** 12)), mock.patch.object(api, '_same_disk', same):
            r = s.recommend(hw)
            self.assertEqual((r['pack'], r['folder']), ('small', str(self.parent)))
            self.assertTrue(r['ai'])
            self.assertIn('Medium would need', r['why'])
            self.assertIn('Ext', r['why'])                    # where Medium would fit, if they choose it
        with mock.patch.object(hardware, 'disk_of', lambda p: (10 * 10 ** 9, 8 * 10 ** 12)), mock.patch.object(api, '_same_disk', same):
            r = s.recommend({**hw, 'disks': [{'path': str(self.home), 'free_bytes': 10 ** 10, 'total_bytes': 8 * 10 ** 12}, ext]})
            self.assertEqual((r['pack'], r['folder']), ('medium', '/Volumes/Ext'))
            self.assertIn('Keep that disk connected', r['why'])

    def test_hardware_here(self):
        hw = hardware.detect()
        self.assertIn(hw['os'], ('macos', 'windows'))
        self.assertGreater(hw['ram_bytes'], 2 ** 30)
        self.assertTrue(hw['disks'] and hw['disks'][0]['free_bytes'] > 0)


class Through(Base):
    """/api/setup/* over the app's bridge, as the window asks: no socket."""

    def test_bridge(self):
        import bridge as B
        s = self.setup()
        with mock.patch.object(api, 'SETUP', s):
            b = B.Bridge(api.SetupServer, 'buffer', B.ORIGIN_WINDOWS, tmpdir=str(self.tmp))
            got = []
            done = threading.Event()

            def ask(method, path, headers=None, body=None):
                got.clear(); done.clear()
                b.fetch(method, B.ORIGIN_WINDOWS + path, headers or {}, body, lambda r: (got.append(r), done.set()))
                done.wait(20)
                return got[0]
            r = ask('GET', '/api/setup/state')
            self.assertEqual(r.status, 200)
            self.assertEqual(json.loads(r.body)['mode'], 'first-run')
            r = ask('POST', '/api/setup/start', {'Content-Type': 'application/json'}, b'{"pack":"small"}')
            self.assertEqual(r.status, 403)       # no launch key
            r = ask('POST', '/api/setup/pause', {'Content-Type': 'application/json', 'X-Lastbook-Key': b.key}, b'{}')
            self.assertEqual(r.status, 200)
            r = ask('GET', '/')
            self.assertEqual(r.status, 200)
            self.assertTrue(b.top_url_ok(B.ORIGIN_WINDOWS + '/ui/setup.html'))
            r = ask('GET', '/documents/x.pdf')
            self.assertEqual(r.status, 404)


@unittest.skipUnless(os.environ.get('LASTBOOK_FULL_DISK') == '1' and sys.platform == 'darwin', 'LASTBOOK_FULL_DISK=1 on a Mac')
class FullDisk(Base):
    def test_disk_fills_during_download(self):
        img = self.tmp / 'small.dmg'
        subprocess.run(['hdiutil', 'create', '-size', '3m', '-fs', 'HFS+', '-volname', 'LBFULL', str(img)], check=True, capture_output=True)
        out = subprocess.run(['hdiutil', 'attach', '-nobrowse', '-mountrandom', str(self.tmp), str(img)], check=True, capture_output=True, text=True).stdout
        mount = Path(out.strip().split('\t')[-1])
        try:
            s = self.setup()
            r = s.start('small', True, str(mount))
            self.assertEqual(r['code'], 'no_space')            # refused before starting, with the numbers
            self.assertLess(r['free_bytes'], r['need_bytes'])
            d = download.Download(f'{self.base}/Lastbook-Small.zip', mount / 'x.zip', len(self.zip), sha(self.zip), download.Control(),
                                  allowed=ALLOWED, context=self.ctx)
            with self.assertRaises(download.Failed) as e:
                d.run()                                       # the space check skipped: the disk really fills
            self.assertEqual(e.exception.code, 'no_space')
        finally:
            subprocess.run(['hdiutil', 'detach', str(mount), '-force'], capture_output=True)


def child(cfg):
    """For the restart tests: run a job until killed."""
    cfg = json.loads(cfg)
    ctx = ssl.create_default_context(cafile=cfg['cert'])
    m = manifest.Manifest(bundled=cfg['manifest'], remote=None, allowed=ALLOWED, context=ctx)
    if cfg.get('slow_unpack'):
        real = install.unpack

        def slow(*a, **k):
            prog = a[4]
            return real(*a[:4], lambda d, t: (time.sleep(0.002), prog(d, t)))
        install.unpack = slow
    s = api.Setup('first-run', cfg['settings'], cfg['parent'], manifest=m, allowed=ALLOWED, context=ctx, home=cfg['home'], llm_local=False)
    print(s.start('small', False), flush=True)
    time.sleep(600)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--child':
        child(sys.argv[2])
    else:
        unittest.main()
