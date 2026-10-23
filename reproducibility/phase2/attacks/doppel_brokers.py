"""Capture broker interfaces with DoppelGNG and retain its verdicts.
The stock capture browser has neither the custom parent actor nor the MV3 broker installed.
An incomplete capture therefore cannot establish secrecy against a browser owner."""

from pathlib import Path
import os, subprocess, time, json, urllib.request, socket, sys, secrets, traceback

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(
    os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[2] / '.doppelgng'))
)
NODE = 'node'
out = ROOT / 'evidence' / ('capture-brokers-' + str(time.time_ns()))
out.mkdir()
report = {'hypothesis': __doc__, 'cases': {}}
for name, source, route in [
    ('extension-v1', 'server.mjs', 'worker-test'),
    ('extension-v2', 'provisioning.mjs', 'broker-v2'),
    ('browser-component', 'server.mjs', 'native-test'),
]:
    if len(sys.argv) > 1 and name != sys.argv[1]:
        continue
    folder = out / name
    folder.mkdir()
    server = None
    case = {
        'route': route,
        'limitation': 'Unchanged stock capture browser has no broker runtime. Functional owner extraction is evaluated separately.',
    }
    try:
        for port in [45911, 45912, 45918]:
            with socket.socket() as s:
                s.bind(('127.0.0.1', port))
        env = os.environ.copy()
        env['P2_ADMIN_TOKEN'] = secrets.token_hex(32)
        env['P2_CAPTURE_ROUTE'] = route
        env['P2_RESEARCH_CREDENTIAL'] = json.loads(
            (ROOT / 'protections/extension/config.js')
            .read_text()
            .split('=', 1)[1]
            .strip()
            .rstrip(';')
        )
        with (folder / 'server.log').open('w') as serverlog:
            server = subprocess.Popen(
                [NODE, str(ROOT / 'websites' / source)],
                env=env,
                stdout=serverlog,
                stderr=subprocess.STDOUT,
            )
            for _ in range(100):
                try:
                    urllib.request.urlopen('http://127.0.0.1:45911/' + route + '/')
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Owned broker site did not start')
            command = [
                sys.executable,
                '-m',
                'doppelgng',
                'capture',
                '--url',
                'http://127.0.0.1:45911/' + route + '/',
                '--authorized',
                '--output',
                str(folder / 'archive'),
                '--port',
                '45918',
            ]
            (folder / 'procedure.json').write_text(
                json.dumps({'command': command, 'scope': case['limitation']}, indent=2)
            )
            print(json.dumps({'starting': name, 'directory': str(folder)}), flush=True)
            with (folder / 'capture.log').open('w') as log:
                result = subprocess.run(
                    command, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT
                )
            case['exitCode'] = result.returncode
            manifest_path = folder / 'archive/manifest.json'
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                case['status'] = manifest['status']
                case['resources'] = len(manifest['resources'])
                case['pages'] = {
                    url: {
                        key: value
                        for key, value in page.items()
                        if key in ['state', 'error', 'validation', 'title']
                    }
                    for url, page in manifest.get('pages', {}).items()
                }
            else:
                case['manifest'] = 'Not created'
        case['outcome'] = 'complete'
    except Exception as error:
        case['outcome'] = 'failed'
        case['error'] = repr(error)
        traceback.print_exc()
    finally:
        if server:
            server.terminate()
            server.wait(timeout=8)
        report['cases'][name] = case
        (out / 'results.json').write_text(json.dumps(report, indent=2))
        print(
            json.dumps(
                {
                    'finished': name,
                    **{
                        key: case.get(key)
                        for key in ['status', 'resources', 'exitCode', 'outcome', 'error']
                    },
                }
            ),
            flush=True,
        )
print(
    json.dumps(
        {
            'directory': str(out),
            'outcomes': {
                name: {key: case.get(key) for key in ['status', 'resources', 'outcome', 'error']}
                for name, case in report['cases'].items()
            },
        },
        indent=2,
    )
)
if any(case.get('outcome') != 'complete' for case in report['cases'].values()):
    raise SystemExit(1)
