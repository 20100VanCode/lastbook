"""Real-window checks on this Mac, off-screen, for two rules: library content runs no scripts, and nothing reaches the network.
A decoy on 127.0.0.1:8943 stands in for the internet and logs every connection. Controls take one layer away at a time, to show the layer is what stops it.
Every click on a link goes through the product's navigation delegate, which cancels it: nothing reaches the system. No model; never packaged.
  python mac_noscript_check.py SECTION NAME   (product, rules-alone, no-layers, js-layer, js-control, frame-hole, bad-rules, pages)"""
import json, os, socket, sys, threading, time
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, '/path/to/lastbook/app/tests')
from mac_driver import Run, DATA

PORT = 8943
D = f'http://127.0.0.1:{PORT}'
PAGES = DATA / 'library-data' / 'pages' / 'nsc'
COURSES = 'courses/'
hits = []


def decoy():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', PORT))
    s.listen(64)

    def one(c):
        c.settimeout(1)
        try:
            first = c.recv(200)
        except OSError:
            first = b''
        hits.append(first.split(b'\r\n')[0].decode('latin-1')[:90] or '(connected, sent nothing)')
        try:
            c.sendall(b'HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n')
        except OSError:
            pass
        c.close()

    while True:
        c, _ = s.accept()
        threading.Thread(target=one, args=(c,), daemon=True).start()


def beacon(name, quote='"'):
    return f"new Image().src={quote}lastbook://app/pages/nsc/ran-{name}.png{quote}"


def write_pages():
    PAGES.mkdir(parents=True, exist_ok=True)
    (PAGES / 'x.js').write_text(beacon('external') + ';')
    (PAGES / 'pic.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg"><script>{beacon("svg-file")}</script></svg>')
    (PAGES / 'target.html').write_text('<!doctype html><title>target</title><p>arrived</p>')
    (PAGES / 'inner.html').write_text(f'<!doctype html><script>{beacon("nested-frame")}</script><img src="{D}/page-nested-img">')
    (PAGES / 'attack.html').write_text(f'''<!doctype html><html><head><title>attack</title><base href="{D}/page-base/">
<meta http-equiv="refresh" content="1;url={D}/page-refresh">
<link rel=stylesheet href="{D}/page-css"><link rel=preconnect href="{D}"><link rel=prefetch href="{D}/page-prefetch"><link rel=preload as=image href="{D}/page-preload"><link rel=dns-prefetch href="//decoy.invalid">
<style>@import url({D}/page-import);@font-face{{font-family:Z;src:url({D}/page-font)}}body{{font-family:Z;background:url({D}/page-bg)}}</style>
<script>{beacon("inline")}</script><script src="/pages/nsc/x.js"></script><script>eval('{beacon("eval", chr(92) + chr(34))}')</script>
<noscript><iframe src="{D}/page-noscript-frame"></iframe><img src="{D}/page-noscript-img"><link rel=stylesheet href="{D}/page-noscript-css"></noscript></head>
<body onload='{beacon("onload")}'>
<img src="nothing" onerror='{beacon("onerror")}'><img src="{D}/page-img"><svg onload='{beacon("svg-onload")}'><script>{beacon("svg-inline")}</script><image href="{D}/page-svg-img"/></svg>
<video src="{D}/page-video" autoplay></video><audio src="{D}/page-audio" autoplay></audio><video><source src="{D}/page-source"><track src="{D}/page-track" default></video>
<object data="{D}/page-object"></object><embed src="{D}/page-embed"><object data="/pages/nsc/pic.svg"></object><embed src="/pages/nsc/pic.svg"><img src="/pages/nsc/pic.svg">
<iframe src="{D}/page-frame"></iframe><iframe src="/pages/nsc/inner.html"></iframe><iframe src="/pages/nsc/pic.svg"></iframe>
<iframe srcdoc='<script>{beacon("srcdoc")}</script><img src="{D}/page-srcdoc-img">'></iframe><iframe src='data:text/html,<script>{beacon("data-frame")}</script>'></iframe>
<a ping="{D}/page-ping" href="#x" id=p>ping</a><form action="{D}/page-form" method=post><input name=a value=b><input type=submit autofocus></form></body></html>''')
    links = [('data', f'data:text/html,<script>{beacon("data-link")}</script>'), ('javascript', f'javascript:{beacon("js-link")}'), ('https', 'https://example.invalid/x'), ('decoy', f'{D}/click-decoy'),
             ('mailto', 'mailto:a@example.invalid'), ('tel', 'tel:1'), ('macappstore', 'macappstore://example.invalid/x'), ('itms', 'itms://example.invalid/x'), ('unknown', 'foo-bar://x'),
             ('app', 'lastbook://app/'), ('api', '/api/health')]
    rows = ''.join(f'<a href="{h.replace(chr(34), "&quot;")}" style="display:block;height:40px" id="l{i}">{n}</a>' for i, (n, h) in enumerate(links))
    rows += f'<a href="{D}/click-blank" target=_blank style="display:block;height:40px">blank</a><a href="{D}/click-top" target=_top style="display:block;height:40px">top</a><a ping="{D}/click-ping" href="#y" style="display:block;height:40px">ping</a>'
    rows += '<form action="' + D + '/click-form" method=post style="height:40px;margin:0"><input type=submit value="send" style="display:block;height:38px;width:300px"></form><a href="target.html" target=_blank download style="display:block;height:40px">local</a>'
    (PAGES / 'click.html').write_text(f'<!doctype html><title>click</title><body style="margin:0">{rows}')
    return [n for n, _ in links] + ['blank', 'top', 'ping', 'form', 'local']


def top_probe(r):
    """What the app's own page could ask for, with no content policy in the way: the rule list alone answers it."""
    return r.js(f"""
const D={json.dumps(D)};const log={{}};const box=document.createElement('div');box.style='position:fixed;left:0;top:0;width:10px;height:10px;overflow:hidden';document.body.append(box);
const add=(t,a)=>{{const e=document.createElement(t);Object.assign(e,a);box.append(e);return e}};
add('img',{{src:D+'/top-img'}});add('img',{{src:'https://127.0.0.1:{PORT}/top-https-img'}});add('link',{{rel:'stylesheet',href:D+'/top-css'}});add('script',{{src:D+'/top-script'}});
add('video',{{src:D+'/top-video',autoplay:true,muted:true}});add('audio',{{src:D+'/top-audio',autoplay:true}});
const v=add('video',{{}});const so=document.createElement('source');so.src=D+'/top-source';v.append(so);const tr=document.createElement('track');tr.src=D+'/top-track';tr.default=true;v.append(tr);v.load();
add('link',{{rel:'preconnect',href:D}});add('link',{{rel:'prefetch',href:D+'/top-prefetch'}});add('link',{{rel:'preload',as:'image',href:D+'/top-preload'}});add('link',{{rel:'dns-prefetch',href:'//decoy.invalid'}});
add('style',{{textContent:'@import url('+D+'/top-import);@font-face{{font-family:Z9;src:url('+D+'/top-font)}}#__fz{{font-family:Z9;background:url('+D+'/top-bg)}}'}});add('div',{{id:'__fz',textContent:'x'}});
try{{new FontFace('Z8','url('+D+'/top-fontface)').load().catch(()=>{{}})}}catch(e){{log.fontface=String(e)}}
add('iframe',{{src:D+'/top-frame'}});add('iframe',{{srcdoc:'<link rel=stylesheet href="'+D+'/srcdoc-css"><img src="'+D+'/srcdoc-img"><video src="'+D+'/srcdoc-video" autoplay></video><iframe src="'+D+'/srcdoc-frame"></iframe>'}});
for(const [n,f] of Object.entries({{
  fetch:()=>fetch(D+'/top-fetch',{{mode:'no-cors'}}),
  xhr:()=>new Promise((ok,no)=>{{const x=new XMLHttpRequest();x.open('GET',D+'/top-xhr');x.onload=ok;x.onerror=()=>no('error');x.send()}}),
  eventsource:()=>{{const s=new EventSource(D+'/top-es');setTimeout(()=>s.close(),1500);return 'made'}},
  websocket:()=>{{const s=new WebSocket('ws://127.0.0.1:{PORT}/top-ws');return 'made'}},
  beacon:()=>navigator.sendBeacon?navigator.sendBeacon(D+'/top-beacon','x'):'no sendBeacon',
  rtc:()=>typeof RTCPeerConnection,
}})){{try{{log[n]=String(await f()).slice(0,60)}}catch(e){{log[n]='refused: '+String(e).slice(0,70)}}}}
const a=add('a',{{href:'#__p'}});a.setAttribute('ping',D+'/top-ping');a.click();
await sleep(3000);box.remove();return log""")


def frame_with(r, src):
    return r.js(f"document.querySelectorAll('.__tf').forEach(x=>x.remove());const f=document.createElement('iframe');f.className='__tf';f.style='position:fixed;left:0;top:0;width:800px;height:760px;z-index:99999;background:#fff;border:0';f.src={json.dumps(src)};document.body.append(f);await sleep(1200);return 1")


def ran(r, since=0):
    return sorted({x.get('t', '').rsplit('/ran-', 1)[-1] for x in r.log('bridge', since) if '/ran-' in str(x.get('t'))})


def attack(r):
    t0 = time.time()
    n = len(hits)
    frame_with(r, '/pages/nsc/attack.html')
    time.sleep(5)
    r.rec('attack_page_scripts_that_ran', ran(r, t0))
    r.rec('attack_page_decoy_hits', hits[n:])
    r.rec('attack_page_requests', sorted({str(x.get('t')) for x in r.log('bridge', t0)}))
    r.shot('attack.png')


def clicks(r, names):
    out = {}
    for i, name in enumerate(names):
        frame_with(r, '/pages/nsc/click.html')
        t0, n = time.time(), len(hits)
        r.cmd('click', x=100, y=20 + 40 * i)
        time.sleep(1)
        out[name] = {'decisions': [(x['url'][:60], x['target'], x['decision']) for x in r.log('decide', t0)], 'decoy': hits[n:], 'ran': ran(r, t0), 'leave': [x.get('url', '')[:50] for x in r.log('leave', t0)], 'windows': len(r.cmd('state').get('windows', [])), 'top': r.js('return location.href')[:40]}
        r.rec('frame_click_' + name, out[name])
    r.js("document.querySelectorAll('.__tf').forEach(x=>x.remove());return 1")
    for name, href in (('https', 'https://example.invalid/top'), ('mailto', 'mailto:a@example.invalid'), ('macappstore', 'macappstore://example.invalid/x'), ('unknown', 'foo-bar://x'), ('decoy', D + '/top-click')):
        for tgt in ('', ' target="_blank"'):
            r.js(f"let d=document.getElementById('__t');if(d)d.remove();d=document.createElement('div');d.id='__t';d.style='position:fixed;left:0;top:0;width:400px;z-index:99999;background:#fff';d.innerHTML={json.dumps(f'<a{tgt} href={chr(34)}{href}{chr(34)} style={chr(34)}display:block;height:40px{chr(34)}>x</a>')};document.body.append(d);return 1")
            t0, n = time.time(), len(hits)
            r.cmd('click', x=50, y=20)
            time.sleep(0.8)
            r.rec(f'top_click_{name}{"_blank" if tgt else ""}', {'decisions': [(x['url'][:50], x['target'], x['decision']) for x in r.log('decide', t0)], 'decoy': hits[n:], 'top': r.js('return location.href')[:40], 'windows': len(r.cmd('state').get('windows', []))})
    r.js("document.getElementById('__t').remove();return 1")


def ui(r):
    r.go('#/wiki/appropedia_en_all_maxi_2026-02.zim/Solar_cooker', '#wframe', 2500)
    r.rec('zim_article', r.js("const f=document.querySelector('#wframe');const d=f.contentDocument;return {wtitle:document.querySelector('#wtitle').innerText,hash:location.hash,frame:d&&d.title,words:d?d.body.innerText.split(/\\s+/).length:null,images:d?d.images.length:null,drawn:d?[...d.images].filter(i=>i.naturalWidth).length:null,links:d?d.links.length:null,base:d?d.querySelectorAll('base').length:null,firstLink:d?[...d.links].map(a=>a.getAttribute('href')).find(h=>h&&!h.startsWith('#')&&!/^https?:/.test(h)):null}"))
    r.shot('zim.png')
    # a link inside the encyclopedia page, followed by the reader's title and address
    t = r.js("const f=document.querySelector('#wframe');const a=[...f.contentDocument.links].find(a=>{const h=a.getAttribute('href');const q=a.getBoundingClientRect();return h&&!h.startsWith('#')&&!/^https?:/.test(h)&&q.top>40&&q.bottom<f.clientHeight-10&&q.left>0&&q.width>4});const q=a.getBoundingClientRect(),o=f.getBoundingClientRect();return {x:o.left+q.left+Math.min(q.width/2,10),y:o.top+q.top+q.height/2,href:a.getAttribute('href')}")
    if t and t.get('x'):
        r.js(f"document.querySelector('#wframe').scrollIntoView({{block:'start'}});return 1")
        t = r.js("const f=document.querySelector('#wframe');const a=[...f.contentDocument.links].find(a=>{const h=a.getAttribute('href');const q=a.getBoundingClientRect();return h&&!h.startsWith('#')&&!/^https?:/.test(h)&&q.top>40&&q.bottom<f.clientHeight-10&&q.left>0&&q.width>4});const q=a.getBoundingClientRect(),o=f.getBoundingClientRect();return {x:o.left+q.left+Math.min(q.width/2,10),y:o.top+q.top+q.height/2,href:a.getAttribute('href')}")
        r.cmd('click', x=t['x'], y=t['y'])
        time.sleep(2)
        r.rec('zim_link_followed', {'clicked': t['href'], 'after': r.js("const f=document.querySelector('#wframe');return {wtitle:document.querySelector('#wtitle').innerText,hash:location.hash,frame:f.contentDocument&&f.contentDocument.title}")})
    r.go('#/', None, 300)
    r.go('#/wiki/appropedia_en_all_maxi_2026-02.zim/', '#wframe', 2500)
    r.rec('zim_main_by_meta_redirect', r.js("const f=document.querySelector('#wframe');return {wtitle:document.querySelector('#wtitle').innerText,hash:location.hash,frame:f.contentDocument&&f.contentDocument.title,where:f.contentWindow.location.pathname}"))
    r.go('#/', None, 300)
    r.go('#/read/f7ff53bcaae9cc?p=9&view=pdf', 'iframe.frame', 2500)
    r.rec('pdf_page_jump', r.js("const f=document.querySelector('iframe.frame');return {src:f.getAttribute('src').slice(-30),plugin:!!(f.contentDocument&&f.contentDocument.querySelector('embed'))}"))
    r.shot('pdf.png')
    r.go('#/', None, 300)
    r.go('#/read/99dd5e2cc78a16a0?view=web', 'iframe.frame', 2000)
    r.shot('saved.png')
    r.rec('saved_page_view', r.js("const f=document.querySelector('iframe.frame');return {src:f.getAttribute('src').slice(-40),readable_from_app:(()=>{try{return !!f.contentDocument}catch(e){return 'error'}})()}"))
    r.rec('home_after', r.js("location.hash='#/';await sleep(800);return {h1:document.querySelector('#main h1').innerText,api:(await fetch('/api/health')).status}"))
    r.go('#/map', 'canvas', 1500)
    r.rec('map_opens', r.js("return {canvas:!!document.querySelector('canvas')}"))
    r.rec('menu', r.cmd('menu', ids=['WKMenuItemIdentifier' + n for n in ('Copy', 'CopyLink', 'OpenLink', 'SearchWeb', 'LookUp', 'ShareMenu', 'Translate', 'WritingTools', 'SpeechMenu')]))


def pages(r):
    write_pages()
    for name, path in (('video', 'courses/5-60-thermodynamics-kinetics-spring-2008/resources/lecture-30-introduction-to-reaction-kinetics/index.html'),
                       ('download', 'courses/18-05-introduction-to-probability-and-statistics-spring-2022/download/index.html'),
                       ('gallery', 'courses/12-001-introduction-to-geology-fall-2013/pages/field-trip/index.html'),
                       ('pdf', 'courses/5-60-thermodynamics-kinetics-spring-2008/resources/lec_12/index.html'),
                       ('menus', 'courses/6-033-computer-system-engineering-spring-2018/resources/unique-aspects-of-the-course/index.html'),
                       ('nist', 'courses/nist-sematech-statistical-handbook/handbook/eda/section3/eda352.htm')):
        t0, n = time.time(), len(hits)
        frame_with(r, '/' + path)
        time.sleep(2)
        got = r.js(f"const t=await (await fetch({json.dumps('/' + path)})).text();return {{bytes:t.length,style:t.includes('lb-')||t.includes('.collapse'),transcript:(t.match(/lb-transcript\" open/g)||[]).length,figures:(t.match(/<figure style=/g)||[]).length}}")
        r.shot(f'page-{name}.png')
        rows = r.log('bridge', t0)
        r.rec('page_' + name, {**(got or {}), 'requests': len(rows), 'not_ok': [(x.get('t', '')[-50:], x.get('status')) for x in rows if (x.get('status') or 0) >= 400][:8], 'decoy': hits[n:]})
    frame_with(r, '/courses/5-60-thermodynamics-kinetics-spring-2008/resources/lecture-30-introduction-to-reaction-kinetics/index.html')
    time.sleep(1)
    r.cmd('click', x=70, y=203)     # the Menu button, now a plain link, at this frame's narrow width
    time.sleep(1)
    r.shot('page-drawer-open.png')
    big = PAGES / 'big.html'        # the largest saved page in the real library, when copied here by hand
    biggest = big if big.exists() else sorted(Path(DATA / 'library-data').glob('courses/*/**/*.html'), key=lambda p: p.stat().st_size)[-1]
    rel = '/' + str(biggest.relative_to(DATA / 'library-data'))
    r.rec('largest_page_timer_gap', {'path': rel, 'bytes': biggest.stat().st_size, **(r.js(f"let g=0,l=performance.now();const iv=setInterval(()=>{{const n=performance.now();g=Math.max(g,n-l);l=n}},16);document.querySelectorAll('.__tf').forEach(x=>x.remove());const f=document.createElement('iframe');f.className='__tf';f.src={json.dumps(rel)};let done=null;const t0=performance.now();f.onload=()=>{{done=Math.round(performance.now()-t0)}};document.body.append(f);await until(()=>done!==null,90000);await sleep(4000);clearInterval(iv);f.remove();return {{gap_ms:Math.round(g),load_ms:done}}",timeout=120) or {})})
    r.rec('page_kills', [l.strip() for l in open(r.out / 'stdout.txt', errors='replace') if 'ending the page' in l])


section, name = sys.argv[1], sys.argv[2]
names = write_pages()
threading.Thread(target=decoy, daemon=True).start()
ARGS = {'product': [], 'rules-alone': ['--features-as-before', '--allow-frames'], 'no-layers': ['--features-as-before', '--allow-frames', '--no-rule-list'],
        'js-layer': ['--no-csp'], 'js-control': ['--no-csp', '--frame-scripts'], 'frame-hole': ['--old-frame-rule', '--frame-scripts'], 'after-hole': ['--old-frame-rule'], 'bad-rules': ['--bad-rules'], 'pages': []}[section]
r = Run(name, '--stub-chat', *ARGS)
try:
    if section == 'bad-rules':
        time.sleep(6)
        r.rec('refused', r.log('asks'))
        r.rec('state', {k: v for k, v in r.cmd('state').items() if k in ('url', 'title')})
        r.rec('requests', len(r.log('bridge')))
    else:
        r.rec('up', r.wait_up(40))
        if section in ('rules-alone', 'no-layers', 'product'):
            n = len(hits)
            r.rec('top_probe', top_probe(r))
            time.sleep(2)
            r.rec('top_probe_decoy_hits', sorted(hits[n:]))
        if section in ('product', 'js-layer', 'js-control', 'no-layers', 'rules-alone'):
            attack(r)
        if section in ('product', 'frame-hole', 'after-hole'):
            clicks(r, names)
        if section == 'product':
            ui(r)
        if section == 'pages':
            pages(r)
        r.rec('all_decoy_hits', len(hits))
        r.rec('outside_at_end', {k: v for k, v in r.outside().items() if k in ('listen', 'inet', 'model_files', 'real_library_files')})
        rows = r.log('mem')
        r.rec('focus_all_samples', {'samples': len(rows), 'active': sum(1 for x in rows if x.get('active')), 'key': sum(1 for x in rows if x.get('key'))})
finally:
    r.stop()
