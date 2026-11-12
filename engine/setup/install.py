"""Unpacking a pack and switching to it, so that a working library is never broken.

  <parent>/LastbookData.setup/unpack/LastbookData    the new library, built here from the pack's zip files
  <parent>/LastbookData                             the library Lastbook opens

Every member of a zip is checked before anything is written: a relative name under LastbookData/, no '..', no drive or root,
no symbolic link, no device, and a total no larger than the manifest's installed_bytes. Files are written as <name>.partial and
renamed when whole, so an unpack that stops (a crash, power) carries on where it was. Switching is one rename on one disk.
An upgrade first moves the old library aside to LastbookData.old-<date>; when the app restarts it opens the new one, and only if
that fails to open is the old one put back (apply_pending, called by app/main.py before the engine starts).
"""
import json
import os
import shutil
import stat
import time
import zipfile
from pathlib import Path, PurePosixPath

DATA_NAME = 'LastbookData'
CATALOG = Path('library-data') / 'catalog.json'
SLACK = 1.02            # installed_bytes is measured; a zip's members may add a little in directory entries
SPACE_MARGIN = 2 * 10 ** 9
PENDING = 'pending.json'
COPY = 4 * 1024 * 1024


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def is_library(folder):
    try:
        return (Path(folder) / CATALOG).is_file()
    except OSError:
        return False


def _member_parts(info):
    name = info.filename
    if '\\' in name or '\x00' in name:
        raise Refused('unpack', f'The pack holds a file with a name Lastbook does not accept ({name[:80]!r}).')
    p = PurePosixPath(name)
    if p.is_absolute() or name.startswith('/') or (p.parts and ':' in p.parts[0]):
        raise Refused('unpack', f'The pack holds a file with an absolute path ({name[:80]!r}).')
    parts = [x for x in p.parts if x not in ('', '.')]
    if any(x == '..' for x in parts):
        raise Refused('unpack', f'The pack holds a file that would land outside the library ({name[:80]!r}).')
    if not parts or parts[0] != DATA_NAME:
        raise Refused('unpack', f'The pack holds a file outside its LastbookData folder ({name[:80]!r}).')
    mode = (info.external_attr >> 16) & 0o170000
    if mode and mode not in (stat.S_IFREG, stat.S_IFDIR):
        raise Refused('unpack', f'The pack holds a link or a special file ({name[:80]!r}).')
    if info.flag_bits & 0x1:
        raise Refused('unpack', 'The pack is encrypted.')
    return parts


def check_zip(path, installed_bytes=None):
    """(list of (info, parts), total bytes) once every member has passed, else Refused."""
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise Refused('unpack', f'The pack could not be opened as a zip file ({type(e).__name__}).')
    with z:
        members, total, seen = [], 0, set()
        for info in z.infolist():
            parts = _member_parts(info)
            key = '/'.join(parts).lower()      # two names that differ only in case would overwrite each other on a Mac or Windows
            if key in seen and not info.is_dir():
                raise Refused('unpack', f'The pack holds the same file twice ({info.filename[:80]!r}).')
            seen.add(key)
            total += info.file_size
            members.append((info, parts))
    if installed_bytes is not None and total > installed_bytes * SLACK + 1024 * 1024:
        raise Refused('unpack', f'The pack unpacks to {total:,} bytes, more than the {installed_bytes:,} it should.')
    return members, total


def unpack(zip_path, into, installed_bytes, control, progress):
    """Unpacks into <into>/LastbookData. progress(done, total). control.check() raises to pause or cancel. Resumable."""
    members, total = check_zip(zip_path, installed_bytes)
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    root = into.resolve()
    done = 0
    with zipfile.ZipFile(zip_path) as z:
        for info, parts in members:
            control.check()
            dest = root.joinpath(*parts)
            if root not in dest.parents and dest != root:
                raise Refused('unpack', 'The pack holds a file that would land outside the library.')
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink():
                raise Refused('unpack', 'A link appeared in the unpack folder.')
            if dest.is_file() and dest.stat().st_size == info.file_size:
                done += info.file_size          # whole from an earlier run
                progress(done, total)
                continue
            part = dest.with_name(dest.name + '.partial')
            with z.open(info) as src, open(part, 'wb') as out:
                while True:
                    control.check()
                    b = src.read(COPY)
                    if not b:
                        break
                    out.write(b)
                    done += len(b)
                    progress(done, total)
            if part.stat().st_size != info.file_size:
                raise Refused('unpack', f'A file in the pack came out the wrong size ({info.filename[:80]!r}).')
            os.replace(part, dest)
            t = time.mktime(info.date_time + (0, 0, -1))
            os.utime(dest, (t, t))
    lib = root / DATA_NAME
    if not is_library(lib):
        raise Refused('unpack', 'The unpacked pack has no library catalog in it.')
    return lib


# ------------------------------------------------------------------------------------------------------------ space --
def need_bytes(pack, model, have_files=()):
    """Room needed on the target disk: what is still to download, plus the unpacked size, plus SPACE_MARGIN."""
    n = SPACE_MARGIN
    if pack:
        n += sum(f['size'] for f in pack['files'] if f['name'] not in have_files) + (pack.get('installed_bytes') or 0)
    if model:
        n += model['size'] if model['file'] not in have_files else 0
    return n


# -------------------------------------------------------------------------------------------------------- switching --
def _write_json(path, d):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(d, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def old_name(target):
    base = target.with_name(f'{DATA_NAME}.old-{time.strftime("%Y%m%d")}')
    p, i = base, 2
    while p.exists():
        p = base.with_name(f'{base.name}-{i}')
        i += 1
    return p


def stage_switch(work, new_lib, target, model_file=None):
    """Writes what the switch will do, for apply_pending. Nothing is renamed yet."""
    d = {'new': str(new_lib), 'target': str(target), 'model_file': model_file, 'written': time.time()}
    _write_json(Path(work) / PENDING, d)
    return d


def carry_over(old, new):
    """What belongs to the person, not the pack, goes with them: the model file, and the AI's on/off setting."""
    old, new = Path(old), Path(new)
    moved = []
    src = old / 'models'
    if src.is_dir():
        (new / 'models').mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            dest = new / 'models' / f.name
            if f.is_file() and not dest.exists():
                os.replace(f, dest)
                moved.append(dest)
    state = old / 'derived' / 'llm' / 'state.json'
    if state.is_file() and not (new / 'derived' / 'llm' / 'state.json').exists():
        (new / 'derived' / 'llm').mkdir(parents=True, exist_ok=True)
        shutil.copy2(state, new / 'derived' / 'llm' / 'state.json')
    return moved


def switch(new_lib, target):
    """The renames. Returns the old library's new name, or None when there was none. Raises Refused, leaving things as they were."""
    new_lib, target = Path(new_lib), Path(target)
    if not is_library(new_lib):
        raise Refused('activate', 'The new library is not complete.')
    old = None
    if target.exists():
        old = old_name(target)
        if is_library(target):
            carry_over(target, new_lib)
        try:
            os.replace(target, old)
        except OSError as e:
            raise Refused('activate', f'Lastbook could not move the old library aside ({type(e).__name__}). Close anything using it, then try again.')
    try:
        os.replace(new_lib, target)
    except OSError as e:
        if old:
            os.replace(old, target)
        raise Refused('activate', f'Lastbook could not put the new library in place ({type(e).__name__}).')
    return old


def apply_pending(work):
    """Runs at startup, before the engine opens anything. Returns (library folder or None, a note dict or None).
    If a switch was staged, do it; if the new library then does not open, put the old one back."""
    work = Path(work)
    pend = work / PENDING
    try:
        d = json.loads(pend.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, None
    target = Path(d['target'])
    note = {'target': str(target), 'old': None, 'model_file': d.get('model_file')}
    if d.get('switched'):
        lib_ok = is_library(target)
    else:
        try:
            old = switch(d['new'], target)
        except Refused as e:
            print('setup: switch failed:', e.message, flush=True)
            pend.unlink()
            note['error'] = e.message
            return (target if is_library(target) else None), note
        d['switched'], d['old'] = True, old and str(old)
        _write_json(pend, d)
        lib_ok = is_library(target)
    note['old'] = d.get('old')
    if not lib_ok and d.get('old') and Path(d['old']).exists():
        broken = target.with_name(target.name + '.failed')
        os.replace(target, broken)
        os.replace(d['old'], target)
        carry_over(broken, target)      # the model file, moved into the new one, goes back too
        note['error'] = 'The new library did not open, so Lastbook put the old one back.'
        note['old'] = None
    return target if is_library(target) else None, note


def confirm(work):
    """The new library opened: the switch is done. The old one stays until the person deletes it from setup."""
    try:
        (Path(work) / PENDING).unlink()
    except OSError:
        pass
