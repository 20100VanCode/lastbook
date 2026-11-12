# Helpers for steps run inside vw.py py. Real clicks and keys go through the session agent; DevTools only observes and finds where things are.
import json, os, re, time, collections
L = rf'{LOGS}\{run_dir()}'
c = top()
c.call('Page.enable'); c.call('Runtime.enable')
OUT = open(L + r'\use.jsonl', 'a', encoding='utf-8', buffering=1)
def rec(name, **k):
    OUT.write(json.dumps({'step': name, 'ts': round(time.time(), 1), **k}, ensure_ascii=False) + '\n'); print(name, json.dumps(k, ensure_ascii=False)[:1500], flush=True)
def E(x, secs=60):
    return c.eval(x, secs)
def state():
    return E("""(()=>{const m=document.querySelector('#main');return {hash:location.hash,title:document.title,h1:(m.querySelector('h1')||{}).innerText||'',len:m.innerText.length,errs:[...m.querySelectorAll('.err')].map(e=>e.innerText.slice(0,240)),empty:[...m.querySelectorAll('.empty')].map(e=>e.innerText.slice(0,240)),text:m.innerText.slice(0,260)}})()""")
def where(sel, text=None, nth=0):
    """Scroll the element into view; centre in CSS px, or None."""
    js = """((sel,text,nth)=>{let a=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length);if(text)a=a.filter(e=>(e.innerText||e.value||'').toLowerCase().includes(text.toLowerCase()));const e=a[nth];if(!e)return null;e.scrollIntoView({block:'center',inline:'nearest'});let r=e.getBoundingClientRect();if(!e.closest('header')&&r.top+r.height/2<420&&r.height<100){scrollBy(0,r.top+r.height/2-440);r=e.getBoundingClientRect()}return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,h:r.height,tag:e.tagName,txt:(e.innerText||'').slice(0,80),href:e.getAttribute('href'),n:a.length}})"""
    return E(js + f'({json.dumps(sel)},{json.dumps(text)},{nth})')
def scr(x, y):
    w = agent('windows')['windows'][0]; d = E('devicePixelRatio'); return int(w['origin'][0] + x * d), int(w['origin'][1] + y * d)
def clickxy(x, y, **k):
    sx, sy = scr(x, y); return agent('click', x=sx, y=sy, **k)
def click(sel, text=None, nth=0, wait=1.2, **k):
    p = where(sel, text, nth)
    if not p: return {'clicked': False, 'why': 'not found', 'sel': sel, 'text': text}
    time.sleep(0.25); p = where(sel, text, nth)
    for f in (0, -0.4, 0.4, -0.25, 0.25):     # another program's window may sit over part of this one: the agent refuses a click that would land on it
        r = clickxy(p['x'] + f * p['w'], p['y'], **k)
        if r.get('clicked'): break
    time.sleep(wait); r['el'] = p.get('txt') or p.get('tag'); r['href'] = p.get('href'); return r
def typ(t): return agent('type', text=t, secs=60)
def key(*k): return agent('keys', keys=list(k))
SHOTS = []
def shot(n, scale=3):
    r = agent('shot', name=n, scale=scale); return r.get('path')
def settle(ms=800):
    time.sleep(ms / 1000)
    E("""(async()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));const t=performance.now();while(document.querySelector('#main .loading')&&performance.now()-t<20000)await s(80)})()""")
def go(h, wait=1.5):
    E(f'location.hash={json.dumps(h)}'); settle(); time.sleep(wait); return state()
def frames():
    return [x for x in targets() if x['type'] == 'iframe']
def feval(expr, frame=None):
    """Evaluate inside the page's own frame. Sandboxed frames run in their own process, so each is its own DevTools target. Timers do not run there, so nothing may wait."""
    fs = []
    for _ in range(15):
        fs = frames()
        if fs: break
        time.sleep(0.2)
    if not fs:     # a same-process frame (encyclopedia articles)
        return E("(()=>{const f=document.querySelector('#main iframe');if(!f||!f.contentDocument)return {noframe:true};const win=f.contentWindow;return (function(document,location,innerHeight){return " + expr + "})(f.contentDocument,win.location,win.innerHeight)})()", 20)
    f = frame or fs[-1]
    k = CDP(f['webSocketDebuggerUrl'])
    try:
        k.call('Runtime.enable', secs=10)
        r = k.call('Runtime.evaluate', {'expression': expr, 'returnByValue': True}, secs=15)
    except Exception as e:
        return {'fail': repr(e)[:200]}
    finally:
        k.s.close()
    if 'exceptionDetails' in r: return {'exc': str(r['exceptionDetails'])[:300]}
    return r['result'].get('value')
FRAME_ONE = """(()=>{const im=[...document.images];im.forEach(i=>{try{i.loading='eager'}catch{}});
return {ready:document.readyState,url:location.pathname,title:document.title,words:(document.body?document.body.innerText:'').split(/\\s+/).filter(Boolean).length,imgs:im.length,pending:im.filter(i=>i.getAttribute('src')&&!i.complete).length,broken:im.filter(i=>i.getAttribute('src')&&i.complete&&!i.naturalWidth).map(i=>i.getAttribute('src')).slice(0,12),noSrc:im.filter(i=>!i.getAttribute('src')&&!i.getAttribute('srcset')).length,scripts:document.scripts.length,links:document.links.length,h:document.documentElement.scrollHeight,sheets:document.styleSheets.length,textStart:(document.body?document.body.innerText:'').slice(0,200)}})()"""
class _F(str): pass
def frame_info():
    r = None
    for _ in range(25):
        r = feval(FRAME_ONE)
        if not isinstance(r, dict) or 'ready' not in r or (r['ready'] == 'complete' and not r['pending']): break
        time.sleep(0.3)
    return r
