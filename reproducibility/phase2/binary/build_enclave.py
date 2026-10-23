"""Compile a non-debug, unsigned VBS sample; no certificates or host settings are changed."""

from pathlib import Path
import subprocess, json, hashlib, time

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'binary' / ('enclave-build-' + str(time.time_ns()))
out.mkdir()
vc = Path(
    r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207'
)
sdk = Path(r'C:\Program Files (x86)\Windows Kits\10')
command = [
    str(vc / 'bin/Hostx64/x64/cl.exe'),
    '/nologo',
    '/O2',
    '/MT',
    '/guard:cf',
    '/LD',
    '/DUNICODE',
    '/D_UNICODE',
]
for folder in [
    vc / 'include',
    sdk / 'Include/10.0.26100.0/um',
    sdk / 'Include/10.0.26100.0/shared',
    sdk / 'Include/10.0.26100.0/ucrt',
]:
    command += ['/I' + str(folder)]
command += [
    str(ROOT / 'binary/enclave-research.c'),
    '/Fo' + str(out / 'enclave.obj'),
    '/link',
    '/OUT:' + str(out / 'research-enclave.dll'),
    '/IMPLIB:' + str(out / 'research-enclave.lib'),
    '/NODEFAULTLIB',
    '/INTEGRITYCHECK',
    '/ENCLAVE',
    '/GUARD:MIXED',
    '/INCREMENTAL:NO',
]
command += [
    str(p)
    for p in [
        vc / 'lib/x64/enclave/libcmt.lib',
        vc / 'lib/x64/enclave/libvcruntime.lib',
        sdk / 'Lib/10.0.26100.0/um/x64/vertdll.lib',
        sdk / 'Lib/10.0.26100.0/um/x64/bcrypt.lib',
        sdk / 'Lib/10.0.26100.0/ucrt_enclave/x64/ucrt.lib',
    ]
]
result = subprocess.run(command, cwd=str(out), capture_output=True, text=True)
report = {
    'hypothesis': __doc__,
    'command': command,
    'exitCode': result.returncode,
    'stdout': result.stdout,
    'stderr': result.stderr,
    'debuggable': False,
    'signed': False,
}
if result.returncode == 0:
    tool = subprocess.run(
        [str(sdk / 'bin/10.0.26100.0/x64/veiid.exe'), str(out / 'research-enclave.dll')],
        capture_output=True,
        text=True,
    )
    report['veiid'] = {'exitCode': tool.returncode, 'stdout': tool.stdout, 'stderr': tool.stderr}
    report['sha256'] = hashlib.sha256((out / 'research-enclave.dll').read_bytes()).hexdigest()
(out / 'build.json').write_text(json.dumps(report, indent=2))
print(json.dumps({**report, 'directory': str(out)}, indent=2))
result.check_returncode()
