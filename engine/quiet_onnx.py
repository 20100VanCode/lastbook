"""Windows only. onnxruntime writes usage events to Windows (ETW provider Microsoft.ML.ONNXRuntime) while it is being imported, with the computer's processor,
memory and graphics drivers in them, and the Windows collector is listed for that provider. No setting reaches those: disable_telemetry_events runs too late.

So the two onnxruntime files are loaded first, without the import that starts them, and their one call that writes an event is pointed at a function that
writes nothing and reports success. The files on disk stay as they are. Only this process changes, and only these two files' calls.
Anything unexpected raises, and retrieval.py then never imports onnxruntime: semantic search is off and keyword search works.
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import sys

FILES = ('onnxruntime_pybind11_state.pyd', 'onnxruntime.dll')
WRITERS = {b'EventWrite', b'EventWriteEx', b'EventWriteString', b'EventWriteTransfer'}
WRITES_NOTHING = b'\x31\xc0\xc3'     # xor eax, eax; ret. ERROR_SUCCESS, on x64 where the caller cleans up.
ALTERED_SEARCH_PATH, COMMIT_RESERVE, READ_WRITE, EXECUTE_READ = 0x8, 0x3000, 0x04, 0x20
_done = []


def _api():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.LoadLibraryExW.restype = wt.HMODULE
    k.LoadLibraryExW.argtypes = (wt.LPCWSTR, wt.HANDLE, wt.DWORD)
    k.VirtualAlloc.restype = ctypes.c_void_p
    k.VirtualAlloc.argtypes = (ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD)
    k.VirtualProtect.restype = wt.BOOL
    k.VirtualProtect.argtypes = (ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, ctypes.POINTER(wt.DWORD))
    return k


def _capi_folder():
    root = getattr(sys, '_MEIPASS', None)
    if root:
        return os.path.join(root, 'onnxruntime', 'capi')
    spec = importlib.util.find_spec('onnxruntime')
    if not spec or not spec.origin:
        raise ImportError('onnxruntime is not installed')
    return os.path.join(os.path.dirname(spec.origin), 'capi')


def _u32(address):
    return ctypes.c_uint32.from_address(address).value


def _point_writers_at(base, stub, k):
    """Walks the file's import table in memory: a 64-bit image's table of 20-byte entries, each with its names and the slots its calls go through."""
    header = base + _u32(base + 0x3C)
    if ctypes.c_uint16.from_address(header + 24).value != 0x20B:   # PE32+
        raise OSError('not a 64-bit image')
    entry = base + _u32(header + 24 + 112 + 8)                     # the optional header's second data directory: imports
    changed = 0
    while _u32(entry + 12):
        names, slots = base + (_u32(entry) or _u32(entry + 16)), base + _u32(entry + 16)
        i = 0
        while True:
            thunk = ctypes.c_uint64.from_address(names + i * 8).value
            if not thunk:
                break
            if not thunk >> 63 and ctypes.string_at(base + (thunk & 0x7fffffff) + 2) in WRITERS:
                old = wt.DWORD()
                slot = slots + i * 8
                if not k.VirtualProtect(slot, 8, READ_WRITE, ctypes.byref(old)):
                    raise ctypes.WinError(ctypes.get_last_error())
                ctypes.c_uint64.from_address(slot).value = stub
                k.VirtualProtect(slot, 8, old.value, ctypes.byref(wt.DWORD()))
                changed += 1
            i += 1
        entry += 20
    return changed


def silence():
    if _done:
        return
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError('only 64-bit Windows is handled')
    k = _api()
    stub = k.VirtualAlloc(None, 4096, COMMIT_RESERVE, READ_WRITE)
    if not stub:
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(stub, WRITES_NOTHING, len(WRITES_NOTHING))
    if not k.VirtualProtect(stub, 4096, EXECUTE_READ, ctypes.byref(wt.DWORD())):
        raise ctypes.WinError(ctypes.get_last_error())
    folder = _capi_folder()
    for name in FILES:
        handle = k.LoadLibraryExW(os.path.join(folder, name), None, ALTERED_SEARCH_PATH)     # runs no onnxruntime start-up: that happens in the import
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if not _point_writers_at(handle, stub, k):
            raise OSError(f'{name} has none of the expected calls: a different onnxruntime')
    _done.append(True)
