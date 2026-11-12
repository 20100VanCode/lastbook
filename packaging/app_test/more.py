# Second pass: things the first pass could not settle. Works around another program's window sitting over the middle of the screen.
PK = json.load(open(os.environ['PK_CFG'], encoding='utf-8'))
V = "(()=>{const v=document.querySelector('video');return {t:v.currentTime,paused:v.paused,ready:v.readyState,dur:v.duration}})()"
E(f"location.hash='#/watch/{PK['video']}'"); time.sleep(3); settle()
E("scrollTo(0,0)"); time.sleep(0.4)
r = E("(()=>{const r=document.querySelector('video').getBoundingClientRect();return [r.left,r.top,r.width,r.height,innerHeight]})()"); rec('video-rect', r=r)
click('video', wait=2); rec('v-playing', v=E(V))   # first click starts it
bar_y = r[1] + r[3] - 16
if bar_y > r[4] - 6:   # the bar is below the window: scroll so it shows
    E(f"scrollBy(0,{bar_y - r[4] + 60})"); time.sleep(0.5); r = E("(()=>{const r=document.querySelector('video').getBoundingClientRect();return [r.left,r.top,r.width,r.height,innerHeight]})()"); bar_y = r[1] + r[3] - 16
rec('video-rect2', r=r, bar_y=bar_y)
# move there first so the bar appears; then click three places along it
for f in (0.8, 0.5, 0.25):
    sx, sy = scr(r[0] + r[2] * f, bar_y); a = agent('click', x=sx, y=sy); time.sleep(1.2); rec('v-seek-click', frac=f, click=a.get('clicked'), v=E(V))
agent('screen', name='video-after-seek', scale=3)
key('right'); time.sleep(0.6); a = E(V); key('right'); time.sleep(0.6); b = E(V); rec('v-seek-keys', a=a, b=b, active=E("document.activeElement.tagName"))
rec('v-seek-video-frame', w=E("document.querySelector('video').videoWidth"))
click('video', wait=0.6); rec('v-pause', v=E(V))
# About: why status text
E("location.hash='#/about'"); time.sleep(1)
rec('about-apis', r=E("""Promise.all(['/api/library','/api/download-status','/api/assistant/status'].map(u=>fetch(u).then(async r=>[u,r.status,(await r.text()).slice(0,160)]).catch(e=>[u,String(e)])))"""))
time.sleep(6); rec('about-later', cards=E("[...document.querySelectorAll('#main .card')].map(c=>c.innerText.slice(0,230))"))
E("location.hash='#/'"); time.sleep(0.5); E("location.hash='#/about'"); time.sleep(4); rec('about-second', cards=E("[...document.querySelectorAll('#main .card')].map(c=>c.innerText.slice(0,230))")); shot('about-second')
# Sources: open a details by real click
E("location.hash='#/read/lastbook-sources'"); time.sleep(3)
E("scrollTo(0,0)"); time.sleep(0.3)
rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
d = feval("""(()=>{const s=document.querySelectorAll('details summary')[1];s.scrollIntoView({block:'nearest'});const r=s.getBoundingClientRect();return {x:r.left+20,y:r.top+r.height/2}})()""")
time.sleep(0.5); rect = E("(()=>{const r=document.querySelector('#main iframe').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
a = clickxy(rect[0] + d['x'], rect[1] + d['y']); time.sleep(1.5); rec('sources-details', click=a.get('clicked'), where=d, rect=rect, open=feval("document.querySelectorAll('details')[1].open"), inner=feval("document.querySelectorAll('details')[1].innerText.slice(0,300)")); shot('sources-details')
# Shelf "other": how a person would reach Sources
E("location.hash='#/shelf/other'"); time.sleep(2); rec('shelf-other', text=E("document.querySelector('#main').innerText.slice(0,400)"))
# Map: wheel and drag, on the free part left of the other program's window
r = click('.tabs-top a', 'Map', wait=5); E("scrollTo(0,0)"); time.sleep(0.5)
m = E("(()=>{const r=document.querySelector('#mapc').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()"); rec('map-rect', m=m, hash=E('location.hash'))
sx, sy = scr(m[0] + 120, m[1] + 300 if m[1] + 300 < 520 else 500)
agent('scroll', x=sx, y=sy, d=-120); time.sleep(0.7); agent('scroll', x=sx, y=sy, d=-120); time.sleep(3); rec('map-wheel-out', hash=E('location.hash'))
agent('scroll', x=sx, y=sy, d=120); time.sleep(0.7); agent('scroll', x=sx, y=sy, d=120); time.sleep(0.7); agent('scroll', x=sx, y=sy, d=120); time.sleep(4); rec('map-wheel-in', hash=E('location.hash')); agent('screen', name='map-wheel-in', scale=3)
for z, nm in ((6, 'z6'), (10, 'z10'), (15, 'z15')):
    E(f"location.hash='#/map?lat=39.0997&lon=-94.5786&z={z}'"); time.sleep(5); agent('screen', name='map-' + nm, scale=3)
print('more done', flush=True)
