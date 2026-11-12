"""Writes size, mtime and ctime of every file in the real library, for a before and after comparison. Only stats files, never opens one. Sign-in and cookie files are skipped by name, not even statted. Not in any pack.

  python -I -B library_listing.py list <out.tsv>
  python -I -B library_listing.py compare <before.tsv> <after.tsv> <out.tsv> [<audit log> ...]
"""
import fnmatch
import os
import sys
from collections import Counter
from pathlib import Path

ROOTS = {'library-data': os.path.realpath('/path/to/lastbook/library-data'), 'derived/geo': '/path/to/lastbook/derived/geo'}
NEVER = ('video-auth*', '*cookie*')


def walk(root, follow=True):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            it = list(os.scandir(d))
        except OSError:
            continue
        for e in it:
            low = e.name.lower()
            if any(fnmatch.fnmatchcase(low, p) for p in NEVER):
                continue
            try:
                if e.is_symlink():
                    continue
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    yield e.path, e.stat(follow_symlinks=False)
            except OSError:
                continue


def do_list(out):
    n = 0
    with open(out, 'w', encoding='utf-8', errors='surrogateescape') as f:
        for label, root in ROOTS.items():
            for path, st in walk(root):
                f.write(f'{label}/{os.path.relpath(path, root)}\t{st.st_size}\t{st.st_mtime_ns}\t{st.st_ctime_ns}\n')
                n += 1
    print(out, n, 'files')


def load(p):
    out = {}
    with open(p, encoding='utf-8', errors='surrogateescape') as f:
        for line in f:
            a = line.rstrip('\n').split('\t')
            out[a[0]] = tuple(a[1:])
    return out


def do_compare(before, after, out, logs):
    b, a = load(before), load(after)
    opened = set()
    for log in logs:
        for line in open(log, encoding='utf-8', errors='surrogateescape'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and not line.startswith('#'):
                opened.add(parts[1])
    root = ROOTS['library-data'] + os.sep
    alias = '/path/to/lastbook/library-data/'
    op = {('library-data/' + p.removeprefix(alias).removeprefix(root)) for p in opened}
    added = sorted(set(a) - set(b))
    gone = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    with open(out, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write('change\tpath\tbefore\tafter\tI_opened_it\n')
        for k in added:
            f.write(f'added\t{k}\t\t{a[k]}\t{k in op}\n')
        for k in gone:
            f.write(f'gone\t{k}\t{b[k]}\t\t{k in op}\n')
        for k in changed:
            f.write(f'changed\t{k}\t{b[k]}\t{a[k]}\t{k in op}\n')
    def top(k):
        return '/'.join(k.split('/')[:2])
    print(f'{len(b)} files before, {len(a)} after; added {len(added)}, gone {len(gone)}, changed {len(changed)}')
    print('added by folder:', Counter(top(k) for k in added).most_common(12))
    print('gone by folder:', Counter(top(k) for k in gone).most_common(12))
    print('changed by folder:', Counter(top(k) for k in changed).most_common(12))
    print('files opened by my tools (from audit logs):', len(op))
    print('opened and also changed since:', sorted(k for k in changed if k in op)[:40])


if __name__ == '__main__':
    os.nice(15)
    if sys.argv[1] == 'list':
        do_list(sys.argv[2])
    else:
        do_compare(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])
