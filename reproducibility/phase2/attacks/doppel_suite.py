"""Run the capture tool unchanged and retain its classifications."""

import os

from pathlib import Path
import subprocess, time, json, urllib.request, socket, sys

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(
    os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[2] / '.doppelgng'))
)
NODE = 'node'
mode = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
out = ROOT / 'evidence' / ('capture-' + mode + '-' + str(time.time_ns()))
out.mkdir()
for port in [45911, 45912, 45918]:
    with socket.socket() as s:
        s.bind(('127.0.0.1', port))
serverlog = (out / 'server.log').open('w')
server = subprocess.Popen(
    [NODE, str(ROOT / 'websites/suite.mjs')] + (['--baseline'] if mode == 'baseline' else []),
    stdout=serverlog,
    stderr=subprocess.STDOUT,
)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:45911/environment')
            break
        except Exception:
            time.sleep(0.1)
    command = [
        sys.executable,
        '-m',
        'doppelgng',
        'capture',
        '--url',
        'http://127.0.0.1:45911/suite/plain/',
        '--authorized',
        '--authorize-resource-origin',
        'http://127.0.0.1:45912',
        '--output',
        str(out / 'archive'),
        '--port',
        '45918',
    ]
    (out / 'procedure.json').write_text(
        json.dumps(
            {
                'mode': mode,
                'command': command,
                'scope': 'Public signed-out pages; JavaScript-only sign-in and mutations are outside the unchanged capture workflow.',
            },
            indent=2,
        )
    )
    with (out / 'capture.log').open('w') as log:
        result = subprocess.run(command, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT)
    print(
        json.dumps({'mode': mode, 'exitCode': result.returncode, 'directory': str(out)}), flush=True
    )
finally:
    server.terminate()
    server.wait(timeout=8)
    serverlog.close()
