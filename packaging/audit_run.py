"""Runs a pack tool and logs every file it opens or changes inside the real library, using Python's own audit hook. Not in any pack.

  python -I -B audit_run.py <log file> <script> [its arguments]

Each line: event, path, mode or flags. A write-mode open or any rename, delete or chmod inside the library is marked WRITE. APFS clones go through ctypes and are not seen here; they are the 'clone' rows of each pack's manifest, and clonefile never writes to its source.
"""
import os
import runpy
import sys

LIBS = (os.path.realpath('/path/to/lastbook/library-data') + os.sep, '/path/to/lastbook/library-data' + os.sep)
log = open(sys.argv[1], 'a', encoding='utf-8', errors='surrogateescape', buffering=1)
log.write(f'# pid {os.getpid()} {sys.argv[2:]}\n')
seen = set()


def under(p):
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    return isinstance(p, str) and p.startswith(LIBS)


def hook(event, args):
    if event == 'open' and args and under(args[0]):
        mode, flags = args[1], args[2]
        wrote = (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)) or (isinstance(mode, str) and any(c in mode for c in 'wax+'))
        key = (event, str(args[0]), bool(wrote))
        if key not in seen:
            seen.add(key)
            log.write(f"{'WRITE' if wrote else 'read'}\t{args[0]}\t{mode}\n")
    elif event == 'sqlite3.connect' and args and any(under(str(a).removeprefix('file:')) for a in args):
        log.write(f'WRITE-OR-READ-SQLITE\t{args[0]}\t\n')
    elif event in ('os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.link', 'os.symlink', 'os.truncate', 'os.utime', 'shutil.move', 'shutil.rmtree', 'shutil.copyfile') and args:
        if any(under(a) for a in args if isinstance(a, (str, bytes))):
            log.write(f"WRITE\t{args[0]}\t{event}\n")


sys.addaudithook(hook)
script = sys.argv[2]
sys.argv = sys.argv[2:]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
runpy.run_path(script, run_name='__main__')
