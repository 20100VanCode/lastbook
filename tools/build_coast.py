#!/usr/bin/env python3
"""Add an ocean polygon to the offline map. The Geofabrik "free" GeoPackage has no coastline, so this reads
natural=coastline ways from the SoCal .osm.pbf (read only) with pyosmium, joins them into chains, and closes
the open mainland chain out to sea. Islands are stored as land rings drawn on top of the ocean.

  derived/buildenv/bin/python tools/build_coast.py library-data/geography/openstreetmap/socal-latest.osm.pbf derived/geo/map.sqlite
"""
import sqlite3, sys
import osmium

PBF, DST = sys.argv[1], sys.argv[2]


class Coast(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []

    def way(self, w):
        if w.tags.get('natural') == 'coastline':
            try:
                self.ways.append(([n.ref for n in w.nodes], [(n.lon, n.lat) for n in w.nodes]))
            except osmium.InvalidLocationError:
                pass


def chains(ways):
    by_start = {}
    for refs, pts in ways:
        by_start.setdefault(refs[0], []).append((refs, pts))
    used = set()
    out = []
    for refs, pts in ways:
        if id(pts) in used:
            continue
        used.add(id(pts))
        r, p = list(refs), list(pts)
        while r[-1] != r[0]:
            nxt = [w for w in by_start.get(r[-1], []) if id(w[1]) not in used]
            if not nxt:
                break
            used.add(id(nxt[0][1]))
            r += nxt[0][0][1:]
            p += nxt[0][1][1:]
        out.append((r[0] == r[-1], p))
    # join open chains whose start is another chain's end (pieces processed out of order)
    merged = True
    while merged:
        merged = False
        opens = [c for c in out if not c[0]]
        for a in opens:
            for b in opens:
                if a is not b and a[1][-1] == b[1][0]:
                    out.remove(a); out.remove(b)
                    out.append((a[1][0] == b[1][-1], a[1] + b[1][1:]))
                    merged = True
                    break
            if merged:
                break
    return out


def pack(parts):
    from array import array
    a = array('i', [len(parts)])
    for p in parts:
        a.append(len(p))
        lx = ly = 0
        for x, y in p:
            x, y = int(round(x * 1e6)), int(round(y * 1e6))
            a.append(x - lx); a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


h = Coast()
h.apply_file(PBF, locations=True, idx='flex_mem')
cs = chains(h.ways)
closed = [p for c, p in cs if c]
opened = sorted([p for c, p in cs if not c], key=len, reverse=True)
print('coast ways', len(h.ways), 'closed rings', len(closed), 'open chains', [len(p) for p in opened[:5]])
db = sqlite3.connect(DST)
db.execute("DELETE FROM feat_idx WHERE id IN (SELECT id FROM feat WHERE layer IN ('ocean','island'))")
db.execute("DELETE FROM feat WHERE layer IN ('ocean','island')")
nid = db.execute('SELECT max(id) FROM feat').fetchone()[0] + 1
W = -125.0  # well out to sea
rings = []
for p in opened:
    # land is on the left of coastline direction; close each open chain through the sea to the west.
    rings.append(p + [(W, p[-1][1]), (W, p[0][1]), p[0]])
for ring in rings:
    xs = [x for x, _ in ring]; ys = [y for _, y in ring]
    db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (nid, 'ocean', 'ocean', None, 0, pack([ring])))
    db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (nid, min(xs), max(xs), min(ys), max(ys), 0, 30))
    nid += 1
for ring in closed:
    xs = [x for x, _ in ring]; ys = [y for _, y in ring]
    # OSM closed coastline rings around land run counter-clockwise; water "holes" (lakes on islands) are rare here.
    db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (nid, 'island', 'island', None, 0, pack([ring])))
    db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (nid, min(xs), max(xs), min(ys), max(ys), 0, 30))
    nid += 1
db.commit()
print('stored', len(rings), 'ocean rings', len(closed), 'islands')
