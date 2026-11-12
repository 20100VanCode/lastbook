"""One planted canary page, shown in the real Lastbook.exe window through its normal reader route. Test code, never packaged.
Library content must run no scripts. The page tries every usual way; each one, if it runs, leaves a mark in its own DOM and asks for /pages/pkg/ran-NAME.png.
  python -I -B -X utf8 win_canary.py install | run RUN | remove
Records raw values into logs/RUN/canary.json. The exe has to be up already with its debug port on 8941 (win_exe.ps1 -Cdp)."""
import base64
import glob
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cdp  # noqa: E402

BUILD = Path(r'C:\Users\you\app-test\app-build')
LIB = Path(glob.glob(r'C:\Users\you\app-test\app-only-proof\data\L*')[0]) / 'library-data'
PAGES = LIB / 'pages' / 'pkg'
CATALOG = LIB / 'catalog.json'
BACKUP = BUILD / 'verify' / 'catalog.pkg.json'
ID = 'pkg-canary'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAEBgIApD5fRAAAAABJRU5ErkJggg==')


def mark(name, q='"'):
    return f"document.documentElement.setAttribute({q}data-ran-{name}{q},{q}1{q});new Image().src={q}/pages/pkg/ran-{name}.png{q}"


def files():
    a = "'"
    return {
        'x.js': mark('external') + ';',
        'mod.js': mark('module') + ';',
        'pic.svg': f'<svg xmlns="http://www.w3.org/2000/svg"><script>{mark("svg-file")}</script></svg>',
        'inner.html': f'<!doctype html><title>inner</title><p>inner frame arrived</p><script>{mark("nested-frame")}</script>',
        'canary.html': f'''<!doctype html><html><head><meta charset="utf-8"><title>canary</title>
<meta http-equiv="refresh" content="2;url=javascript:{mark("meta-refresh", a)}">
<script>{mark("inline")}</script>
<script>eval({json.dumps(mark("eval"))})</script>
<script src="/pages/pkg/x.js"></script>
<script type="module" src="/pages/pkg/mod.js"></script>
<style>body{{font:18px sans-serif}}</style></head>
<body onload='{mark("body-onload")}'>
<h1>CANARY-VISIBLE</h1><noscript><p>NOSCRIPT-VISIBLE: this line shows only when scripts are off</p></noscript>
<p><img id="good" src="/pages/pkg/loaded.png" width="40" height="40" alt="local image"> local image above</p>
<img src="/pages/pkg/missing.png" onerror='{mark("img-onerror")}'>
<svg width="10" height="10" onload='{mark("svg-onload")}'><script>{mark("svg-inline")}</script><animate attributeName="x" dur="1s" onbegin='{mark("svg-animate")}'/></svg>
<details open ontoggle='{mark("details-toggle")}'><summary>details</summary>open</details>
<input autofocus onfocus='{mark("autofocus")}'>
<video src="/pages/pkg/missing.mp4" onerror='{mark("video-onerror")}'></video>
<marquee onstart='{mark("marquee")}' width="50">m</marquee>
<iframe id="js" src="javascript:{mark("js-frame", a)}"></iframe>
<iframe id="sd" srcdoc="<script>{mark("srcdoc", a)}</script>"></iframe>
<iframe id="inner" src="/pages/pkg/inner.html"></iframe>
<iframe id="data" src="data:text/html,<script>new Image().src='https://lastbook.invalid/pages/pkg/ran-data-frame.png'</script>"></iframe>
<object data="/pages/pkg/pic.svg" type="image/svg+xml"></object>
<embed src="/pages/pkg/pic.svg" type="image/svg+xml">
<img src="https://example.invalid/pkg-outside-img"><link rel="stylesheet" href="https://example.invalid/pkg-outside-css">
<p>END-OF-PAGE</p></body></html>''',
    }


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def install():
    PAGES.mkdir(exist_ok=True)
    for name, text in files().items():
        (PAGES / name).write_text(text, encoding='utf-8')
    (PAGES / 'loaded.png').write_bytes(PNG)
    BACKUP.write_bytes(CATALOG.read_bytes())
    c = json.loads(CATALOG.read_text(encoding='utf-8'))
    c.append({'id': ID, 'kind': 'html', 'title': ID, 'path': 'pages/pkg/canary.html', 'publisher': 'pkg', 'collection': 'pkg', 'category': 'pkg', 'bytes': 1, 'sha256': '', 'source_url': '', 'final_url': ''})
    CATALOG.write_text(json.dumps(c), encoding='utf-8')
    print('installed; catalog before', sha(BACKUP)[:16], 'now', sha(CATALOG)[:16])


def remove():
    CATALOG.write_bytes(BACKUP.read_bytes())
    for name in list(files()) + ['loaded.png']:
        (PAGES / name).unlink(missing_ok=True)
    PAGES.rmdir()
    BACKUP.unlink()
    print('removed; catalog', sha(CATALOG)[:16], 'folder left', PAGES.exists())


class Client(cdp.CDP):
    def sess(self, method, params=None, session=None, seconds=30):
        self.n += 1
        msg = {'id': self.n, 'method': method, 'params': params or {}}
        if session:
            msg['sessionId'] = session
        raw = json.dumps(msg).encode()
        mask = os.urandom(4)
        n = len(raw)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536 else bytes([0x80 | 127]) + struct.pack('>Q', n))
        self.s.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(raw)))
        return self.wait(self.n, seconds)


def walk(node, out):
    out.append(node)
    for key in ('children', 'pseudoElements', 'shadowRoots'):
        for k in node.get(key) or []:
            walk(k, out)
    if node.get('contentDocument'):
        walk(node['contentDocument'], out)


def run(name):
    out_dir = BUILD / 'logs' / name
    (out_dir / 'shots').mkdir(parents=True, exist_ok=True)
    end = time.time() + 45
    page = None
    while time.time() < end and not page:
        try:
            page = next((t for t in cdp.targets(8941) if t['type'] == 'page' and t['url'].startswith('https://lastbook.invalid')), None)
        except OSError:
            pass
        time.sleep(0.3)
    if not page:
        print('no page target')
        return 1
    c = Client(8941, page['webSocketDebuggerUrl'])
    sessions = {}      # sessionId -> target info
    seen = []          # every event, tagged by phase
    bypass = [False]

    def setup(session):
        for m in ('Network.enable', 'Log.enable', 'Runtime.enable', 'Page.enable', 'DOM.enable'):
            c.sess(m, None, session)
        if bypass[0]:
            c.sess('Page.setBypassCSP', {'enabled': True}, session)
        if session:
            c.sess('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': True, 'flatten': True}, session)
            c.sess('Runtime.runIfWaitingForDebugger', None, session)

    def drain(seconds, phase):
        stop = time.time() + seconds
        while time.time() < stop:
            c.pump(0.2)
            while c.events:
                e = c.events.pop(0)
                e['phase'] = phase
                seen.append(e)
                if e['method'] == 'Target.attachedToTarget':
                    sessions[e['params']['sessionId']] = e['params']['targetInfo']
                    setup(e['params']['sessionId'])

    def dom_dump():
        res = {}
        for s in [None] + list(sessions):
            m = c.sess('DOM.getDocument', {'depth': -1, 'pierce': True}, s)
            nodes = []
            if 'result' in m:
                walk(m['result']['root'], nodes)
            res[s or 'top'] = nodes
        return res

    def marks(dump):
        found, texts, urls = set(), set(), set()
        for nodes in dump.values():
            for n in nodes:
                attrs = n.get('attributes') or []
                for k in attrs[0::2]:
                    if k.startswith('data-ran-'):
                        found.add(k)
                v = n.get('nodeValue') or ''
                for word in ('CANARY-VISIBLE', 'NOSCRIPT-VISIBLE', 'END-OF-PAGE', 'inner frame arrived'):
                    if word in v:
                        texts.add(word)
                if n.get('documentURL'):
                    urls.add(n['documentURL'][:120])
        return sorted(found), sorted(texts), sorted(urls)

    def ran_requests(phase):
        return sorted({e['params']['request']['url'].rsplit('/', 1)[-1] for e in seen if e['phase'] == phase and e['method'] == 'Network.requestWillBeSent' and '/ran-' in e['params']['request']['url']})

    def summary(phase):
        reqs = [e['params']['request']['url'][:110] for e in seen if e['phase'] == phase and e['method'] == 'Network.requestWillBeSent']
        logs = [(e['params']['entry'].get('source'), e['params']['entry']['text'][:230]) for e in seen if e['phase'] == phase and e['method'] == 'Log.entryAdded']
        cons = [(e['params'].get('type'), str(e['params'].get('args'))[:160]) for e in seen if e['phase'] == phase and e['method'] == 'Runtime.consoleAPICalled']
        return {'requests': reqs, 'ran_requests': ran_requests(phase), 'log_entries': logs, 'console': cons}

    report = {'exe_target': page['url'], 'ua': None}
    setup(None)
    c.sess('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': True, 'flatten': True})
    t = time.time()
    while time.time() - t < 30 and not c.eval("!!document.querySelector('#main h1')"):
        time.sleep(0.2)
    report['ua'] = c.eval('navigator.userAgent')
    report['first_h1_secs'] = round(time.time() - t, 2)
    drain(0.5, 'boot')

    # The detector's first control: from the top frame, which does run scripts, the same kind of request has to show up.
    c.eval("new Image().src='/pages/pkg/ran-top-control.png';0")
    drain(1, 'top-control')
    report['top_control'] = {'ran_requests': ran_requests('top-control')}

    # What the app really serves for the page: scripts still in the text, and the policy on the answer.
    report['served'] = c.eval("fetch('/pages/pkg/canary.html').then(async r=>{const t=await r.text();return {status:r.status,csp:r.headers.get('content-security-policy'),has_script_tags:(t.match(/<script/g)||[]).length,has_onload:t.includes('onload='),bytes:t.length}}).catch(e=>String(e))")

    # The test itself, through the reader's normal route.
    c.eval(f"location.hash='#/read/{ID}?view=web';0")
    drain(8, 'canary')
    report['canary'] = summary('canary')
    report['frame'] = c.eval("(()=>{const f=document.querySelector('iframe.frame');return f?{src:f.src,sandboxAttr:f.getAttribute('sandbox')}:null})()")
    report['top_href'] = c.eval('location.href')
    responses = [{'url': e['params']['response']['url'][:100], 'status': e['params']['response']['status'], 'csp': next((v for k, v in e['params']['response'].get('headers', {}).items() if k.lower() == 'content-security-policy'), None)}
                 for e in seen if e['phase'] == 'canary' and e['method'] == 'Network.responseReceived' and '/pages/pkg/' in e['params']['response']['url']]
    report['canary']['responses'] = responses
    report['targets'] = [[x['type'], x['url'][:100]] for x in cdp.targets(8941)]
    report['sessions'] = [[v['type'], v['url'][:100]] for v in sessions.values()]
    dump = dom_dump()
    found, texts, urls = marks(dump)
    report['canary'].update(dom_marks=found, dom_texts=texts, dom_documents=urls)
    report['canary']['good_image'] = [{k: n.get('attributes')} for nodes in dump.values() for n in nodes for k in [n.get('nodeName')] if k == 'IMG' and 'good' in (n.get('attributes') or [])][:1]
    (out_dir / 'shots' / 'canary.png').write_bytes(base64.b64decode(c.call('Page.captureScreenshot', {'format': 'png'})['data']))

    # The detector's second control: a mark put into the frame's own DOM from outside has to be read back.
    wrote = None
    for s, nodes in dump.items():
        body = next((n for n in nodes if n.get('nodeName') == 'H1' and any('CANARY-VISIBLE' in (k.get('nodeValue') or '') for k in n.get('children') or [])), None)
        if body:
            m = c.sess('DOM.setAttributeValue', {'nodeId': body['nodeId'], 'name': 'data-ran-detector-control', 'value': '1'}, None if s == 'top' else s)
            wrote = 'error' not in m
            break
    report['dom_control'] = {'wrote': wrote, 'read_back': 'data-ran-detector-control' in marks(dom_dump())[0]}

    # The third control: the same page with the page's policy bypassed by DevTools. Marks here show the canary's scripts are real ones and the detector sees them.
    bypass[0] = True
    for s in [None] + list(sessions):
        c.sess('Page.setBypassCSP', {'enabled': True}, s)
    c.eval("(()=>{const f=document.querySelector('iframe.frame');f.src=f.src+'?c=1';return 0})()")
    drain(7, 'bypass')
    report['bypass_control'] = summary('bypass')
    report['bypass_control']['dom_marks'] = marks(dom_dump())[0]

    c.eval("location.hash='#/';0")
    drain(1, 'end')
    report['end_href'] = c.eval('location.href')
    report['end_targets'] = [[x['type'], x['url'][:100]] for x in cdp.targets(8941)]
    (out_dir / 'canary.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    what = sys.argv[1]
    sys.exit(install() if what == 'install' else remove() if what == 'remove' else run(sys.argv[2]))
