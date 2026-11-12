"""Are the built app's own files enough? Never packaged. Runs real_data_check.py with every import served from inside Lastbook.app.

The product window can't be driven from outside, and PDF, ZIM and numpy load only on first use, so a smoke run alone wouldn't catch a missing one.
This uses the app's compressed modules and native libraries under the same Python version, with sys.frozen set. It is the package's contents, not the
package running: no window. Anything imported from outside the package is listed at the end, so a product import that isn't packaged shows up.
  LASTBOOK_TEST_DATA=<folder> mac-venv/bin/python -B mac_package_contents.py <Lastbook.app>"""
import marshal
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE2 = r'''
import importlib.abc, importlib.machinery, importlib.util, marshal, os, runpy, sys, atexit
frameworks, blob, check = sys.argv[1:4]
real_stdlib = [p for p in sys.path if 'python3.11' in p]
toc = marshal.loads(open(blob, 'rb').read())
sys.frozen = True
sys._MEIPASS = frameworks
outside = []

class Package(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if name not in toc:
            return None
        kind = toc[name][0]
        spec = importlib.util.spec_from_loader(name, self, is_package=kind in (1, 3))
        where = os.path.join(frameworks, *name.split('.'))
        spec.origin = os.path.join(where, '__init__.py') if kind == 1 else where + '.py'
        spec.has_location = True
        if kind in (1, 3):
            spec.submodule_search_locations = [where]
        return spec
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        code = marshal.loads(toc[module.__name__][1]) if toc[module.__name__][1] else None
        if code:
            exec(code, module.__dict__)

class Outside(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(name, real_stdlib if path is None else path)
        if spec and spec.origin and not spec.origin.startswith(frameworks):
            outside.append(name)
        return spec

sys.path[:] = [os.path.join(frameworks, 'base_library.zip'), frameworks, os.path.join(frameworks, 'lib-dynload')]
sys.meta_path[:] = [m for m in sys.meta_path if m is not importlib.machinery.PathFinder]
sys.meta_path += [Package(), importlib.machinery.PathFinder, Outside()]
def report():
    print('FROM THE PACKAGE:', {n: str(getattr(sys.modules.get(n), '__file__', None)).replace(frameworks, '<app>') for n in ('server', 'bridge', 'engine.library', 'numpy', 'pypdfium2', 'libzim', 'bs4')})
    print('IMPORTED FROM OUTSIDE THE PACKAGE:', sorted(set(outside)))
atexit.register(report)
_exit = os._exit
def exit_with_report(code):   # real_data_check leaves this way, which skips atexit
    report()
    sys.stdout.flush()
    _exit(code)
os._exit = exit_with_report
runpy.run_path(check, run_name='__main__')
'''


def main():
    from PyInstaller.archive.readers import CArchiveReader
    app = Path(sys.argv[1]).resolve()
    pkg = CArchiveReader(str(app / 'Contents/MacOS/Lastbook'))
    toc = {}
    for name, entry in pkg.toc.items():
        if entry[-1] == 'z':
            pyz = pkg.open_embedded_archive(name)
            toc = {mod: (pyz.toc[mod][0], pyz.extract(mod, raw=True) if pyz.toc[mod][0] in (0, 1) else None) for mod in pyz.toc}
    with tempfile.NamedTemporaryFile(suffix='.bin', dir=os.environ.get('TMPDIR')) as f:
        f.write(marshal.dumps(toc))
        f.flush()
        return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', STAGE2, str(app / 'Contents/Frameworks'), f.name, str(HERE / 'real_data_check.py')]).returncode


if __name__ == '__main__':
    sys.exit(main())
