"""Exercise the ordinary VBS loader with my unsigned test image. No signing policy is altered.
Successful allocation is not attestation, secrecy, or successful protected program execution.
"""

from pathlib import Path
import ctypes, json, sys, time, hashlib
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[1]
image = Path(sys.argv[1]).resolve()
assert image.is_relative_to(ROOT / 'binary')
k = ctypes.WinDLL('api-ms-win-core-enclave-l1-1-0.dll', use_last_error=True)
process_api = ctypes.WinDLL('kernel32', use_last_error=True)
process_api.GetCurrentProcess.restype = wintypes.HANDLE


class Info(ctypes.Structure):
    _fields_ = [('Flags', wintypes.DWORD), ('OwnerID', ctypes.c_ubyte * 32)]


info = Info()
info.Flags = 0
info.OwnerID[:] = hashlib.sha256(b'owned-phase-two-research').digest()
error = wintypes.DWORD()
k.CreateEnclave.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
k.CreateEnclave.restype = ctypes.c_void_p
k.LoadEnclaveImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
k.LoadEnclaveImageW.restype = wintypes.BOOL
k.DeleteEnclave.argtypes = [ctypes.c_void_p]
k.DeleteEnclave.restype = wintypes.BOOL
report = {
    'hypothesis': __doc__,
    'image': str(image),
    'debuggable': False,
    'sizeBytes': 2097152,
    'settingsChanged': False,
    'attestationPerformed': False,
}
ctypes.set_last_error(0)
address = k.CreateEnclave(
    process_api.GetCurrentProcess(),
    None,
    2097152,
    0,
    16,
    ctypes.byref(info),
    ctypes.sizeof(info),
    ctypes.byref(error),
)
code = ctypes.get_last_error()
report['create'] = {
    'success': bool(address),
    'windowsError': code,
    'enclaveError': error.value,
    'message': ctypes.FormatError(code),
}
if address:
    try:
        ctypes.set_last_error(0)
        loaded = k.LoadEnclaveImageW(address, str(image))
        code = ctypes.get_last_error()
        report['load'] = {
            'success': bool(loaded),
            'windowsError': code,
            'message': ctypes.FormatError(code),
        }
        report['executionAttempted'] = False
    finally:
        ctypes.set_last_error(0)
        deleted = k.DeleteEnclave(address)
        code = ctypes.get_last_error()
        report['delete'] = {
            'success': bool(deleted),
            'windowsError': code,
            'message': ctypes.FormatError(code),
        }
(image.parent / 'loader-results.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
