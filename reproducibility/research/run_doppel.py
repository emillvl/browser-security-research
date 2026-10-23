"""Run the capture tool with its existing source and policy."""

import shutil

from pathlib import Path
import subprocess, os, time, json, sys
from record import record

ROOT = Path(__file__).resolve().parent
PROJECT = Path(
    os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[1] / '.doppelgng'))
)
NODE = Path(shutil.which('node') or 'node').resolve().parent
mode = sys.argv[1] if len(sys.argv) > 1 else 'live'
targets = {
    'live': ('https://emilvaliyev.com/', 'captures/live'),
    'baseline': ('http://127.0.0.1:4381/baseline/', 'captures/baseline'),
    'protected': ('http://127.0.0.1:4381/protected/', 'captures/protected'),
    'protected_authorized': ('http://127.0.0.1:4381/protected/', 'captures/protected_authorized'),
    'robots': ('http://127.0.0.1:4381/robots/', 'captures/robots'),
}
url, folder = targets[mode]
output = ROOT / folder
env = os.environ.copy()
env['PYTHONPATH'] = str(PROJECT)
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PATH'] = str(NODE) + os.pathsep + env.get('PATH', '')
env['TMP'] = str(ROOT / 'tmp')
env['TEMP'] = str(ROOT / 'tmp')
(ROOT / 'tmp').mkdir(exist_ok=True)
env['PYTHONIOENCODING'] = 'utf-8'
command = [
    str(PROJECT / '.venv/Scripts/python.exe'),
    '-B',
    '-m',
    'doppelgng',
    'capture',
    '--url',
    url,
    '--authorized',
    '--output',
    str(output),
    '--port',
    {
        'live': '4385',
        'baseline': '4386',
        'protected': '4387',
        'protected_authorized': '4387',
        'robots': '4388',
    }[mode],
]
if mode in ('baseline', 'protected', 'protected_authorized'):
    command += ['--scenarios', str(ROOT / 'lab/scenarios.json')]
if mode == 'protected_authorized':
    command += ['--authorize-resource-origin', 'http://127.0.0.1:4382']
record(
    'decision',
    'DOP-' + mode,
    'Begin unmodified DoppelGNG CLI with default robots, tolerance and viewports.',
    command=command,
)
start = time.perf_counter()
with (ROOT / 'evidence' / f'doppel-{mode}.log').open('w', encoding='utf-8') as f:
    result = subprocess.run(command, cwd=ROOT.parent, env=env, stdout=f, stderr=subprocess.STDOUT)
summary = {
    'mode': mode,
    'command': command,
    'elapsed_seconds': time.perf_counter() - start,
    'exit_code': result.returncode,
}
if (output / 'manifest.json').exists():
    m = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    summary.update(
        status=m.get('status'),
        pages={u: p.get('state') for u, p in m.get('pages', {}).items()},
        resources=len(m.get('resources', {})),
        error=m.get('error'),
    )
(ROOT / 'evidence' / f'doppel-{mode}-summary.json').write_text(
    json.dumps(summary, indent=2), encoding='utf-8'
)
record(
    'observation',
    'DOP-' + mode,
    'Capture process finished.',
    [f'evidence/doppel-{mode}.log', f'evidence/doppel-{mode}-summary.json'],
    result=summary,
)
print(json.dumps(summary, indent=2))
sys.exit(result.returncode)
