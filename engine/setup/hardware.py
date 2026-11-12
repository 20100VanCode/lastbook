"""What this computer has: OS, processor type, memory, graphics memory (Windows, through DXGI) and room on each disk.
No new dependency and no subprocess for any of it, except the AI's own measure (measure_ai), which runs lastbook-llm."""
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

GiB = 2 ** 30
RESERVE = int(2.5 * GiB)     # the same reserve llm_local.judge keeps for the system and the rest of Lastbook
VRAM_KEPT = GiB              # graphics memory the estimate leaves for the card's own work


def os_name():
    return 'macos' if sys.platform == 'darwin' else 'windows' if sys.platform == 'win32' else sys.platform


def arch():
    m = platform.machine().lower()
    return 'arm64' if m in ('arm64', 'aarch64') else 'x64' if m in ('x86_64', 'amd64', 'x64') else m


# --------------------------------------------------------------------------------------------------------------- Mac --
def _sysctl(name, kind='int'):
    libc = ctypes.CDLL('/usr/lib/libc.dylib', use_errno=True)
    if kind == 'int':
        v, n = ctypes.c_uint64(0), ctypes.c_size_t(8)
        if libc.sysctlbyname(name.encode(), ctypes.byref(v), ctypes.byref(n), None, ctypes.c_size_t(0)) != 0:
            return None
        return v.value
    n = ctypes.c_size_t(0)
    if libc.sysctlbyname(name.encode(), None, ctypes.byref(n), None, ctypes.c_size_t(0)) != 0 or not n.value:
        return None
    buf = ctypes.create_string_buffer(n.value)
    if libc.sysctlbyname(name.encode(), buf, ctypes.byref(n), None, ctypes.c_size_t(0)) != 0:
        return None
    return buf.value.decode('utf-8', 'replace')


# ----------------------------------------------------------------------------------------------------------- Windows --
class _MemoryStatus(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_uint32), ('dwMemoryLoad', ctypes.c_uint32), ('ullTotalPhys', ctypes.c_uint64), ('ullAvailPhys', ctypes.c_uint64),
                ('ullTotalPageFile', ctypes.c_uint64), ('ullAvailPageFile', ctypes.c_uint64), ('ullTotalVirtual', ctypes.c_uint64),
                ('ullAvailVirtual', ctypes.c_uint64), ('ullAvailExtendedVirtual', ctypes.c_uint64)]


class _Guid(ctypes.Structure):
    _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]


class _AdapterDesc1(ctypes.Structure):
    _fields_ = [('Description', ctypes.c_wchar * 128), ('VendorId', ctypes.c_uint32), ('DeviceId', ctypes.c_uint32), ('SubSysId', ctypes.c_uint32),
                ('Revision', ctypes.c_uint32), ('DedicatedVideoMemory', ctypes.c_size_t), ('DedicatedSystemMemory', ctypes.c_size_t),
                ('SharedSystemMemory', ctypes.c_size_t), ('AdapterLuid', ctypes.c_uint64), ('Flags', ctypes.c_uint32)]


def _com(ptr, index, *argtypes):
    """Method `index` of a COM object's vtable, bound to the object."""
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtbl[index])
    return lambda *a: fn(ptr, *a)


def _windows_ram():
    st = _MemoryStatus()
    st.dwLength = ctypes.sizeof(st)
    return st.ullTotalPhys if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)) else None


def _windows_gpus():
    """Each real graphics adapter (not Microsoft's software one) with its dedicated memory, from IDXGIFactory1::EnumAdapters1."""
    iid = _Guid(0x770aae78, 0xf26f, 0x4dba, (ctypes.c_ubyte * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))   # IID_IDXGIFactory1
    factory = ctypes.c_void_p()
    try:
        dxgi = ctypes.windll.dxgi
    except OSError:
        return []
    if dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(factory)) != 0 or not factory:
        return []
    out = []
    try:
        for i in range(16):
            adapter = ctypes.c_void_p()
            if _com(factory, 12, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p))(i, ctypes.byref(adapter)) != 0:   # EnumAdapters1; DXGI_ERROR_NOT_FOUND ends it
                break
            try:
                d = _AdapterDesc1()
                if _com(adapter, 10, ctypes.POINTER(_AdapterDesc1))(ctypes.byref(d)) == 0 and not d.Flags & 2:     # GetDesc1; 2 = DXGI_ADAPTER_FLAG_SOFTWARE
                    out.append({'name': d.Description.strip(), 'vram_bytes': int(d.DedicatedVideoMemory)})
            finally:
                _com(adapter, 2)()     # Release
    finally:
        _com(factory, 2)()
    return out


def _windows_drives():
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i in range(26):
        if mask & (1 << i):
            root = f'{chr(65 + i)}:\\'
            if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 3:   # DRIVE_FIXED
                out.append(Path(root))
    return out


# ------------------------------------------------------------------------------------------------------------- disks --
def disk_of(path):
    """(free, total) on the disk that holds path, or the nearest folder above it that exists."""
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    u = shutil.disk_usage(p)
    return u.free, u.total


def disk_name(path):
    """What the system calls the disk holding path: a volume name on a Mac (Macintosh HD), "Label (D:)" on Windows. None if unknown."""
    try:
        if sys.platform == 'win32':
            root = os.path.splitdrive(os.path.abspath(path))[0] + '\\'
            label = ctypes.create_unicode_buffer(261)
            if not ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), label, 261, None, None, None, None, 0):
                return None
            return f'{label.value or "Local Disk"} ({root[:2]})'
        if sys.platform == 'darwin':
            import Foundation
            p = Path(path)
            while not p.exists() and p.parent != p:
                p = p.parent
            ok, name, _ = Foundation.NSURL.fileURLWithPath_(str(p)).getResourceValue_forKey_error_(None, Foundation.NSURLVolumeLocalizedNameKey, None)
            return str(name) if ok and name else None
    except Exception:
        return None
    return None


def candidate_disks(extra=()):
    """Places a library could go, one per disk: the home folder's disk first, then other fixed drives or mounted volumes."""
    places = [Path.home(), *map(Path, extra)]
    if sys.platform == 'win32':
        places += _windows_drives()
    elif sys.platform == 'darwin':
        try:
            places += [p for p in Path('/Volumes').iterdir() if p.is_dir() and not p.is_symlink() and os.access(p, os.W_OK)]
        except OSError:
            pass
    seen, out = set(), []
    for p in places:
        try:
            q = p
            while not q.exists() and q.parent != q:
                q = q.parent
            dev = os.stat(q).st_dev
            if dev in seen:
                continue
            free, total = disk_of(q)
        except OSError:
            continue
        seen.add(dev)
        out.append({'path': str(p), 'name': disk_name(q), 'free_bytes': free, 'total_bytes': total})
    return out


# ------------------------------------------------------------------------------------------------------------ the AI --
def _gb(n):
    return f'{n / 1e9:.0f} GB' if n >= 10e9 else f'{n / 1e9:.1f} GB'


def estimate_ai(ram, gpus, unified, memory_bytes):
    """Before the model file is here to measure: the model and its context need memory_bytes, plus RESERVE for everything else.
    On a Mac that is all one memory. On Windows the part that fits on the graphics card does not count against the computer's own."""
    needs = int(memory_bytes + RESERVE)
    if not ram:
        return {'fits': False, 'needs_bytes': needs, 'estimate': True, 'why': 'Lastbook could not tell how much memory this computer has.'}
    if unified or not gpus:
        in_ram = needs
    else:
        vram = max(g['vram_bytes'] for g in gpus)
        in_ram = int(max(memory_bytes - max(vram - VRAM_KEPT, 0), 0) + RESERVE)
    fits = ram >= in_ram
    out = {'fits': fits, 'needs_bytes': needs, 'estimate': True}
    if fits:
        out['why'] = f'The local AI needs about {_gb(needs)} of memory, and this computer has {_gb(ram)}' + (
            '.' if unified or not gpus else ' plus its graphics memory.')
    else:
        out['why'] = (f'The local AI needs about {_gb(in_ram)} of this computer’s memory, and it has {_gb(ram)}. '
                      'Lastbook works without it: search and reading are the same.')
    return out


def measure_ai(llm_local, model_path, timeout=180):
    """llama.cpp's own measure of the model file on this computer, judged as the AI judges it. None if it cannot be measured."""
    runner = llm_local.runner_path()
    if not runner or not Path(model_path).is_file():
        return None
    threads = max(4, min(16, (os.cpu_count() or 8) // 2))
    argv = [str(runner), '--model', str(model_path), '--ctx', str(llm_local.CTX), '--threads', str(threads), '--measure']
    kw = {'creationflags': 0x08000000} if os.name == 'nt' else {}     # CREATE_NO_WINDOW
    try:
        out = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, **kw)
        fit = next((json.loads(l) for l in out.stdout.decode('utf-8', 'replace').splitlines() if l.startswith('{"ev":"fit"')), None)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not fit:
        return None
    j = llm_local.judge(fit)
    return {'fits': bool(j['fits']), 'needs_bytes': int(j['needs']), 'estimate': False,
            'why': j.get('why') or f'Measured on this computer: the local AI needs about {_gb(j["needs"])} of memory, and it fits.'}


def detect(extra_disks=()):
    """Everything but the AI's fit, which the caller adds (estimate_ai or measure_ai)."""
    name = os_name()
    ram, gpus, unified = None, [], False
    try:
        if name == 'macos':
            ram = _sysctl('hw.memsize')
            unified = arch() == 'arm64'
            chip = _sysctl('machdep.cpu.brand_string', 'str')
            if chip:
                gpus = [{'name': chip, 'vram_bytes': 0}]     # Apple silicon: the graphics share the one memory
        elif name == 'windows':
            ram = _windows_ram()
            gpus = _windows_gpus()
    except Exception as e:      # a strange driver must not stop setup: it then estimates from what it has
        print('setup: hardware detection:', type(e).__name__, e, flush=True)
    return {'os': name, 'arch': arch(), 'ram_bytes': ram, 'unified_memory': unified, 'gpus': gpus, 'disks': candidate_disks(extra_disks)}
