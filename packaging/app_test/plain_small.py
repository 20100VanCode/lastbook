# No DevTools in this run: real mouse and keyboard only, by screen position; shots are the record. Positions are shot pixels, one third of screen pixels.
import time
def C(x, y, wait=2.5, **k):
    r = agent('click', x=x * 3, y=y * 3, **k); time.sleep(wait); return r.get('clicked')
def S(n): agent('screen', name=n, scale=3)
def T(t): agent('type', text=t, secs=60)
def K(*k): agent('keys', keys=list(k))
TOP = {'home': (261, 69), 'ask': (352, 69), 'videos': (458, 69), 'map': (568, 69), 'library': (680, 69), 'search': (980, 69)}
print(C(*TOP['ask'])); S('p-ask'); print(C(800, 584, 0.4)); T('how do I make water safe to drink'); K('enter'); time.sleep(8); S('p-ask-sent')
print(C(*TOP['videos'], 3)); S('p-videos')
print(C(*TOP['map'], 8)); S('p-map'); agent('scroll', x=300, y=1500, d=120); time.sleep(0.7); agent('scroll', x=300, y=1500, d=120); time.sleep(4); S('p-map-zoom')
print(C(*TOP['library'], 3)); S('p-library')
print(C(*TOP['search'], 0.4)); T('wildfires'); K('enter'); time.sleep(4); S('p-search-wildfires')
print(C(*TOP['search'], 0.4)); K('ctrl', 'a'); T('boil water'); K('enter'); time.sleep(4); S('p-search-boil')
print(C(100, 400, 4)); S('p-pdf-from-search')
print(C(*TOP['home'], 3)); S('p-home')
print('end')
