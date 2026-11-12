# A person's walk through one pack, with real mouse and keyboard. DevTools only finds positions and reads what happened.
PK = json.loads(os.environ.get('PK', '{}')) if False else json.load(open(os.environ['PK_CFG'], encoding='utf-8'))
ONLY = set(filter(None, os.environ.get('PK_ONLY', '').split(',')))
def want(n): return not ONLY or n in ONLY
def hits():
    return E("""(()=>{const m=document.querySelector('#main');const a=[...m.querySelectorAll('a[href]')].map(x=>x.getAttribute('href'));const c=k=>a.filter(h=>h.startsWith(k)).length;return {read:c('#/read/'),watch:c('#/watch/'),wiki:c('#/wiki/'),guide:c('#/t/'),ask:c('#/ask'),heads:[...m.querySelectorAll('h2,h3')].map(h=>h.innerText).slice(0,12),empty:[...m.querySelectorAll('.empty')].map(e=>e.innerText.slice(0,200)),text:m.innerText.slice(0,500)}})()""")
def search(q, name, wait=4):
    r1 = click('#topQ', wait=0.2); key('ctrl', 'a'); typ(q); key('enter'); time.sleep(wait); settle(1500)
    h = hits(); rec(name, q=q, click=r1.get('clicked'), hash=E('location.hash'), **h); shot(name); return h

if want('nav'):
    E("location.hash='#/'"); time.sleep(1)
    for n in ['Ask', 'Videos', 'Map', 'Library', 'Home']:
        r = click('.tabs-top a', n, wait=2.5); s = state(); rec('nav-' + n, clicked=r.get('clicked'), hash=s['hash'], h1=s['h1'], len=s['len'], errs=s['errs']); shot('nav-' + n)
    r = click('.foot a', 'About', wait=2); rec('foot-about', clicked=r.get('clicked'), **state())

if want('search'):
    h = search(PK['search_good'], 'search-good')
    r = click('#main #sres a[href^="#/read/"], #main #spass a[href^="#/read/"], #main a.rcard', wait=4); s = state(); rec('search-good-open', clicked=r.get('clicked'), el=r.get('el'), href=r.get('href'), h1=s['h1'], hash=s['hash'], errs=s['errs']); shot('search-good-open')
    r = click('#main .rtop a', wait=2.5); rec('search-back-button', el=r.get('el'), hash=E('location.hash'), h1=state()['h1'])
    search(PK['search_nonsense'], 'search-nonsense')
    for i, q in enumerate(PK['search_larger']): search(q, f'search-larger-{i}')
    for i, q in enumerate(PK.get('search_owner', [])): search(q, f'search-owner-{i}')

if want('pdf'):
    i = PK['pdf']; E(f"location.hash='#/read/{i}'"); time.sleep(3); settle(); s = state(); rec('pdf-open', **s); shot('pdf-page')
    im = lambda: E("(()=>{const i=document.querySelector('img.pageimg');return i?{src:i.getAttribute('src'),w:i.naturalWidth,done:i.complete}:null})()")
    rec('pdf-page-img', img=im())
    r = click('.rbar a.nav', 'Next', wait=2.5); rec('pdf-next', clicked=r.get('clicked'), hash=E('location.hash'), img=im())
    click('#pg', wait=0.2); key('ctrl', 'a'); typ('12'); key('enter'); time.sleep(2.5); rec('pdf-goto-12', hash=E('location.hash'), img=im()); shot('pdf-page12')
    key('tab'); E("document.querySelector('#main').focus()"); key('right'); time.sleep(2); rec('pdf-arrow-right', hash=E('location.hash'))
    r = click('[data-view=text]', wait=2.5); t = E("(document.querySelector('.pagetext')||{}).innerText||''"); rec('pdf-text', clicked=r.get('clicked'), hash=E('location.hash'), chars=len(t), start=t[:120]); shot('pdf-text')
    r = click('[data-view=pdf]', wait=7); rec('pdf-whole', clicked=r.get('clicked'), hash=E('location.hash'), frame=E("(document.querySelector('iframe.frame')||{}).src"), targets=[x['type'] for x in targets()]); print(agent('screen', name='pdf-whole', scale=3).get('path'))
    # "Open the original file" under About this source
    click('details.about-src summary', wait=0.8); r = click('details.about-src a.btn', wait=3); rec('pdf-open-original', clicked=r.get('clicked'), href=r.get('href'), hash=E('location.hash'), allwin=[w['title'] for w in agent('allwin')['windows']], downloads=agent('summary').get('downloads_new')); print(agent('screen', name='pdf-open-original', scale=3).get('path'))

if want('saved'):
    for n, i in PK['saved'].items():
        E(f"location.hash='#/read/{i}'"); time.sleep(3); settle(); s = state(); fi = frame_info(); rec('saved-' + n, h1=s['h1'], errs=s['errs'], frame=fi); shot('saved-' + n)
        u = E("document.querySelector('#main iframe').getAttribute('src')")
        rec('saved-bytes-' + n, u=u, r=E(f"fetch({json.dumps(u)}).then(async r=>{{const b=await r.text();return {{status:r.status,bytes:b.length,script:(b.match(/<script\\b/ig)||[]).length,on:(b.match(/<[a-z][^>]*\\son[a-z]+\\s*=/ig)||[]).length,csp:r.headers.get('content-security-policy')}}}})"))
        ifr = where('#main iframe'); rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        lk = feval("""(()=>{const a=[...document.links].filter(l=>l.getClientRects().length);const pick=[];for(const l of a){const r=l.getBoundingClientRect();if(r.top>0&&r.bottom<innerHeight){pick.push({t:l.innerText.slice(0,40),href:l.getAttribute('href'),x:r.left+r.width/2,y:r.top+r.height/2})}if(pick.length>=3)break}return pick})()""")
        for j, l in enumerate(lk if isinstance(lk, list) else []):
            before = feval('location.pathname'); r = clickxy(rect[0] + l['x'], rect[1] + l['y']); time.sleep(2.5)
            rec(f'saved-link-{n}-{j}', link=l, before=before, after=feval('location.pathname+" | "+document.title+" | "+(document.body?document.body.innerText.slice(0,80):"")'), hash=E('location.hash'), allwin=[w['title'] for w in agent('allwin')['windows']]); shot(f'saved-link-{n}-{j}')
            E(f"location.hash='#/'"); time.sleep(0.8); E(f"location.hash='#/read/{i}'"); time.sleep(3.5)
            break
        r = click('[data-view=text]', wait=2.5); t = E("(document.querySelector('.pagetext')||{}).innerText||''"); rec('saved-text-' + n, clicked=r.get('clicked'), chars=len(t), start=t[:100]); shot('saved-text-' + n)

if want('course') and PK.get('course'):
    for n, i in PK['course'].items():
        E(f"location.hash='#/read/{i}'"); time.sleep(3); settle(); s = state(); fi = frame_info(); rec('course-' + n, h1=s['h1'], errs=s['errs'], frame=fi); shot('course-' + n)
        rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        lk = feval("""(()=>{const a=[...document.links].filter(l=>l.getClientRects().length);const out=[];for(const l of a){const h=l.getAttribute('href')||'';if(/^https?:|^#|^mailto/.test(h))continue;const r=l.getBoundingClientRect();if(r.top>0&&r.bottom<innerHeight-10&&r.width>4)out.push({t:l.innerText.slice(0,50),href:h,x:r.left+r.width/2,y:r.top+r.height/2})}return out.slice(0,6)})()""")
        rec('course-links-' + n, links=lk)
        if isinstance(lk, list) and lk:
            l = lk[-1]; r = clickxy(rect[0] + l['x'], rect[1] + l['y']); time.sleep(3); rec(f'course-click-{n}', link=l, after=frame_info(), hash=E('location.hash')); shot(f'course-click-{n}')

if want('video') and PK.get('video'):
    i = PK['video']; E(f"location.hash='#/watch/{i}'"); time.sleep(3); settle()
    V = "(()=>{const v=document.querySelector('video');return {t:v.currentTime,paused:v.paused,ready:v.readyState,dur:v.duration,w:v.videoWidth,h:v.videoHeight,err:v.error&&v.error.message,muted:v.muted,vol:v.volume}})()"
    s = state(); rec('video-open', h1=s['h1'], errs=s['errs'], v=E(V), owner=E("(document.querySelector('.vmeta b')||{}).innerText")); shot('video-open')
    click('video', wait=5); a = E(V); time.sleep(2); b = E(V); rec('video-play', a=a, b=b); agent('screen', name='video-playing', scale=3)
    # native timeline: near the bottom of the video element
    r = E("(()=>{const r=document.querySelector('video').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    agent('click', x=scr(r[0] + r[2] * 0.6, r[1] + r[3] - 28)[0], y=scr(r[0] + r[2] * 0.6, r[1] + r[3] - 28)[1]); time.sleep(3); c1 = E(V); rec('video-seek-timeline', after=c1)
    key('right'); time.sleep(1.5); rec('video-seek-key', after=E(V))
    n = where('.cue'); 
    if n: click('.cue', nth=min(3, n['n'] - 1), wait=2); rec('video-cue', after=E(V), cues=n['n'])
    agent('screen', name='video-seeked', scale=3)
    click('video', wait=1); rec('video-pause', after=E(V))
    E("location.hash='#/'"); time.sleep(1)

if want('wiki'):
    E("location.hash='#/library'"); time.sleep(2)
    for name in PK['zim_cards_have'] + PK.get('zim_cards_missing', []):
        E("location.hash='#/library'"); time.sleep(1.5)
        r = click('#main a.card', name, wait=4); s = state(); fi = frame_info(); rec('zim-card-' + name, clicked=r.get('clicked'), h1=s['h1'], hash=s['hash'], frame=fi, errs=s['errs']); shot('zim-card-' + name.replace(' ', '_'))
    E("location.hash='#/encyclopedias'"); time.sleep(2)
    r = click('#zq', wait=0.2); typ(PK['zim_query']); key('enter'); time.sleep(4); s = state(); rec('zim-search', hash=s['hash'], text=s['text'], hits=E("[...document.querySelectorAll('#main a.row')].slice(0,6).map(a=>[a.getAttribute('href'),a.innerText.slice(0,70)])")); shot('zim-search')
    r = click('#main a.row', wait=4); s = state(); fi = frame_info(); rec('zim-article', el=r.get('el'), h1=s['h1'], hash=s['hash'], frame=fi); shot('zim-article')
    rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    lk = feval("""(()=>{for(const l of document.links){const h=l.getAttribute('href')||'';if(/^https?:|^#|^\\/\\//.test(h)||!l.innerText.trim())continue;const r=l.getBoundingClientRect();if(r.top>40&&r.bottom<innerHeight-10)return {t:l.innerText.slice(0,40),href:h,x:r.left+r.width/2,y:r.top+r.height/2}}return null})()""")
    if isinstance(lk, dict) and 'x' in lk: clickxy(rect[0] + lk['x'], rect[1] + lk['y']); time.sleep(4); s = state(); rec('zim-inner-link', link=lk, h1=s['h1'], hash=s['hash'], frame=frame_info()); shot('zim-inner-link')
    r = click('#wopen', wait=2.5); rec('zim-own-tab', clicked=r.get('clicked'), hash=E('location.hash'), allwin=[w['title'] for w in agent('allwin')['windows']])
    lk = feval("""(()=>{for(const l of document.links){const h=l.getAttribute('href')||'';if(!/^https?:/.test(h))continue;const r=l.getBoundingClientRect();if(r.top>40&&r.bottom<innerHeight-10)return {t:l.innerText.slice(0,40),href:h,x:r.left+r.width/2,y:r.top+r.height/2}}return null})()""")
    if isinstance(lk, dict) and 'x' in lk: clickxy(rect[0] + lk['x'], rect[1] + lk['y']); time.sleep(3); rec('zim-web-link', link=lk, hash=E('location.hash'), frame=feval('location.pathname'), allwin=[w['title'] for w in agent('allwin')['windows']])

if want('map'):
    r = click('.tabs-top a', 'Map', wait=8); s = state(); rec('map-open', clicked=r.get('clicked'), status=E("(document.querySelector('#mstatus')||{}).innerText"), data=E("(document.querySelector('#mdata')||{}).innerText"), text=s['text']); shot('map-open'); agent('screen', name='map-open-screen', scale=3)
    for j, q in enumerate(PK['map_q']):
        r = click('#pq', wait=0.2); key('ctrl', 'a'); typ(q); key('enter'); time.sleep(3.5)
        res = E("[...document.querySelectorAll('#pres button,#pres a,#pres li')].slice(0,6).map(a=>a.innerText.slice(0,80))"); rec(f'map-q{j}', q=q, res=res, api=E(f"fetch('/api/places?q='+encodeURIComponent({json.dumps(q)})).then(r=>r.json()).then(d=>JSON.stringify(d).slice(0,400))")); shot(f'map-q{j}-list')
        r = click('#pres button,#pres a,#pres li', wait=7); rec(f'map-q{j}-open', el=r.get('el'), clicked=r.get('clicked'), hash=E('location.hash'), status=E("(document.querySelector('#mstatus')||{}).innerText"), data=E("(document.querySelector('#mdata')||{}).innerText")); agent('screen', name=f'map-q{j}-result', scale=3)
    p = where('#mapc') or where('canvas')
    if p:
        click('#zin', wait=3); click('#zin', wait=3); click('#zin', wait=4); agent('screen', name='map-zoomed', scale=3); rec('map-zoom', hash=E('location.hash'))
    click('#near', wait=3); rec('map-near', text=E("(document.querySelector('#card')||{}).innerText||''"))
    rec('map-tile-check', r=E("""(async()=>{const a=await fetch('/api/map/info').then(r=>r.json());return JSON.stringify(a).slice(0,500)})()"""))

if want('ask'):
    r = click('.tabs-top a', 'Ask', wait=3); s = state(); rec('ask-open', clicked=r.get('clicked'), text=s['text'], status=E("fetch('/api/assistant/status').then(r=>r.json()).then(d=>JSON.stringify(d).slice(0,500))")); shot('ask-open')
    r = click('#chatIn', wait=0.3); typ(PK['ask']); key('enter'); time.sleep(10); rec('ask-sent', clicked=r.get('clicked'), text=E("document.querySelector('#main').innerText.slice(0,1400)"), errs=state()['errs']); shot('ask-sent')

if want('about'):
    E("location.hash='#/about'"); time.sleep(3); txt = E("document.querySelector('#main').innerText"); rec('about', text=txt); shot('about')
    for name in ['Gap closure report', 'Learning pathways report', 'Supplies planning']:
        r = click('#main a', name, wait=3); rec('about-link-' + name, clicked=r.get('clicked'), href=r.get('href'), hash=E('location.hash'), allwin=[w['title'] for w in agent('allwin')['windows']]); shot('about-link-' + name.replace(' ', '_'))
    links = E("[...document.querySelectorAll('#main a')].map(a=>[a.innerText.slice(0,50),a.getAttribute('href')])"); rec('about-links', links=links)
    i = 'lastbook-sources'
    search('sources and permissions', 'search-sources', wait=3)
    E(f"location.hash='#/read/{i}'"); time.sleep(3); settle(); s = state(); fi = frame_info(); rec('sources-open', h1=s['h1'], errs=s['errs'], frame=fi); shot('sources-open')
    full = feval("document.body.innerText"); open(L + r'\sources-text.txt', 'w', encoding='utf-8').write(full if isinstance(full, str) else str(full))
    pubs = E("fetch('/api/library').then(r=>r.json()).then(d=>JSON.stringify(d).slice(0,500))"); rec('library-numbers', pubs=pubs)
    rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    d = feval("""(()=>{const s=document.querySelector('details summary');s.scrollIntoView({block:'center'});const r=s.getBoundingClientRect();return {x:r.left+20,y:r.top+r.height/2}})()"""); clickxy(rect[0] + d['x'], rect[1] + d['y']); time.sleep(1.5); rec('sources-details', open=feval("document.querySelector('details').open"), inner=feval("document.querySelector('details').innerText.slice(0,240)")); shot('sources-details')

if want('save'):
    i = PK['pdf']; E(f"location.hash='#/read/{i}'"); time.sleep(3)
    r = click('#main .rtop button', 'Save', wait=1); E("location.hash='#/saved'"); time.sleep(1.5); rec('save', clicked=r.get('clicked'), saved=E("[...document.querySelectorAll('#main .collection')].map(c=>c.innerText.slice(0,160))")); shot('saved-list')
print('use done', flush=True)
