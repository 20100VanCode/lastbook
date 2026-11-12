"""Reads an ETW trace turned to XML: who sent what where. python3 net_read.py trace.xml procs-now.csv known_pid[,known_pid] control_pid"""
import csv, collections, sys
import xml.etree.ElementTree as ET
path, procs_csv, known, ctl = sys.argv[1], sys.argv[2], {int(x) for x in sys.argv[3].split(',')}, int(sys.argv[4])
names = {int(r['Id']): r['ProcessName'] for r in csv.DictReader(open(procs_csv, encoding='utf-8-sig'))}
NS = '{http://schemas.microsoft.com/win/2004/08/events/event}'
per = collections.defaultdict(collections.Counter); dns = collections.defaultdict(collections.Counter); tot = collections.Counter(); first = None; last = None
for ev, el in ET.iterparse(path, events=('end',)):
    if el.tag != NS + 'Event': continue
    s = el.find(NS + 'System'); prov = s.find(NS + 'Provider').get('Name'); eid = int(s.find(NS + 'EventID').text)
    ex = s.find(NS + 'Execution'); xpid = int(ex.get('ProcessID')) if ex is not None and ex.get('ProcessID') else -1
    d = {x.get('Name'): (x.text or '').strip() for x in el.iter(NS + 'Data')}
    t = s.find(NS + 'TimeCreated').get('SystemTime'); first = first or t; last = t
    tot[prov] += 1
    if 'Kernel-Network' in (prov or ''):
        pid = int(d.get('PID') or xpid); per[pid][(eid, d.get('daddr'), d.get('dport'))] += 1
    elif 'DNS' in (prov or ''):
        q = d.get('QueryName')
        if q: dns[xpid][q] += 1
    el.clear()
print('trace', first, 'to', last, dict(tot))
def show(pid):
    print(' ', pid, names.get(pid, '(gone now)'), 'events', sum(per[pid].values()), per[pid].most_common(8), 'dns', dns[pid].most_common(5))
print('Known app processes:'); [show(p) for p in sorted(known)]
print('Control:'); show(ctl)
print('Every process in the trace that has since gone, and is not the control or known:')
for p in sorted(per):
    if p not in names and p not in known and p != ctl: show(p)
print('Other processes (still running): ', collections.Counter(names[p] for p in per if p in names))
print('Any webview process still running with traffic:', [p for p in per if names.get(p, '').lower().startswith('msedgewebview2') or names.get(p, '').lower().startswith('lastbook')])
