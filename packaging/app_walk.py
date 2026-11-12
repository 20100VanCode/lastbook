"""Walks the real packaged Lastbook.app over one pack, the way a person would, window off screen. Records raw values; judged by reading them.
app_walk.py PACK DATA_FOLDER [--only a,b,c]
PACK names the output folder under derived/packs/app-walk/. DATA_FOLDER is a scratch clone of the pack, because the app writes to its data folder.
No model: SURVIVAL_MODEL_BASE points at port 1, where nothing listens, so the real DeepSeek is never called.
Test only, never packaged."""
import csv, json, random, re, subprocess, sys, threading, time, traceback, urllib.parse
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path('/path/to/lastbook')
sys.path.insert(0, str(ROOT / 'derived/app-build/verify-mac/fin'))
import finlib
from finlib import region

args = sys.argv[1:]
PACK, DATA = args[0], Path(args[1])
BASE = re.sub(r'-\d+$', '', PACK)   # small-2 is a second run over small
only = args[args.index('--only') + 1].split(',') if '--only' in args else None
LAST = ROOT / 'derived/app-build/verify-mac/last'
finlib.APP = str(ROOT / 'derived/app-build/mac/20261101-193435/dist/Lastbook.app')
finlib.EXE = finlib.APP + '/Contents/MacOS/Lastbook'
finlib.DYLIB = LAST / 'lbtest.dylib'
finlib.DATA = DATA
PACKS = ROOT / 'derived/packs'
OUT = PACKS / 'app-walk' / PACK
OUT.mkdir(parents=True, exist_ok=True)
contents = list(csv.DictReader(open(DATA / 'pack-contents.tsv', newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
broken_rows = [r for r in contents if r.get('path') is None]   # a line break in a title splits a row of the contents list
contents = [r for r in contents if r.get('path') is not None and r.get('kind') in ('pdf', 'html', 'pptx', 'video', 'transcript', 'zim', 'docx', 'txt', 'epub') or (r.get('path') is not None)]
for r in contents:
    r['publisher'] = r.get('publisher') or ''
manifest = list(csv.DictReader(open(DATA / 'pack-manifest.tsv', newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
ids = {r['id'] for r in contents}
random.seed(20261102)

# The owner's own Lastbook may be open. A separate home keeps this run's web storage away from theirs, and starts it as a fresh install.
HOME = Path('/tmp/lastbook-scratch/home') / PACK
HOME.mkdir(parents=True, exist_ok=True)
_run = subprocess.run


def run_with_home(cmd, *k, **kw):
    if cmd and cmd[0] == '/usr/bin/open':
        cmd = cmd[:1] + ['--env', f'CFFIXED_USER_HOME={HOME}'] + cmd[1:]
    return _run(cmd, *k, **kw)


subprocess.run = run_with_home
MODEL = 'http://127.0.0.1:1'  # nothing listens there: no model, and never the real one on 19443
a = finlib.App(str(OUT), model=MODEL, decoy=False)
frontmost = []


def front_watch():
    while a.alive:
        try:
            if finlib.front_pid() == a.pid:
                frontmost.append(time.time())
        except Exception:
            pass
        time.sleep(0.5)


threading.Thread(target=front_watch, daemon=True).start()
HELP_ERR = "window.__errs=window.__errs||[];if(!window.__hook){window.__hook=1;addEventListener('error',e=>window.__errs.push(String(e.message||e.target&&(e.target.src||e.target.href)||'?').slice(0,160)),true);addEventListener('unhandledrejection',e=>window.__errs.push('rej:'+String(e.reason).slice(0,160)))}"
SNAP = r"""await until(()=>!document.querySelector('#main .loading'),9000);await sleep(%d);
const m=document.getElementById('main');const T=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
return {hash:location.hash,title:document.title,h1:T(document.querySelector('#main h1')||{}),len:m.innerText.length,err:[...m.querySelectorAll('.err,.ans-error')].map(e=>T(e).slice(0,200)),empty:[...m.querySelectorAll('.empty')].map(e=>T(e).slice(0,120)),
imgs:[...m.querySelectorAll('img')].map(i=>i.currentSrc||i.src),broken:[...m.querySelectorAll('img')].filter(i=>i.complete&&!i.naturalWidth).map(i=>(i.currentSrc||i.src).slice(-70)),
links:[...m.querySelectorAll('a[href]')].map(x=>[x.getAttribute('href'),T(x).slice(0,70)]),frames:[...m.querySelectorAll('iframe')].map(f=>f.getAttribute('src')),text:T(m).slice(0,400),errs:(window.__errs||[]).splice(0)}"""


def snap(wait=150):
    return a.js(SNAP % wait, timeout=40) or {}


def strip_from(h):
    u = urllib.parse.urlsplit(h)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if k != 'from']
    return u.path + (u.fragment and '#' + u.fragment or '') + ('?' + urllib.parse.urlencode(q) if q else '')


def norm(h):
    h = h.split('#', 1)[1] if h.startswith('#') else h
    p, _, q = h.partition('?')
    q2 = [(k, v) for k, v in urllib.parse.parse_qsl(q) if k != 'from']
    return '#' + p + ('?' + urllib.parse.urlencode(q2) if q2 else '')


results = {}


def rec(k, v):
    results[k] = v
    a.rec(k, v)
    (OUT / 'walk.json').write_text(json.dumps(results, indent=1, default=str))


def section(fn):
    if only and fn.__name__ not in only:
        return
    print('=== ', fn.__name__, flush=True)
    t = time.time()
    try:
        fn()
    except Exception:
        rec('EXC_' + fn.__name__, traceback.format_exc())
    rec('took_' + fn.__name__, round(time.time() - t, 1))
    st = a.cmd('state')
    rec('win_' + fn.__name__, {k: st.get(k) for k in ('frame', 'off', 'active', 'key', 'error')})
    a.js(HELP_ERR + "return 1")


# ---------------------------------------------------------------- chrome
def chrome():
    a.go('#/', None, 600)
    outside = a.js(r"return [...document.querySelectorAll('a[href]')].filter(x=>!x.closest('#main')).map(x=>[x.getAttribute('href'),(x.innerText||'').trim().slice(0,40),x.getBoundingClientRect().width>0])")
    rec('links_outside_main', outside)
    for h, text, vis in outside:
        if not vis or h == '#main':
            continue
        c = a.click("[...document.querySelectorAll('a[href]')].filter(x=>!x.closest('#main')&&x.getBoundingClientRect().width>0).find(x=>x.getAttribute('href')==%s&&(x.innerText||'').trim().slice(0,40)==%s)" % (json.dumps(h), json.dumps(text)))
        time.sleep(0.8)
        s = snap(300)
        rec('real_click_top ' + (text or h), {'clicked': bool(c.get('w')), **{k: s.get(k) for k in ('hash', 'h1', 'len', 'err', 'empty', 'broken', 'errs')}})
        a.shot('top-' + re.sub(r'\W+', '_', text or h) + '.png')
    a.go('#/', None, 800)
    a.shot('home.png')
    rec('home_text', a.js("return document.getElementById('main').innerText.slice(0,1500)"))


# ---------------------------------------------------------------- crawl
ITEM = re.compile(r'^#/(read|watch|wiki)/')
NAV = re.compile(r'^#/(t/|library|videos|shelf/|collection|encyclopedias$|prepare|learn|browse|about)|^#/$')
items, routes, nonhash = {}, {}, {}


def crawl():
    topics = a.js("const t=await (await fetch('/api/topics')).json();return (Array.isArray(t)?t:t.topics).map(x=>x.id)")
    rec('topic_ids', topics)
    shelves = a.js("return await (await fetch('/api/shelves')).json()")
    rec('shelves_api', shelves)
    todo = ['#/', '#/library', '#/videos', '#/videos/all', '#/encyclopedias', '#/prepare', '#/about', '#/learn', '#/browse'] + [f'#/t/{i}' for i in topics] + [f"#/shelf/{s['id']}" for s in shelves]
    seen = set()
    while todo:
        h = todo.pop(0)
        if h in seen or len(seen) > 4000:
            continue
        seen.add(h)
        a.go(h, None, 100)
        s = snap()
        links = s.pop('links', [])
        s.pop('text', None)
        imgs = s.pop('imgs', [])
        s['nlinks'] = len(links)
        routes[h] = s
        for i in imgs:
            nonhash.setdefault('IMG ' + i, h)
        for l, text in links:
            if l.startswith('#/'):
                n = norm(l)
                if ITEM.match(n):
                    items.setdefault(n, {'text': text, 'from': h})
                elif NAV.match(n) and n not in seen:
                    if not re.search(r'[?&]q=', n):
                        todo.append(n)
                elif n.startswith('#/ask') or n.startswith('#/map') or n.startswith('#/saved') or n.startswith('#/search'):
                    pass
                else:
                    nonhash.setdefault('ODD ' + l, h)
            elif not l.startswith('#'):
                nonhash.setdefault(l, h)
    (OUT / 'routes.json').write_text(json.dumps(routes, indent=0, default=str))
    (OUT / 'items.json').write_text(json.dumps(items, indent=0))
    rec('crawl_counts', {'routes': len(routes), 'items': len(items), 'other_links': len(nonhash)})
    rec('routes_with_error', {k: {x: v.get(x) for x in ('h1', 'err', 'errs', 'broken')} for k, v in routes.items() if v.get('err') or v.get('errs') or v.get('broken')})
    rec('routes_empty_state', {k: v.get('empty') for k, v in routes.items() if v.get('empty')})
    rec('routes_not_found', [k for k, v in routes.items() if 'isn’t here' in (v.get('h1') or '')])
    rec('routes_thin', {k: v.get('len') for k, v in routes.items() if (v.get('len') or 0) < 120})
    # every picture and non-hash link the crawl saw, fetched by the app
    other = list(nonhash)
    urls = [x[4:] if x.startswith('IMG ') else x for x in other if not x.startswith('ODD ')]
    rep = {'n': len(urls), 'bad': []}
    for i in range(0, len(urls), 40):
        r = a.js("const out=[];for(const u of %s){try{const c=new AbortController();const q=await fetch(u,{signal:c.signal});out.push([u,q.status]);c.abort()}catch(e){out.push([u,String(e).slice(0,60)])}}return out" % json.dumps(urls[i:i + 40]), timeout=120)
        rep['bad'] += [x for x in (r if isinstance(r, list) else []) if x[1] not in (200, 206)]
    rep['bad_where'] = {b[0]: nonhash.get(b[0]) or nonhash.get('IMG ' + b[0]) for b in rep['bad']}
    rec('pictures_and_plain_links_fetched', rep)
    rec('odd_links', {k[4:]: v for k, v in nonhash.items() if k.startswith('ODD ')})


# ---------------------------------------------------------------- items
ITEM_JS = r"""const T=e=>(e&&e.innerText||'').replace(/\s+/g,' ').trim();
await until(()=>!document.querySelector('#main .loading')&&(document.querySelector('.rtitle,.vtitle,#wframe,#main h1')),9000);await sleep(120);
const m=document.getElementById('main');const o={hash:location.hash.replace(/&?from=[^&]*/,'').slice(0,90),h1:T(document.querySelector('#main h1')).slice(0,90),src:T(document.querySelector('.rsrc,.vmeta')).slice(0,90),err:[...m.querySelectorAll('.err,.ans-error')].map(e=>T(e).slice(0,160))};
const n=[...m.querySelectorAll('.notice')].map(T).filter(x=>/couldn|could not|can.t/i.test(x)).map(x=>x.slice(0,120));if(n.length)o.notice=n;
const img=document.querySelector('img.pageimg');if(img){const i=await until(()=>img.complete,15000);o.pageimg=img.naturalWidth}
const v=document.querySelector('#vid');if(v){await until(()=>v.readyState>=1||v.error,7000);o.video={rs:v.readyState,err:v.error&&v.error.code,dur:Math.round(v.duration)||0}}
const w=document.querySelector('#wframe');if(w){await until(()=>w.contentDocument&&w.contentDocument.readyState==='complete'&&w.contentDocument.body&&w.contentDocument.body.innerText.length>0,8000);const d=w.contentDocument;o.wiki={wtitle:T(document.querySelector('#wtitle')).slice(0,80),frame:d&&d.title.slice(0,80),len:d&&d.body.innerText.length,start:d&&T(d.body).slice(0,80),loc:w.contentWindow.location.pathname.slice(-60)}}
const f=document.querySelector('iframe.frame');if(f)o.frame=f.getAttribute('src').slice(-90);return o"""
FRAME = "const T=(document.body&&document.body.innerText||'').replace(/\\s+/g,' ').trim();return {title:document.title.slice(0,60),len:T.length,start:T.slice(0,60),imgs:document.images.length,drawn:[...document.images].filter(i=>i.naturalWidth>0).length,undrawn:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.getAttribute('src')).slice(0,6),scriptEls:document.scripts.length,kind:document.contentType}"


def visit(h):
    a.go(h, None, 30)
    o = a.js(ITEM_JS, timeout=50) or {}
    if o.get('frame') and not o['frame'].lower().endswith('.pdf') and '.pdf#' not in o['frame'].lower():
        time.sleep(0.35)
        o['inframe'] = a.fjs(FRAME, timeout=20)
    return o


def walk_items():
    src = items or json.loads((OUT / 'items.json').read_text()) if (items or (OUT / 'items.json').exists()) else {}
    done = {}
    names = list(src)
    for i, h in enumerate(names):
        o = visit(h)
        o['from'] = src[h]['from']
        o['label'] = src[h]['text']
        done[h] = o
        if i % 50 == 0:
            print('items', i, len(names), flush=True)
            (OUT / 'item-visits.json').write_text(json.dumps(done, indent=0, default=str))
    (OUT / 'item-visits.json').write_text(json.dumps(done, indent=0, default=str))
    def bad(o):
        if o.get('err') or o.get('notice') or o.get('__error'):
            return True
        if 'pageimg' in o and not o['pageimg']:
            return True
        if o.get('video') and (o['video'].get('err') or not o['video'].get('rs')):
            return True
        if o.get('wiki') and not (o['wiki'].get('len') or 0) > 40:
            return True
        i = o.get('inframe')
        if i and (i.get('__error') or (i.get('len') or 0) < 40 and not i.get('drawn')):
            return True
        return 'isn’t here' in (o.get('h1') or '')
    b = {k: v for k, v in done.items() if bad(v)}
    (OUT / 'item-bad.json').write_text(json.dumps(b, indent=0, default=str))
    rec('item_visits', {'n': len(done), 'bad': len(b), 'bad_examples': dict(list(b.items())[:12]), 'kinds': {k: sum(1 for x in done if x.startswith('#/' + k)) for k in ('read', 'watch', 'wiki')},
                        'scripts_in_frames': sum((v.get('inframe') or {}).get('scriptEls') or 0 for v in done.values()), 'frames_measured': sum(1 for v in done.values() if v.get('inframe')), 'undrawn_images': {k: v['inframe']['undrawn'] for k, v in done.items() if (v.get('inframe') or {}).get('undrawn')}})


# ------------------------------------------------------- every record, through the app
def records():
    rows = [r for r in contents if r['kind'] not in ('zim',)]
    fails, kinds = [], {}
    code = r"""const ok={};const bad=[];for(const [id,kind] of %s){try{const q=await fetch('/api/doc/'+encodeURIComponent(id));if(!q.ok){bad.push([id,kind,'doc',q.status]);continue}const d=await q.json();
    if(d.kind==='transcript'&&!d.path){ok[kind]=(ok[kind]||0)+1;continue}
    const u='/'+String(d.path||'').split('/').map(encodeURIComponent).join('/');const c=new AbortController();const f=await fetch(u,{signal:c.signal,headers:{Range:'bytes=0-0'}});const s=f.status;c.abort();
    if(s===200||s===206)ok[kind]=(ok[kind]||0)+1;else bad.push([id,kind,'file',s,d.path,d.remote||null])}catch(e){bad.push([id,kind,'exc',String(e).slice(0,80)])}}return {ok,bad}"""
    for i in range(0, len(rows), 60):
        r = a.js(code % json.dumps([[x['id'], x['kind']] for x in rows[i:i + 60]]), timeout=240)
        if not isinstance(r, dict) or 'ok' not in r:
            fails.append(['batch', i, str(r)[:200]])
            continue
        for k, v in r['ok'].items():
            kinds[k] = kinds.get(k, 0) + v
        fails += r['bad']
        if i % 1200 == 0:
            print('records', i, len(rows), flush=True)
    (OUT / 'record-failures.json').write_text(json.dumps(fails, indent=0))
    by = {}
    for f in fails:
        k = '%s %s %s' % (f[1], f[2], f[3]) if len(f) > 3 else 'other'
        by[k] = by.get(k, 0) + 1
    rec('records_through_app', {'records': len(rows), 'ok': kinds, 'failed': len(fails), 'failed_by': by, 'examples': fails[:8]})
    # catalog against the contents list
    cat = a.js("const s=await (await fetch('/api/library')).json();return s")
    rec('api_library', cat)
    rec('pack_json', json.loads((DATA / 'pack.json').read_text()))
    rec('contents_rows_split_by_line_breaks', [dict(r) for r in broken_rows][:8])
    # a rendered first page of PDFs: all in Small, a sample elsewhere
    pdfs = [r for r in contents if r['kind'] == 'pdf']
    sample = pdfs if len(pdfs) < 200 else random.sample(pdfs, 150)
    code = r"""const o=[];for(const id of %s){const t=performance.now();try{const q=await fetch('/api/page/'+encodeURIComponent(id)+'/1.png?w=500');const b=await q.blob();const i=await createImageBitmap(b).catch(()=>null);o.push([id,q.status,i?i.width:0,Math.round(performance.now()-t)])}catch(e){o.push([id,'exc',String(e).slice(0,50),0])}}return o"""
    res = []
    for i in range(0, len(sample), 20):
        res += a.js(code % json.dumps([x['id'] for x in sample[i:i + 20]]), timeout=300) or []
    rec('pdf_first_page_rendered', {'n': len(res), 'ok': sum(1 for x in res if x[1] == 200 and x[2]), 'bad': [x for x in res if not (x[1] == 200 and x[2])][:30], 'slowest_ms': max([x[3] for x in res] or [0])})


# ---------------------------------------------------------------- scripts in the served bytes
def served_bytes():
    rows = [m['path'][len('library-data'):] for m in manifest if m['path'].startswith('library-data/') and re.search(r'\.x?html?$', m['path'], re.I)]
    code = r"""const P={script:/<script\b/i,onattr:/<[a-z][^>]*\son[a-z]{3,}\s*=/i,iframe:/<(iframe|object|embed|applet)\b/i,linkhttp:/<link\b[^>]*https?:/i,srchttp:/\bsrc(set)?\s*=\s*["']?\s*(https?:)?\/\//i,cssurl:/url\(\s*["']?\s*(https?:)?\/\//i,imp:/@import/i,formhttp:/<form\b[^>]*action\s*=\s*["']?https?:/i,refresh:/http-equiv\s*=\s*["']?refresh/i,base:/<base\b/i,jshref:/href\s*=\s*["']?\s*javascript:/i};
    const c={};const off=[];let n=0,bad=0,bytes=0;for(const p of %s){const u=p.split('/').map(encodeURIComponent).join('/');const q=await fetch(u);if(!q.ok){bad++;off.push([p,q.status]);continue}const t=await q.text();n++;bytes+=t.length;for(const k in P)if(P[k].test(t)){c[k]=(c[k]||0)+1;if(off.length<40)off.push([p,k,(t.match(P[k])||[''])[0].slice(0,80)])}}return {n,bad,bytes,c,off}"""
    tot = {'n': 0, 'bad': 0, 'bytes': 0, 'c': {}, 'off': []}
    for i in range(0, len(rows), 50):
        r = a.js(code % json.dumps(rows[i:i + 50]), timeout=300)
        if not isinstance(r, dict) or 'n' not in r:
            tot['off'].append(['batch', i, str(r)[:200]])
            continue
        tot['n'] += r['n']; tot['bad'] += r['bad']; tot['bytes'] += r['bytes']
        for k, v in r['c'].items():
            tot['c'][k] = tot['c'].get(k, 0) + v
        if len(tot['off']) < 200:
            tot['off'] += r['off']
        if i % 2000 == 0:
            print('served', i, len(rows), flush=True)
    (OUT / 'served-bytes.json').write_text(json.dumps(tot, indent=0))
    rec('served_bytes', {**tot, 'html_in_manifest': len(rows), 'off': tot['off'][:30]})


# ---------------------------------------------------------------- stripped against the original, same window
ORIG_N = {'small': 30, 'medium': 80, 'all': 12}.get(BASE, 0)


def compare():
    stripped = [m for m in manifest if m['how'] == 'stripped' and m['path'].startswith('library-data/')]
    def weight(m):
        return sum(int(x.split('=')[1]) for x in m['changes'].split(',') if '=' in x and not x.startswith('comment'))
    heavy = sorted(stripped, key=weight, reverse=True)[:ORIG_N // 3]
    pick = heavy + random.sample(stripped, min(len(stripped), ORIG_N - len(heavy)))
    named = [m for m in stripped if re.search(r'apr215\.htm$|steps-to-build-a-successful-family-emergency-plan|ifrc-cea-toolkit-tool-15-3', m['path'])]
    pick = list({m['path']: m for m in named + pick}.values())
    lib = (ROOT / 'library-data').resolve()
    rows = []
    a.go('#/read/lastbook-sources?view=web', 'iframe.frame', 400)
    M = "const W=(document.body&&document.body.innerText||'').replace(/\\s+/g,' ').trim();return {title:document.title.slice(0,70),len:W.length,words:W.split(' ').slice(0,60000),imgs:document.images.length,drawn:[...document.images].filter(i=>i.naturalWidth>0).length,undrawn:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.getAttribute('src')||'').slice(0,12),links:document.links.length,scriptEls:document.scripts.length,fonts:[...document.fonts].filter(f=>f.status==='loaded').length,h:document.documentElement.scrollHeight,sheets:document.styleSheets.length}"
    for m in pick:
        rel = m['path'][len('library-data/'):]
        src = lib / rel
        if not src.is_file():
            rows.append({'path': rel, 'orig': 'not found in library'})
            continue
        ctl = DATA / 'library-data' / (rel + '.orig.html')
        ctl.write_bytes(src.read_bytes())      # read-only read of the library; the copy is in the scratch clone
        out = {'path': rel, 'changes': m['changes']}
        for name, u in (('pack', '/' + rel), ('orig', '/' + rel + '.orig.html')):
            enc = '/'.join(urllib.parse.quote(x) for x in u.split('/'))
            a.js("const f=document.querySelector('iframe.frame');await new Promise(r=>{f.onload=r;f.src=%s;setTimeout(r,9000)});await sleep(500);return 1" % json.dumps(enc), timeout=30)
            a.fjs("scrollTo(0,document.body.scrollHeight/2);return 1"); time.sleep(0.25)
            a.fjs("scrollTo(0,document.body.scrollHeight);return 1"); time.sleep(0.25)
            a.fjs("scrollTo(0,0);return 1"); time.sleep(0.35)
            out[name] = a.fjs(M, timeout=40)
            if name == 'pack' and 'bytes' not in out:
                t = a.js("const q=await fetch(%s);const t=await q.text();return {script:(t.match(/<script\\b/gi)||[]).length}" % json.dumps(enc))
                out['pack_served'] = t
            if name == 'orig':
                t = a.js("const q=await fetch(%s);const t=await q.text();return {script:(t.match(/<script\\b/gi)||[]).length}" % json.dumps(enc))
                out['orig_served'] = t
        if isinstance(out.get('pack'), dict) and isinstance(out.get('orig'), dict) and 'words' in out['pack'] and 'words' in out['orig']:
            from collections import Counter
            wp, wo = Counter(out['pack'].pop('words')), Counter(out['orig'].pop('words'))
            lost = wo - wp
            out['words_lost'] = sum(lost.values())
            out['words_gained'] = sum((wp - wo).values())
            out['lost_sample'] = [w for w, _ in lost.most_common(12)]
        rows.append(out)
        ctl.unlink()
    (OUT / 'stripped-vs-original.json').write_text(json.dumps(rows, indent=0, default=str))
    cmp = [r for r in rows if 'words_lost' in r]
    rec('stripped_vs_original', {'pages': len(rows), 'compared': len(cmp), 'detector_control_orig_with_scripts': sum(1 for r in cmp if (r.get('orig_served') or {}).get('script')), 'pack_served_scripts': sum((r.get('pack_served') or {}).get('script') or 0 for r in cmp),
                                 'text_lost_over_1pct': [(r['path'], r['words_lost'], r['orig']['len'], r['lost_sample']) for r in cmp if r['words_lost'] > max(3, r['orig']['len'] / 6 * 0.01)][:20],
                                 'drawn_fewer': [(r['path'], r['pack']['drawn'], r['orig']['drawn'], r['pack']['undrawn']) for r in cmp if r['pack']['drawn'] < r['orig']['drawn']][:20],
                                 'undrawn_in_pack': sum(1 for r in cmp if r['pack']['undrawn']), 'links_fewer': [(r['path'], r['pack']['links'], r['orig']['links']) for r in cmp if r['pack']['links'] < r['orig']['links']][:20],
                                 'fonts_fewer': [(r['path'], r['pack']['fonts'], r['orig']['fonts']) for r in cmp if r['pack']['fonts'] < r['orig']['fonts']][:10], 'sheets_fewer': [(r['path'], r['pack']['sheets'], r['orig']['sheets']) for r in cmp if r['pack']['sheets'] < r['orig']['sheets']][:10],
                                 'height_changed_a_lot': [(r['path'], r['pack']['h'], r['orig']['h']) for r in cmp if abs(r['pack']['h'] - r['orig']['h']) > 0.15 * max(r['orig']['h'], 1)][:20], 'uncompared': [r for r in rows if 'words_lost' not in r][:6]})


# ---------------------------------------------------------------- search
RESULTS = r"""await until(()=>{const s=document.querySelector('#sres');return s&&!s.querySelector('.loading')&&(s.innerText.length>0||document.querySelector('#svid')&&document.querySelector('#svid').innerText.length>0)},20000);await until(()=>{const z=document.querySelector('#zr');return !z||!z.querySelector('.loading')},9000);await sleep(700);const T=e=>(e.innerText||'').replace(/\s+/g,' ').trim();const g=(s)=>[...document.querySelectorAll(s)].map(x=>[x.getAttribute('href').replace(/[?&]from=.*/,''),T(x).slice(0,80)]);
return {hash:location.hash,guides:g('#main a.ghit'),passages:g('#spass a'),videos:g('#svid a.vcard'),read:g('#sres .result h3 a'),wiki:g('#szim a[href^="#/wiki"]'),empty:T(document.querySelector('#main .empty')||{}).slice(0,160),err:[...document.querySelectorAll('#main .err')].map(T),headings:[...document.querySelectorAll('#main h2,#main .sec-head')].map(T).slice(0,8),szim:T(document.querySelector('#szim')||{}).slice(0,160),also:T(document.querySelector('#sres p.small')||{}).slice(0,120)}"""


def do_search(q):
    a.go('#/search?q=' + urllib.parse.quote(q), '#sout', 50)
    return a.js(RESULTS, timeout=50)


def search():
    # Typed with real key events into the top search box, sent with a real click
    a.go('#/', '#bigQ', 400)
    c = a.click("document.querySelector('#bigQ')")
    for ch in 'boil water':
        a.cmd('keydown', uni=ord(ch), code=0, flags=0)
    time.sleep(0.2)
    typed = a.js("return document.querySelector('#bigQ').value")
    if typed != 'boil water':
        a.js("const q=document.querySelector('#bigQ');q.value='boil water';q.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    c2 = a.click("document.querySelector('#bigQF button')")
    r = a.js(RESULTS, timeout=50)
    rec('search_boil_water_real_click', {'typed_by_real_keys': typed, 'clicked': bool(c2.get('w')), **(r or {})})
    a.shot('search-boil-water.png')
    for sel, name in (("#sres .result h3 a", 'manual'), ("#svid a.vcard", 'video'), ("#szim a[href^=\"#/wiki\"]", 'encyclopedia'), ("#spass a", 'passage')):
        d = a.js("const e=document.querySelector(%s);return e?{href:e.getAttribute('href'),text:(e.querySelector('b,h3')||e).innerText.slice(0,80)}:null" % json.dumps(sel))
        if not d:
            rec('search_hit_click_' + name, 'no hit of this kind')
            continue
        c = a.click("document.querySelector(%s)" % json.dumps(sel))
        time.sleep(1.5)
        s = a.js(ITEM_JS, timeout=50)
        i = a.fjs(FRAME, timeout=20) if s and s.get('frame') and '.pdf' not in s['frame'].lower() else None
        rec('search_hit_click_' + name, {'hit': d, 'clicked': bool(c.get('w')), 'opened': s, 'inframe': i})
        a.shot('search-open-' + name + '.png')
        a.cmd('back'); time.sleep(1.2)
        rec('search_back_' + name, a.js("return {hash:location.hash,results:document.querySelectorAll('#sres .result').length}"))
    # real top bar search
    a.go('#/library', None, 200)
    a.js("document.querySelector('#topQ').value='water';return 1")
    c = a.click("document.querySelector('#topSearch button')")
    r = a.js(RESULTS, timeout=50)
    rec('search_top_bar', {'clicked': bool(c.get('w')), 'hash': (r or {}).get('hash'), 'read': len((r or {}).get('read', [])), 'videos': len((r or {}).get('videos', []))})
    # Every hit of several searches opens the right thing
    queries = ['tourniquet', 'solar panel', 'water filter', 'generator safety', 'first aid burn', 'canning tomatoes', 'radio', 'sharpen a knife']
    rep = {}
    for q in queries:
        r = do_search(q) or {}
        checked = []
        for href, text in (r.get('read', [])[:10] + r.get('videos', [])[:5] + r.get('wiki', [])[:3]):
            o = visit(norm(href))
            title = (o.get('h1') or (o.get('wiki') or {}).get('frame') or '')
            okt = bool(title) and (title[:25].lower() in text.lower() or text[:25].lower() in title.lower())
            checked.append({'hit': text[:60], 'href': norm(href)[:70], 'title': title[:60], 'match': okt, 'problem': o.get('err') or o.get('notice') or ((o.get('video') or {}).get('err') and 'video error') or None, 'pageimg': o.get('pageimg')})
        rep[q] = {'counts': {k: len(r.get(k, [])) for k in ('guides', 'passages', 'videos', 'read', 'wiki')}, 'empty': r.get('empty'), 'err': r.get('err'), 'mismatch': [c for c in checked if not c['match'] or c['problem']], 'n_checked': len(checked)}
    (OUT / 'search-hits.json').write_text(json.dumps(rep, indent=0))
    rec('search_every_hit', rep)
    r = do_search('zzqqxxnotaword')
    rec('search_nonsense', r)
    a.shot('search-nonsense.png')
    # zim cards in a nonsense search and a wiki-only search
    r = a.go('#/search?q=zzqqxxnotaword&kind=wiki', '#sout', 1500)
    rec('search_nonsense_wiki_tab', a.js("return document.getElementById('sout').innerText.slice(0,300)"))
    def in_larger(this, larger):
        p = PACKS / larger / 'pack-contents.tsv'
        rows = list(csv.DictReader(open(p, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
        return [x for x in rows if x['id'] not in ids]
    larger = {'small': 'medium', 'medium': 'all'}.get(BASE)
    if larger:
        extra = in_larger(PACK, larger)
        picks = []
        for kind in ('pdf', 'video', 'html'):
            o = [x for x in extra if x['kind'] == kind and len(x['title']) > 18 and 'pdf file' not in x['title']]
            picks += random.sample(o, min(3, len(o)))
        rep = {}
        for x in picks:
            r = do_search(x['title']) or {}
            hrefs = [h for k in ('read', 'videos', 'passages') for h, _ in r.get(k, [])]
            bad = [h for h in hrefs if x['id'] in h]
            rep[x['title'][:70]] = {'kind': x['kind'], 'id': x['id'], 'found_item_itself': bad, 'other_hits': len(hrefs), 'empty': r.get('empty'), 'err': r.get('err'), 'wiki': len(r.get('wiki', []))}
        for term in ('Corporals Corner', 'linear algebra eigenvalues'):
            r = do_search(term) or {}
            rep['TERM ' + term] = {'videos': r.get('videos', [])[:5], 'read': r.get('read', [])[:5], 'empty': r.get('empty'), 'err': r.get('err')}
        rec('search_only_in_larger_pack', rep)
    # the two skipped PDFs and flagged videos by title
    fl = [r for r in csv.DictReader(open(ROOT / 'derived/opensource-prep/safety-triage.csv')) if r['group'] == 'flagged-dangerous']
    rep = {}
    for r0 in random.sample(fl, 6):
        r = do_search(r0['title']) or {}
        rep[r0['title'][:60]] = [h for k in ('videos', 'read') for h, _ in r.get(k, []) if r0['id'] in h]
    rec('search_flagged_video_titles', rep)
    r = do_search('Anatomy and Physiology 2e')
    rec('search_skipped_pdf', {'read': (r or {}).get('read', [])[:8], 'passages': (r or {}).get('passages', [])[:4]})


# ---------------------------------------------------------------- PDFs
IMG = "const i=await until(()=>{const x=document.querySelector('img.pageimg');return x&&x.complete&&x.naturalWidth?x:null},15000);return {hash:location.hash,w:i&&i.naturalWidth,h:i&&i.naturalHeight,pg:(document.querySelector('#pg')||{}).value,title:(document.querySelector('.rtitle')||{}).innerText,src:(document.querySelector('.rsrc')||{}).innerText}"
FR = "const r=document.querySelector('iframe.frame').getBoundingClientRect();return {t:r.top,b:Math.min(r.bottom,innerHeight),l:r.left,r:r.right}"


def pix(name):
    a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(250);return 1")
    p = a.shot(name)
    fr = a.js(FR)
    return {'wk': region(p, fr['l'], fr['t'], fr['r'], fr['b']), 'frame': fr}


def pdf():
    pdfs = [r for r in contents if r['kind'] == 'pdf' and 'pdf file' not in r['title']]
    big = sorted(pdfs, key=lambda r: int(r['bytes'] or 0), reverse=True)
    doc = next((r for r in pdfs if 'first aid' in r['title'].lower()), None) or big[len(big) // 2]
    for name, r in (('main', doc), ('largest', big[0])):
        d = r['id']
        info = a.js(f"return await (await fetch('/api/doc/{d}')).json()")
        total = info.get('pages') or 1
        rec(f'pdf_{name}', {k: info.get(k) for k in ('title', 'publisher', 'pages', 'path', 'kindLabel', 'imageOnly')})
        a.go(f'#/read/{d}?p=1', 'img.pageimg', 800)
        rec(f'pdf_{name}_page_1', a.js(IMG))
        c = a.click("document.querySelector('.rbar a[aria-label=\"Next page\"]')"); time.sleep(1.2)
        rec(f'pdf_{name}_next_click', {'clicked': bool(c.get('w')), **a.js(IMG)})
        a.js("document.querySelector('#main').tabIndex=-1;document.querySelector('#main').focus();return 1")
        a.cmd('keydown', uni=0xF703, code=124, flags=0x800000); time.sleep(1.2)
        rec(f'pdf_{name}_right_arrow', a.js(IMG))
        n = min(total, max(3, total // 2))
        a.js("const p=document.querySelector('#pg');p.value='%d';p.dispatchEvent(new Event('change',{bubbles:true}));return 1" % n); time.sleep(1.5)
        rec(f'pdf_{name}_jump', {'to': n, **a.js(IMG)})
        rec(f'pdf_{name}_jump_pixels', region(a.shot(f'pdf-{name}-page.png'), 100, 100, 1180, 800))
        c = a.click("document.querySelector('[data-view=text]')"); time.sleep(1.5)
        rec(f'pdf_{name}_text_view', {'clicked': bool(c.get('w')), **a.js("const t=document.querySelector('.pagetext');return {hash:location.hash,len:t&&t.innerText.length,start:t&&t.innerText.slice(0,100)}")})
        a.shot(f'pdf-{name}-text.png')
        c = a.click("document.querySelector('[data-view=pdf]')"); time.sleep(4)
        rec(f'pdf_{name}_whole', {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash'), 'frame': a.js("return document.querySelector('iframe.frame').getAttribute('src')"), 'pix': pix(f'pdf-{name}-whole.png')})
    # "Open the original file": should do nothing in this app, no other program
    before = finlib.running_apps()
    a.go(f"#/read/{doc['id']}?p=1", 'img.pageimg', 500)
    a.js("document.querySelectorAll('details').forEach(d=>d.open=true);await sleep(200);window.__a=[...document.querySelectorAll('a[target=_blank]')].find(x=>/original file/i.test(x.innerText));window.__a&&window.__a.scrollIntoView({block:'center'});await sleep(200);return 1")
    c = a.click('window.__a'); time.sleep(1.5)
    rec('pdf_open_original', {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash'), 'apps_new': sorted(set(finlib.running_apps()) - set(before)), 'windows': [w['title'] for w in a.cmd('state').get('windows', []) if w['visible']]})
    # PDFs with active content, opened Whole PDF
    active = list(csv.DictReader(open(PACKS / 'pdf-active-content.tsv'), delimiter='\t'))
    bypath = {r['path']: r for r in contents}
    tried = {}
    want = {}
    for row in active:
        p = row['path']
        if p in bypath:
            for mk in row['markers'].split(','):
                want.setdefault(mk, p)
    for mk, p in want.items():
        d = bypath[p]['id']
        before = finlib.running_apps()
        f0 = finlib.front_name()
        a.go('#/', None, 100)
        a.go(f'#/read/{d}?p=1&view=pdf', 'iframe.frame', 3500)
        st = a.cmd('state')
        tried[mk] = {'path': p[-60:], 'pix': pix(f'pdf-active-{mk}.png'), 'apps_new': sorted(set(finlib.running_apps()) - set(before)), 'front_same': finlib.front_name() == f0, 'sheet': st.get('sheet'), 'windows': [w['title'] for w in st.get('windows', []) if w['visible']], 'marks': a.js("return (window.__errs||[]).splice(0)")}
    rec('pdf_active_content_opened', tried)
    # slides, if any
    ppt = [r for r in contents if r['kind'] == 'pptx']
    if ppt:
        rec('pptx', visit('#/read/' + ppt[0]['id']))
        a.shot('pptx.png')


# ---------------------------------------------------------------- saved page and course
def saved():
    html = [r for r in contents if r['kind'] == 'html' and r['path'].startswith('pages/') and r['id'] != 'lastbook-sources']
    strippedp = {m['path'][len('library-data/'):]: m['changes'] for m in manifest if m['how'] == 'stripped'}
    def w(r):
        ch = strippedp.get(r['path'], '')
        return sum(int(x.split('=')[1]) for x in ch.split(',') if '=' in x and not x.startswith('comment'))
    html.sort(key=w, reverse=True)
    for name, r in (('most_changed', html[0]), ('middle', html[len(html) // 2])):
        a.go(f"#/read/{r['id']}?view=web", 'iframe.frame', 1500)
        rec('saved_' + name, {'id': r['id'], 'title': r['title'], 'changes': strippedp.get(r['path']), 'src': a.js("return (document.querySelector('.rsrc')||{}).innerText"), 'in_frame': a.fjs(FRAME)})
        a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(200);return 1")
        a.shot(f'saved-{name}.png')
        c = a.click("document.querySelector('[data-view=text]')"); time.sleep(1.5)
        rec('saved_text_only_' + name, {'clicked': bool(c.get('w')), **a.js("return {hash:location.hash,len:(document.querySelector('.pagetext')||{innerText:''}).innerText.length}")})
    # a real click on links inside a saved page
    a.go(f"#/read/{html[0]['id']}?view=web", 'iframe.frame', 1500)
    rec('saved_links', a.fjs("const L=[...document.links];return {n:L.length,local:L.filter(x=>x.protocol==='lastbook:').length,web:L.filter(x=>/^https?:/.test(x.protocol)).length}"))
    for label, sel in (('web_link', "[...document.links].find(x=>/^https?:/.test(x.protocol)&&x.getBoundingClientRect().width>0)"), ('local_link', "[...document.links].find(x=>x.protocol==='lastbook:'&&!x.getAttribute('href').startsWith('#')&&x.innerText!='Offline library'&&x.getBoundingClientRect().width>0)"), ('offline_library_header_link', "[...document.links].find(x=>x.innerText=='Offline library')"), ('original_source_header_link', "[...document.links].find(x=>x.innerText=='Original source')")):
        a.go(f"#/read/{html[0]['id']}?view=web", 'iframe.frame', 900)
        r = a.fjs("const e=%s;if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel)
        if not r or (isinstance(r, dict) and r.get('__error')):
            rec('saved_click_' + label, r); continue
        q = a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(100);const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
        r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height,href:e.getAttribute('href')}" % sel)
        before = finlib.running_apps()
        a.click_at(q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2)
        time.sleep(1.5)
        rec('saved_click_' + label, {'href': r['href'], 'after': a.fjs(FRAME), 'apps_new': sorted(set(finlib.running_apps()) - set(before)), 'top': a.js('return location.hash')})
        a.shot('saved-click-' + label + '.png')
    # course
    homes = [r for r in contents if re.fullmatch(r'courses/[^/]+/index\.html?', r['path'])]
    rec('course_homes', len(homes))
    if not homes:
        return
    for r in random.sample(homes, min(5, len(homes))):
        a.go('#/', None, 100)
        a.go(f"#/read/{r['id']}?view=web", 'iframe.frame', 1800)
        rec('course_home_' + r['id'], {'title': r['title'], 'path': r['path'], 'frame': a.fjs(FRAME + "") , 'icons': a.fjs("return {font:[...document.fonts].filter(f=>/Material/.test(f.family)).map(f=>f.status),visible_ligatures:(document.body.innerText.match(/\\b(keyboard_arrow_down|expand_more|menu_book|chevron_right)\\b/g)||[]).length}")})
        links = a.fjs("return [...new Set([...document.querySelectorAll('a[href]')].map(x=>x.href).filter(h=>h.startsWith('lastbook:')))].slice(0,400)")
        rep = a.js("const hs=%s;const o={n:hs.length,ok:0,bad:[]};for(const h of hs){const c=new AbortController();const q=await fetch(h.split('#')[0],{signal:c.signal});(q.ok?o.ok++:o.bad.push([h.slice(-70),q.status]));c.abort()}return o" % json.dumps(links or []), timeout=240)
        rec('course_home_links_' + r['id'], rep)
    a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(150);return 1")
    a.shot('course-home.png')
    # lesson pages with real clicks: the first local page links visible on the home page
    where = "return {frame:location.pathname.slice(-70),title:document.title.slice(0,60),len:document.body.innerText.length,imgs:document.images.length,drawn:[...document.images].filter(i=>i.naturalWidth>0).length,scripts:document.scripts.length,start:document.body.innerText.replace(/\\s+/g,' ').slice(0,80)}"
    vis = """[...document.querySelectorAll('a[href]')].find(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(x).visibility!='hidden'&&/%s/.test(x.getAttribute('href'))&&x.protocol==='lastbook:'})"""
    out = []
    for pat in ('pages\\/syllabus', 'pages\\/lecture', 'pages\\/(calendar|readings)', 'resources\\/'):
        a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(100);return 1")
        sel = vis % pat
        r = a.fjs("const e=%s;if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel)
        time.sleep(0.25)
        if r:
            r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height,href:e.getAttribute('href')}" % sel)
        if not r or r.get('__error'):
            out.append([pat, 'no link', r]); continue
        q = a.js("const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
        x, y = q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2
        a.click_at(x, y); time.sleep(1.8)
        out.append([pat, r['href'], a.fjs(where), a.js('return location.hash')])
    rec('course_real_clicks', out)
    a.shot('course-lesson.png')
    a.cmd('back'); time.sleep(1.2)
    rec('course_back', a.fjs(where))
    # a course page's link to something not in the pack, with a real click
    slug = homes[0]['path'].split('/')[1]
    dl = '/courses/%s/download/index.html' % slug
    a.go(f"#/read/{homes[0]['id']}?view=web", 'iframe.frame', 900)
    a.js("const f=document.querySelector('iframe.frame');await new Promise(r=>{f.onload=r;f.src=%s;setTimeout(r,5000)});await sleep(300);f.scrollIntoView();return 1" % json.dumps(dl))
    L = a.fjs("return [...document.querySelectorAll('a[href]')].filter(x=>x.protocol==='lastbook:'&&x.getBoundingClientRect().width>0&&!x.getAttribute('href').startsWith('#')).map(x=>x.href).slice(0,300)") or []
    miss = a.js("const o=[];for(const h of %s){const c=new AbortController();const q=await fetch(h.split('#')[0],{signal:c.signal});if(!q.ok)o.push([h,q.status]);c.abort()}return o" % json.dumps(L), timeout=200) or []
    rec('course_download_page_links', {'slug': slug, 'links': len(L), 'dead': len(miss), 'examples': [[m[0][-70:], m[1]] for m in miss[:6]]})
    if miss:
        sel = "[...document.querySelectorAll('a[href]')].find(x=>x.href===%s)" % json.dumps(miss[0][0])
        a.fjs("const e=%s;e&&e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel); time.sleep(0.25)
        r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height}" % sel)
        q = a.js("const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
        a.click_at(q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2); time.sleep(1.5)
        rec('course_click_dead_link', {'link': miss[0][0][-70:], 'after': a.fjs(FRAME), 'top': a.js('return location.hash')})
        a.shot('course-dead-link.png')
    # course video: is the lecture video there?
    rec('course_video_like_links', a.fjs("return [...document.links].filter(x=>/\\.(mp4|m4v|webm|pdf)(#|$)/i.test(x.href)).slice(0,5).map(x=>x.href.slice(-60))"))


# ---------------------------------------------------------------- video
VID = "const v=document.querySelector('#vid');if(!v)return null;v.muted=true;v.volume=0;await until(()=>v.readyState>=1||v.error,15000);return {rs:v.readyState,err:v.error&&v.error.code,dur:Math.round(v.duration),paused:v.paused}"
VID2 = """const v=document.querySelector('#vid');v.muted=true;await v.play();await sleep(3000);
const look=()=>{let mx=-1;try{const c=document.createElement('canvas');c.width=16;c.height=9;const g=c.getContext('2d');g.drawImage(v,0,0,16,9);const d=g.getImageData(0,0,16,9).data;mx=0;for(let i=0;i<d.length;i+=4)mx=Math.max(mx,d[i]+d[i+1]+d[i+2])}catch(e){mx=String(e).slice(0,40)}return {t:+v.currentTime.toFixed(1),rs:v.readyState,w:v.videoWidth,h:v.videoHeight,err:v.error&&v.error.code,maxPixel:mx,paused:v.paused}};
const out={dur:Math.round(v.duration),start:look()};const seek=async s=>{const t=performance.now();v.currentTime=s;await Promise.race([new Promise(r=>v.addEventListener('seeked',r,{once:true})),sleep(15000)]);const ms=Math.round(performance.now()-t);await sleep(2000);return {ms,...look()}};
out.mid=await seek(v.duration/2);out.nearEnd=await seek(Math.max(v.duration-15,1));v.pause();return out"""


def video():
    vids = [r for r in contents if r['kind'] == 'video']
    rec('video_records', len(vids))
    if not vids:
        return
    have = [r for r in vids if (DATA / 'library-data' / r['path']).is_file()]
    miss = [r for r in vids if not (DATA / 'library-data' / r['path']).is_file()]
    rec('video_files', {'have': len(have), 'missing': len(miss)})
    if have:
        by = sorted(have, key=lambda r: int(r['bytes'] or 0))
        for name, r in (('small', by[0]), ('middle', by[len(by) // 2]), ('largest', by[-1])):
            a.go('#/', None, 100)
            a.go('#/watch/' + r['id'], '#vid', 200)
            rec('video_' + name, {'title': r['title'], 'publisher': r['publisher'], 'MB': int(r['bytes'] or 0) // 1000000, 'ready': a.js(VID, timeout=30), 'play_seek': a.js(VID2, timeout=70), 'meta': a.js("return (document.querySelector('.vmeta')||{}).innerText")})
        r = by[len(by) // 2]
        a.go('#/', None, 100)
        a.go('#/watch/' + r['id'], '#vid', 200)
        a.js(VID, timeout=30)
        a.js("document.querySelector('#vid').scrollIntoView({block:'center'});await sleep(200);return 1")
        c = a.click("document.querySelector('#vid')"); time.sleep(1.5)
        s1 = a.js("const v=document.querySelector('#vid');return {paused:v.paused,t:v.currentTime}")
        a.click_at(c['x'], c['y']); time.sleep(1)
        s2 = a.js("const v=document.querySelector('#vid');const o={paused:v.paused,t:v.currentTime};v.pause();return o")
        rec('video_real_click', {'after_click': s1, 'after_second': s2})
        a.shot('video.png')
        rec('video_transcript_panel', a.js("return {cues:(document.querySelector('#cues,#tbox,.cues')||{children:[]}).children.length,text:(document.querySelector('.watch')||{innerText:''}).innerText.slice(0,500)}"))
    if miss:
        a.go('#/', None, 100)
        a.go('#/watch/' + miss[0]['id'], '#vid', 200)
        time.sleep(4)
        rec('video_missing_file', {'title': miss[0]['title'], 'path': miss[0]['path'], 'video': a.js("const v=document.querySelector('#vid');return v&&{rs:v.readyState,err:v.error&&v.error.code}"), 'err': a.js("return [...document.querySelectorAll('#main .err')].map(e=>e.innerText)"), 'remote_note': a.js("return [...document.querySelectorAll('#main p.small.muted')].map(e=>e.innerText).slice(0,2)"), 'thumb': a.js(f"const q=await fetch('/api/doc/{miss[0]['id']}');const d=await q.json();return {remote:d.remote,path:d.path,keys:Object.keys(d).slice(0,30)}")})
        a.shot('video-missing.png')
    # videos in the Videos tab that have no file
    rows = a.js("const r=await (await fetch('/api/videos')).json();return Array.isArray(r)?r.length:Object.keys(r)")
    rec('api_videos_shape', rows)


# ---------------------------------------------------------------- encyclopedias
Z = "const f=document.querySelector('#wframe');const d=f&&f.contentDocument;return {wtitle:(document.querySelector('#wtitle')||{}).innerText,hash:location.hash,frame:d&&d.title,loc:f&&f.contentWindow.location.pathname.slice(-50),len:d&&d.body&&d.body.innerText.length,imgs:d?d.images.length:null,drawn:d?[...d.images].filter(i=>i.naturalWidth>0).length:null,scripts:d?d.scripts.length:null,start:d&&d.body&&d.body.innerText.replace(/\\s+/g,' ').slice(0,80),err:[...document.querySelectorAll('#main .err')].map(e=>e.innerText.slice(0,160))}"


def zim():
    a.go('#/encyclopedias', None, 800)
    cards = a.js("return [...document.querySelectorAll('#main a.card[href^=\"#/wiki/\"]')].map(x=>[x.getAttribute('href'),x.innerText.replace(/\\s+/g,' ').slice(0,60)])")
    rec('zim_cards', cards)
    a.shot('encyclopedias.png')
    have = {p.name for p in (DATA / 'library-data/collections').glob('*.zim')}
    rec('zim_files', sorted(have))
    arts = {'mdwiki': ['Burn', 'Anemia'], 'appropedia': ['Solar_cooker'], 'wikibooks': ['Cookbook', 'First_Aid'], 'wikipedia': ['Water_purification']}
    for i in range(len(cards or [])):
        a.go('#/encyclopedias', None, 500)
        h, text = cards[i]
        c = a.click("[...document.querySelectorAll('#main a.card[href^=\"#/wiki/\"]')][%d]" % i)
        time.sleep(3)
        z = a.js(Z)
        name = h.split('/')[2].split('?')[0]
        present = name in have
        rec('zim_card_click ' + name, {'present': present, 'clicked': bool(c.get('w')), **(z or {})})
        a.js("const f=document.querySelector('#wframe');f&&f.scrollIntoView();await sleep(200);return 1")
        a.shot('zim-' + name.split('_')[0] + '.png')
        if not present:
            continue
        for art in arts.get(name.split('_')[0], []):
            a.go('#/', None, 100)
            a.go(f'#/wiki/{name}/{art}', '#wframe', 2500)
            rec(f'zim_article {name} {art}', a.js(Z))
        a.js("document.querySelector('#wframe').scrollIntoView();await sleep(200);return 1")
        p = a.js("const f=document.querySelector('#wframe');const d=f.contentDocument;const L=[...d.querySelectorAll('p a[href]')].find(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.top>40&&r.top<500&&!x.href.startsWith('http')&&!x.getAttribute('href').startsWith('#')});if(!L)return null;const r=L.getBoundingClientRect(),q=f.getBoundingClientRect();return {x:q.left+r.left+Math.min(r.width/2,20),y:q.top+r.top+r.height/2,href:L.getAttribute('href')}")
        if p:
            a.click_at(p['x'], p['y']); time.sleep(2)
        rec('zim_real_link_click ' + name, {'link': p, 'after': a.js(Z)})
        a.shot('zim-article-' + name.split('_')[0] + '.png')
        a.cmd('back'); time.sleep(1.5)
        rec('zim_back ' + name, a.js(Z))
    # search box on the encyclopedias page
    a.go('#/encyclopedias?q=' + urllib.parse.quote('water purification'), None, 2500)
    hits = a.js("return [...document.querySelectorAll('#main a.row[href^=\"#/wiki/\"]')].map(x=>[x.getAttribute('href'),x.innerText.replace(/\\s+/g,' ').slice(0,70)]).slice(0,12)")
    rec('zim_search', {'hits': hits, 'text': a.js("return document.getElementById('main').innerText.slice(0,500)")})
    if hits:
        c = a.click("document.querySelector('#main a.row[href^=\"#/wiki/\"]')"); time.sleep(3)
        rec('zim_search_open', {'clicked': bool(c.get('w')), **a.js(Z)})
    wk = a.js("const q=await fetch('/api/collection-search?q=' + encodeURIComponent('water'));return {s:q.status,t:(await q.text()).slice(0,200)}")
    rec('zim_collection_search_api', wk)


# ---------------------------------------------------------------- map
def amap():
    places = {'small': [('Los Angeles', None), ('Denver', None)], 'medium': [('Los Angeles', None), ('Sacramento', None), ('Denver', None)], 'all': [('Los Angeles', None), ('Denver', None), ('Miami', None)]}.get(BASE, [('Los Angeles', None)])
    c = a.click("[...document.querySelectorAll('.tabs-top a')].find(x=>x.getAttribute('href')=='#/map')")
    await_map = a.js("await until(()=>document.querySelector('#mapc'),15000);await sleep(3500);return {hash:location.hash,canvas:(()=>{const c=document.querySelector('#mapc');return c?[c.width,c.height]:null})(),status:(document.querySelector('#mstatus')||{}).innerText,err:[...document.querySelectorAll('#main .err')].map(e=>e.innerText)}")
    rec('map_open', {'clicked': bool(c.get('w')), **(await_map or {})})
    if not (await_map or {}).get('canvas'):
        a.shot('map-none.png')
        rec('map_page_text', a.js("return document.getElementById('main').innerText.slice(0,500)"))
        return
    rec('map_first_view_pixels', region(a.shot('map-first.png'), 0, 100, 1280, 800))
    time.sleep(1)
    rec('map_covers', a.js("await until(()=>!/Loading/.test((document.querySelector('#mdata')||{}).innerText||''),8000);return {list:(document.querySelector('#mdata')||{}).innerText,link:[...document.querySelectorAll('#mdata ~ p a, section.panel a')].map(x=>x.getAttribute('href'))}"))
    rec('map_info', a.js("const i=await (await fetch('/api/map/info')).json();return {keys:Object.keys(i),datasets:(i.datasets||[]).map(d=>[d.label,d.status,d.bytes]),personal:/\\/Users\\//.test(JSON.stringify(i))}"))
    rec('map_reports_link', a.js("const q=await fetch('/reports/resource-atlas.html').catch(e=>null);return q&&q.status"))
    for place, _ in places:
        a.js("const q=document.querySelector('#pq');q.value=%s;q.dispatchEvent(new Event('input',{bubbles:true}));return 1" % json.dumps(place))
        a.js("document.querySelector('#pf').requestSubmit();return 1")
        r = a.js("await until(()=>{const p=document.querySelector('#pres');return p&&!p.hidden&&p.innerText.length>2&&!/Searching|Looking/.test(p.innerText)},8000);await sleep(300);const p=document.querySelector('#pres');return {hidden:p.hidden,text:p.innerText.slice(0,300),rows:p.querySelectorAll('button,a').length}")
        c = a.click("document.querySelector('#pres button,#pres a')")
        time.sleep(4.5)
        hash_ = a.js("return {hash:location.hash,status:(document.querySelector('#mstatus')||{}).innerText,card:(document.querySelector('#card')||{}).hidden===false?(document.querySelector('#card').innerText||'').slice(0,160):null,near:[...document.querySelectorAll('#main section.panel')].map(s=>s.innerText.slice(0,120)).slice(0,1),err:(window.__errs||[]).splice(0)}")
        p = a.shot('map-' + place.replace(' ', '-') + '.png')
        rec('map_place ' + place, {'found': r, 'clicked_first': bool(c.get('w')), 'after': hash_, 'pixels': region(p, 0, 100, 900, 800)})
    # the whole US, zoom buttons, a real drag is not sent here
    c = a.click("document.getElementById('map-us')"); time.sleep(4)
    p = a.shot('map-us.png')
    rec('map_us_button', {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash'), 'pixels': region(p, 0, 100, 900, 800)})
    for _ in range(2):
        a.click("document.getElementById('zin')"); time.sleep(1)
    rec('map_zoomed', {'hash': a.js('return location.hash')})
    # layers list
    c = a.click("document.getElementById('layers-btn')"); time.sleep(0.8)
    rec('map_layers', a.js("return document.querySelector('#layers').innerText.slice(0,800)"))
    a.shot('map-layers.png')
    t = [x for x in ('Aerial photos', 'Shaded relief', 'Orchard') if True]
    for label in t:
        sel = "[...document.querySelectorAll('#layers label,#layers button,#layers [role=button],#layers .row,#layers li')].find(x=>x.innerText.includes(%s))" % json.dumps(label)
        c = a.click(sel); time.sleep(3.5)
        rec('map_toggle ' + label, {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash.slice(-60)'), 'status': a.js("return (document.querySelector('#mstatus')||{}).innerText"), 'errs': a.js('return (window.__errs||[]).splice(0)'), 'net_404': a.js("const q=await fetch('/api/map/aerial/10/176/409');return q.status"), 'pixels': region(a.shot('map-toggle-' + label.split()[0] + '.png'), 0, 100, 900, 800)})
        c = a.click(sel); time.sleep(0.6)
    a.click("document.getElementById('layers-btn')")
    c = a.click("document.getElementById('map-3d')"); time.sleep(5)
    rec('map_3d_button', {'clicked': bool(c.get('w')), 'status': a.js("return (document.querySelector('#mstatus')||{}).innerText"), 'errs': a.js('return (window.__errs||[]).splice(0)'), 'pixels': region(a.shot('map-3d.png'), 0, 100, 900, 800)})
    a.go('#/', None, 100)
    a.go('#/map?lat=34.05&lon=-118.25&z=13.00', '#mapc', 3000)
    f0 = finlib.front_name()
    c = a.click("[...document.querySelectorAll('#main button')].find(x=>/Use my location/.test(x.innerText))"); time.sleep(2.5)
    rec('map_use_my_location', {'clicked': bool(c.get('w')), 'front_same': finlib.front_name() == f0, 'said': a.js("return (document.querySelector('#mstatus')||{}).innerText+' | '+[...document.querySelectorAll('#main section.panel')].map(s=>s.innerText).join(' ').slice(0,300)")})
    # 3D is in a pack only if terrain is
    a.go('#/', None, 100)
    a.go('#/map?lat=34.05&lon=-118.25&z=13.00', '#mapc', 3500)
    rec('map_LA_z13_pixels', region(a.shot('map-la-z13.png'), 0, 100, 900, 800))
    a.go('#/', None, 100)
    a.go('#/map?lat=39.74&lon=-104.99&z=13.00', '#mapc', 3500)
    rec('map_denver_z13_pixels', region(a.shot('map-denver-z13.png'), 0, 100, 900, 800))
    rec('map_errs', a.js('return (window.__errs||[]).splice(0)'))


# ---------------------------------------------------------------- ask
def ask():
    c = a.click("[...document.querySelectorAll('.tabs-top a')].find(x=>x.getAttribute('href')=='#/ask')")
    a.js("await until(()=>document.querySelector('#chatIn'),8000);await sleep(1500);return 1")
    rec('ask_status', {'clicked': bool(c.get('w')), 'status': a.js("return (document.querySelector('#chatStatus')||{}).innerText"), 'api': a.js("const s=await (await fetch('/api/assistant/status')).json();return {online:s.online,model:s.model,index:s.index,coverage:s.coverage}"), 'send_title': a.js("return document.querySelector('#sendBtn').title")})
    a.shot('ask.png')
    a.js("const t=document.querySelector('#chatIn');t.value='how do I boil water';t.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    r = a.js("const r=document.querySelector('#sendBtn').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}")
    a.click_at(r['x'], r['y'])
    time.sleep(5)
    rec('ask_no_model', a.js("const l=document.querySelector('#chatLog');return {text:l.innerText.slice(0,900),links:[...l.querySelectorAll('a[href^=\"#/\"]')].map(x=>[x.getAttribute('href').replace(/[?&]from=.*/,''),x.innerText.slice(0,60)]).slice(0,10),err:[...l.querySelectorAll('.err,.ans-error')].map(e=>e.innerText.slice(0,200))}"))
    a.shot('ask-no-model.png')
    first = a.js("const e=document.querySelector('#chatLog a[href^=\"#/read\"],#chatLog a[href^=\"#/watch\"]');return e?e.getAttribute('href'):null")
    if first:
        c = a.click("document.querySelector('#chatLog a[href^=\"#/read\"],#chatLog a[href^=\"#/watch\"]')"); time.sleep(1.5)
        rec('ask_fallback_link_opens', {'href': first, 'clicked': bool(c.get('w')), 'opened': a.js(ITEM_JS, timeout=50)})
    # Ask about this, from a page
    rows = [r for r in contents if r['kind'] == 'pdf']
    if rows:
        a.go(f"#/read/{rows[0]['id']}?p=1", 'img.pageimg', 300)
        c = a.click("[...document.querySelectorAll('.rtop a')].find(x=>/ask/i.test(x.innerText))"); time.sleep(1.2)
        rec('ask_about_page', {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash.slice(0,70)'), 'chip': a.js("return (document.querySelector('#ctxChip')||{}).innerText")})
    a.go('#/ask?q=' + urllib.parse.quote('zzqqxxnotaword'), None, 3500)
    rec('ask_no_model_nonsense', a.js("return (document.querySelector('#chatLog')||{innerText:''}).innerText.slice(0,400)"))


# ---------------------------------------------------------------- about and credits
def about():
    a.go('#/library', None, 400)
    c = a.click("document.querySelector('footer.foot a[href=\"#/about\"]')")
    time.sleep(1.2)
    s = snap(400)
    rec('about', {'clicked': bool(c.get('w')), 'text': a.js("return document.getElementById('main').innerText"), 'links': s.get('links')})
    a.shot('about.png')
    rec('about_status_reply_raw', a.js("const q=await fetch('/api/assistant/status');const d=await q.json();const k=Object.keys(d);return {http:q.status,keys:k,error:d.error,online:d.online,model:d.model}"))
    rec('about_download_reply_raw', a.js("const q=await fetch('/api/download-status');return {http:q.status,text:(await q.text()).slice(0,200)}"))
    out = {}
    for l, t in s.get('links', []):
        if not l.startswith('#'):
            out[l] = a.js("const q=await fetch(%s).catch(e=>null);return q&&q.status" % json.dumps(l))
    rec('about_plain_links_status', out)
    c = a.click("[...document.querySelectorAll('#main a[target=_blank]')][0]")
    time.sleep(1)
    rec('about_report_link_click', {'clicked': bool(c.get('w')), 'hash': a.js('return location.hash'), 'windows': [w['title'] for w in a.cmd('state').get('windows', []) if w['visible']]})
    # is the Sources page reachable the way a person would find it
    rec('sources_in_catalog', a.js("const q=await fetch('/api/doc/lastbook-sources');if(!q.ok)return q.status;const d=await q.json();return {title:d.title,publisher:d.publisher,path:d.path,collection:d.collection,kind:d.kind}"))
    r = do_search('Sources and permissions') or {}
    rec('sources_found_by_search', {'read': r.get('read', [])[:5], 'passages': r.get('passages', [])[:3]})
    rts = json.loads((OUT / 'routes.json').read_text()) if (OUT / 'routes.json').exists() else {}
    its = json.loads((OUT / 'items.json').read_text()) if (OUT / 'items.json').exists() else {}
    rec('sources_linked_from_a_shelf_or_guide', {k: v for k, v in its.items() if 'lastbook-sources' in k})
    a.go('#/read/lastbook-sources?view=web', 'iframe.frame', 2000)
    h = a.js("return {h1:(document.querySelector('#main h1')||{}).innerText,src:(document.querySelector('.rsrc')||{}).innerText}")
    rec('sources_page', {**(h or {}), 'frame': a.fjs(FRAME)})
    a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(200);return 1")
    a.shot('sources.png')
    txt = a.fjs("return document.body.innerText")
    (OUT / 'sources-text.txt').write_text(txt if isinstance(txt, str) else json.dumps(txt))
    pubs = sorted({r['publisher'].strip() for r in contents if r['publisher'].strip()})
    low = (txt or '').lower() if isinstance(txt, str) else ''
    missing = [p for p in pubs if p.lower() not in low]
    rec('owners_named_on_sources', {'owners': len(pubs), 'missing_from_page': missing[:40], 'n_missing': len(missing)})
    rec('weak_publisher', {'blank': sum(1 for r in contents if not r['publisher'].strip()), 'see_source': sum(1 for r in contents if r['publisher'].strip().lower() == 'see source')})
    # per-item credit, shown where the item is: a sample
    sample = random.sample([r for r in contents if r['kind'] in ('pdf', 'html', 'video')], min(40, sum(1 for r in contents if r['kind'] in ('pdf', 'html', 'video'))))
    rep = {'n': 0, 'publisher_shown': 0, 'no': []}
    for r in sample:
        o = visit(('#/watch/' if r['kind'] == 'video' else '#/read/') + r['id'])
        rep['n'] += 1
        if r['publisher'].strip() and r['publisher'].strip().lower()[:12] in (o.get('src') or '').lower():
            rep['publisher_shown'] += 1
        else:
            rep['no'].append([r['id'], r['publisher'], o.get('src')])
    rec('credit_on_item_pages', rep)
    # the guide-level source naming: a video card and a topic row
    # "known gap" visible anywhere?
    rec('known_gap_said_in_app', a.js("const a=await fetch('/documents/lastbook/sources-and-permissions.html');const t=await a.text();return {sources_page_mentions_gap:/anatomy/i.test(t),biology:/biology 2e|biology-2e/i.test(t)}"))


def guides():
    """Guides are written into the program, not the pack: what does each size leave of them?"""
    t = a.js("const t=await (await fetch('/api/topics')).json();return Array.isArray(t)?t:t.topics")
    rep = {}
    for x in t:
        d = a.js("const q=await fetch('/api/topics/%s');return q.ok?await q.json():null" % x['id']) or x
        o = {'choices_no_read': [c.get('label') for c in d.get('choices', []) if not c.get('read') and not c.get('videos') and not c.get('goto')], 'route_steps': len(d.get('route', [])), 'route_steps_empty': [c.get('title') for c in d.get('route', []) if not c.get('read') and not c.get('videos') and not c.get('watch')], 'n_choices': len(d.get('choices', [])), 'prepare': len(d.get('prepare', [])), 'learn': len(d.get('learn', [])), 'keys': sorted(k for k in d if isinstance(d[k], list))}
        rep[x['id']] = o
    rec('guides_left', rep)
    a.go('#/t/grow', None, 800)
    a.shot('guide-grow.png')
    a.go('#/t/hurt', None, 800)
    a.shot('guide-hurt.png')


def probe():
    """Pages that looked wrong in the walk, looked at slowly."""
    rep = {}
    for i in ('2bcf93d0ed97f2', 'd1939b3a01cf0c', '3cd9cea3aa8af4', 'f55f3c8aa35447'):
        if i not in ids:
            continue
        a.go(f'#/read/{i}?view=web', 'iframe.frame', 3000)
        lst = a.fjs("return [...document.images].filter(x=>!x.naturalWidth).map(x=>({src:x.getAttribute('src'),url:x.src,complete:x.complete,alt:x.alt,loading:x.loading,box:[x.getBoundingClientRect().width,x.getBoundingClientRect().height],shown:getComputedStyle(x).display}))") or []
        out = []
        for x in lst[:4]:
            if not isinstance(x, dict) or not x.get('url'):
                continue
            d = a.js("try{const q=await fetch(%s);const b=await q.blob();let bm=null;try{const m=await createImageBitmap(b);bm=[m.width,m.height]}catch(e){bm=String(e).slice(0,60)}return {s:q.status,t:q.headers.get('content-type'),n:b.size,bitmap:bm,csp:q.headers.get('content-security-policy')}}catch(e){return String(e).slice(0,80)}" % json.dumps(x['url']))
            out.append({**x, 'fetch': d})
        rep[i] = out
        a.fjs("const e=[...document.images].find(x=>!x.naturalWidth);e&&e.scrollIntoView({block:'center',behavior:'instant'});return 1")
        a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(300);return 1")
        a.shot('probe-' + i + '.png')
    rec('probe_undrawn', rep)
    rep = {}
    for i in ('mfg-b4e6847e10914700', 'community-seed-6d9f9a129f4e708c', 'community-seed-9b09c8905f641be6', 'community-seed-93bfc8eb83b1ecc3'):
        if i not in ids:
            continue
        a.go('#/', None, 200)
        t = time.time()
        a.go(f'#/read/{i}?view=web', 'iframe.frame', 500)
        v = None
        for _ in range(60):
            v = a.fjs(FRAME, timeout=20)
            if isinstance(v, dict) and v.get('len'):
                break
            time.sleep(1)
        rep[i] = {'secs': round(time.time() - t, 1), 'frame': v, 'file': next((r['path'] + ' ' + r['bytes'] for r in contents if r['id'] == i), None)}
        a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(200);return 1")
        a.shot('probe-' + i + '.png')
    rec('probe_empty_frames', rep)


def imgsize():
    """Which saved-page pictures fail to draw: by size? by kind? in a frame, or everywhere?"""
    rows = [m for m in manifest if m['path'].startswith('library-data/assets/') and re.search(r'\.(jpe?g|png)$', m['path'], re.I)]
    rows.sort(key=lambda m: int(m['bytes']))
    pick = rows[:: max(1, len(rows) // 60)][:70]
    html = '<!doctype html><title>t</title>' + ''.join('<img src="/%s" width=60>' % m['path'][len('library-data/'):] for m in pick)
    t = DATA / 'library-data/pages/__imgtest.html'
    t.write_text(html)
    a.go('#/read/lastbook-sources?view=web', 'iframe.frame', 400)
    a.js("const f=document.querySelector('iframe.frame');await new Promise(r=>{f.onload=r;f.src='/pages/__imgtest.html';setTimeout(r,9000)});await sleep(2500);return 1", timeout=20)
    res = a.fjs("return [...document.images].map(i=>[i.getAttribute('src'),i.naturalWidth,i.complete])") or []
    size = {'/' + m['path'][len('library-data/'):]: int(m['bytes']) for m in pick}
    rows2 = sorted([(size.get(r[0], 0), r[1], r[2], r[0][-30:]) for r in res])
    (OUT / 'imgsize.json').write_text(json.dumps(rows2, indent=0))
    rec('img_in_sandbox_frame', {'n': len(rows2), 'failed': [x for x in rows2 if not x[1]][:40], 'largest_ok': max([x[0] for x in rows2 if x[1]] or [0]), 'smallest_failed': min([x[0] for x in rows2 if not x[1]] or [0])})
    top = a.js("const o=[];for(const u of %s){const r=await new Promise(res=>{const i=new Image();i.onload=()=>res(i.naturalWidth);i.onerror=()=>res(0);i.src=u;setTimeout(()=>res(-1),8000)});o.push([u.slice(-30),r])}return o" % json.dumps([r[0] for r in res][-20:]), timeout=200)
    rec('img_same_files_in_top_page', top)
    t.unlink()


def imgone():
    t = DATA / 'library-data/pages/field-survival/__t.html'
    F = ['a51bd879317176b1d2cf.jpg', '65d6e25e4ccc7e73b69e.jpg', '7ba417e54fd54e822b47.png', 'd760bee14c7818a28ad9.jpg', '9c801875e31109b58ed5.png']
    t.write_text('<!doctype html><title>t</title>' + ''.join('<img src="../../assets/field-survival/%s" width=60>' % f for f in F))
    a.go('#/read/lastbook-sources?view=web', 'iframe.frame', 400)
    a.js("const f=document.querySelector('iframe.frame');await new Promise(r=>{f.onload=r;f.src='/pages/field-survival/__t.html';setTimeout(r,9000)});await sleep(1500);return 1", timeout=20)
    rec('imgone_plain_page', a.fjs("return [...document.images].map(i=>[i.getAttribute('src').slice(-12),i.naturalWidth,i.complete])"))
    a.go('#/read/2bcf93d0ed97f2?view=web', 'iframe.frame', 2500)
    rec('imgone_real_page', a.fjs("return [...document.images].map(i=>[(i.getAttribute('src')||'').slice(0,40),i.naturalWidth,i.complete,i.crossOrigin,i.referrerPolicy,i.decoding,i.sizes,i.srcset&&i.srcset.slice(0,50)])"))
    rec('imgone_doc', a.fjs("return {sheets:[...document.styleSheets].map(s=>s.href),base:document.baseURI,url:document.URL,ct:document.contentType,html:document.documentElement.outerHTML.slice(0,300)}"))
    t.unlink()


def course2():
    """No course home has a catalog record, so no shelf reaches one. Opened here by giving the reader's frame the address, then used with real clicks."""
    homes = sorted((DATA / 'library-data/courses').glob('*/index.html'))
    rec('course_folders_with_home', len(homes))
    def load(u, name=None):
        a.js("const f=document.querySelector('iframe.frame');await new Promise(r=>{f.onload=r;f.src=%s;setTimeout(r,7000)});await sleep(600);f.scrollIntoView();await sleep(150);return 1" % json.dumps(u), timeout=20)
    W = "return {frame:location.pathname.slice(-70),title:document.title.slice(0,60),len:document.body.innerText.length,imgs:document.images.length,drawn:[...document.images].filter(i=>i.naturalWidth>0).length,undrawn:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.getAttribute('src')).slice(0,4),scripts:document.scripts.length,start:document.body.innerText.replace(/\\s+/g,' ').slice(0,90),icons:(document.body.innerText.match(/\\b(keyboard_arrow_down|expand_more|menu_book|chevron_right|search|menu)\\b/g)||[]).length,linkFonts:[...document.fonts].map(f=>f.family+':'+f.status).slice(0,4)}"
    a.go('#/read/lastbook-sources?view=web', 'iframe.frame', 400)
    picks = random.sample(homes, min(4, len(homes)))
    for h in picks:
        slug = h.parent.name
        load('/courses/%s/index.html' % slug)
        rec('course_home ' + slug, a.fjs(W))
        L = a.fjs("return [...new Set([...document.querySelectorAll('a[href]')].filter(x=>x.protocol==='lastbook:'&&!x.getAttribute('href').startsWith('#')).map(x=>x.href.split('#')[0]))].slice(0,300)") or []
        rep = a.js("const o={n:0,ok:0,bad:[]};for(const h of %s){const c=new AbortController();const q=await fetch(h,{signal:c.signal});o.n++;(q.ok?o.ok++:o.bad.push([h.slice(-60),q.status]));c.abort()}o.bad=o.bad.slice(0,8);return o" % json.dumps(L), timeout=200)
        rec('course_home_links ' + slug, rep)
    slug = picks[0].parent.name
    load('/courses/%s/index.html' % slug)
    a.shot('course-home.png')
    vis = """[...document.querySelectorAll('a[href]')].find(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(x).visibility!='hidden'&&/%s/.test(x.getAttribute('href'))&&x.protocol==='lastbook:'})"""
    out = []
    for pat in ('pages\\/syllabus', 'pages\\/lecture', 'pages\\/(calendar|readings|assignments)', 'download'):
        sel = vis % pat
        r = a.fjs("const e=%s;if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel); time.sleep(0.3)
        if not r:
            out.append([pat, 'no visible link']); continue
        r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height,href:e.getAttribute('href')}" % sel)
        q = a.js("const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
        a.click_at(q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2); time.sleep(1.8)
        out.append([pat, r['href'], a.fjs(W)])
    rec('course_real_clicks', out)
    a.shot('course-lesson.png')
    a.cmd('back'); time.sleep(1.2)
    rec('course_back', a.fjs(W))
    # the download page: its links to files left out
    load('/courses/%s/download/index.html' % slug)
    L = a.fjs("return [...document.querySelectorAll('a[href]')].filter(x=>x.protocol==='lastbook:'&&x.getBoundingClientRect().width>0&&!x.getAttribute('href').startsWith('#')).map(x=>x.href).slice(0,300)") or []
    miss = a.js("const o=[];for(const h of %s){const c=new AbortController();const q=await fetch(h.split('#')[0],{signal:c.signal});if(!q.ok)o.push([h,q.status]);c.abort()}return o" % json.dumps(L), timeout=200) or []
    rec('course_download_page', {'slug': slug, 'links': len(L), 'dead': len(miss), 'examples': [[m[0][-70:], m[1]] for m in miss[:6]]})
    if miss:
        sel = "[...document.querySelectorAll('a[href]')].find(x=>x.href===%s)" % json.dumps(miss[0][0])
        a.fjs("const e=%s;e&&e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel); time.sleep(0.3)
        r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height}" % sel)
        q = a.js("const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
        a.click_at(q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2); time.sleep(1.5)
        rec('course_click_dead_link', {'link': miss[0][0][-70:], 'after': a.fjs(W), 'top': a.js('return location.hash')})
        a.shot('course-dead-link.png')
    # the handbook, which does have records
    nist = next((r for r in contents if r['id'].startswith('nist-handbook') and r['kind'] == 'html'), None)
    if nist:
        a.go(f"#/read/{nist['id']}?view=web", 'iframe.frame', 1200)
        rec('handbook_page', {'title': nist['title'], 'frame': a.fjs(W)})
        a.shot('handbook.png')
    # the transcript records that search offers as videos
    tr = [r for r in contents if r['kind'] == 'transcript' and r['id'].startswith('course-transcript')][:3]
    for r in tr:
        a.go('#/', None, 100)
        a.go('#/watch/' + r['id'], None, 2500)
        rec('course_transcript_as_video ' + r['id'], {'title': r['title'], 'path': r['path'], 'hash': a.js('return location.hash.slice(0,70)'), 'vid': a.js("const v=document.querySelector('#vid');return v?{rs:v.readyState,err:v.error&&v.error.code,src:v.getAttribute('src')}:null"), 'err': a.js("return [...document.querySelectorAll('#main .err')].map(e=>e.innerText.slice(0,160))"), 'text': a.js("return document.getElementById('main').innerText.slice(0,260)"), 'doc': a.js("const d=await (await fetch('/api/doc/%s')).json();return {kind:d.kind,videoId:d.videoId,path:d.path,pathkeys:Object.keys(d).slice(0,12)}" % r['id'])})
    a.shot('course-transcript.png')
    # one saved page: dead header link with a real click
    pg = next((r for r in contents if r['kind'] == 'html' and r['path'].startswith('pages/field-survival')), None)
    if pg:
        a.go(f"#/read/{pg['id']}?view=web", 'iframe.frame', 1200)
        sel = "[...document.links].find(x=>x.innerText=='Offline library')"
        r = a.fjs("const e=%s;if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});return 1" % sel); time.sleep(0.3)
        if r:
            a.js("document.querySelector('iframe.frame').scrollIntoView();await sleep(120);return 1")
            r = a.fjs("const e=%s;const q=e.getBoundingClientRect();return {l:q.left,t:q.top,w:q.width,h:q.height,href:e.getAttribute('href')}" % sel)
            q = a.js("const q=document.querySelector('iframe.frame').getBoundingClientRect();return {l:q.left,t:q.top}")
            a.click_at(q['l'] + r['l'] + min(r['w'] / 2, 20), q['t'] + r['t'] + r['h'] / 2); time.sleep(1.5)
            rec('saved_offline_library_link', {'href': r['href'], 'after': a.fjs(FRAME), 'top': a.js('return location.hash'), 'fetch': a.js("const q=await fetch('/index.html');return q.status")})
            a.shot('saved-offline-library-click.png')


def trcheck():
    """Transcript records: does each lead to its video, or to a player that cannot play a text file?"""
    tr = [r for r in contents if r['kind'] == 'transcript']
    out = {'n': len(tr), 'with_videoId': 0, 'no_videoId': 0, 'examples_no_video': [], 'videoId_missing_in_pack': 0}
    allv = {r['id'] for r in contents if r['kind'] == 'video'}
    for i in range(0, len(tr), 80):
        res = a.js("const o=[];for(const id of %s){const q=await fetch('/api/doc/'+encodeURIComponent(id));if(!q.ok){o.push([id,q.status]);continue}const d=await q.json();o.push([id,d.videoId||null,d.path,d.title])}return o" % json.dumps([x['id'] for x in tr[i:i + 80]]), timeout=120) or []
        for x in res:
            if x[1] and isinstance(x[1], str):
                out['with_videoId'] += 1
                if x[1] not in allv:
                    out['videoId_missing_in_pack'] += 1
            else:
                out['no_videoId'] += 1
                if len(out['examples_no_video']) < 5:
                    out['examples_no_video'].append(x)
    rec('transcript_records', out)
    r = do_search('linear algebra eigenvalues') or {}
    rec('search_linear_algebra_video_row', r.get('videos', [])[:10])
    n = 0
    bad = []
    for href, text in r.get('videos', [])[:10]:
        o = visit(norm(href))
        n += 1
        if (o.get('video') or {}).get('err') or o.get('err'):
            bad.append([text[:50], o.get('err')])
    rec('search_linear_algebra_video_row_open', {'opened': n, 'failed': bad})
    a.go('#/search?q=eigenvalues&kind=video', None, 1800)
    rec('search_video_tab_cards', a.js("return [...document.querySelectorAll('#sres a.vcard')].map(x=>x.getAttribute('href').slice(0,40)).slice(0,12)"))
    a.shot('search-video-tab.png')


def reportlink():
    a.go('#/map', '#mapc', 2500)
    h0 = a.js('return location.href')
    c = a.click("[...document.querySelectorAll('a')].find(x=>x.getAttribute('href')==='/reports/resource-atlas.html')"); time.sleep(1.5)
    st = a.cmd('state')
    rec('map_report_link_click', {'clicked': bool(c.get('w')), 'same_page': a.js('return location.href') == h0, 'url': st.get('url'), 'text': a.js("return document.body.innerText.slice(0,80)")})
    a.go('#/about', None, 500)
    h0 = a.js('return location.href')
    c = a.click("[...document.querySelectorAll('#main a')].find(x=>/Gap closure/.test(x.innerText))"); time.sleep(1.5)
    st = a.cmd('state')
    rec('about_report_link_real_click', {'clicked': bool(c.get('w')), 'same_page': a.js('return location.href') == h0, 'url': st.get('url'), 'windows': [w['title'] for w in st.get('windows', []) if w['visible']]})


def control():
    """Saved state and Saved page, with the app's own buttons."""
    rows = [r for r in contents if r['kind'] == 'pdf']
    if not rows:
        return
    a.go(f"#/read/{rows[0]['id']}?p=1", 'img.pageimg', 300)
    c = a.click("document.querySelector('[data-save]')"); time.sleep(0.5)
    a.go('#/saved', None, 500)
    rec('saved_item', {'clicked': bool(c.get('w')), 'text': a.js("return document.getElementById('main').innerText.slice(0,300)")})
    c = a.click("#main .collection a.row".join(["document.querySelector('", "')"])); time.sleep(1.2)
    rec('saved_item_opens', {'clicked': bool(c.get('w')), 'h': a.js('return location.hash.slice(0,60)')})


try:
    st = a.wait_up(240)
    rec('up', st)
    a.js(HELP_ERR + "return 1")
    rec('fresh_store', a.js("return Object.keys(localStorage)"))
    rec('start_seconds', round(time.time() - a.started, 1))
    for fn in (chrome, crawl, walk_items, records, served_bytes, compare, search, pdf, saved, video, zim, amap, ask, about, control, guides, probe, imgsize, imgone, course2, trcheck, reportlink):
        section(fn)
        if not a.ours():
            rec('APP_DIED_AFTER', fn.__name__)
            break
finally:
    rec('this_instance_ever_frontmost', len(frontmost))
    rec('store_paths', [l.split()[-1] for l in finlib.sh('/usr/sbin/lsof', '-nP', '-a', '-p', str(a.pid)).splitlines() if 'WebKit' in l and 'Library' in l][:6])
    a.finish('close')
    (OUT / 'walk.json').write_text(json.dumps(results, indent=1, default=str))
