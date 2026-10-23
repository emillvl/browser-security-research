"""Replay captured interface subsets in a standard browser after stopping the original services.
The capture tool's incomplete verdicts remain unchanged."""

from cdp import *
import sys, traceback

NODE = 'node'
captures = Path(sys.argv[1])
out = ROOT / 'evidence' / ('offline-brokers-' + str(time.time_ns()))
out.mkdir()
report = {'hypothesis': __doc__, 'cases': {}}
for port in [45911, 45912]:
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError('Original broker service must be stopped before offline replay')
for name, route in [
    ('extension-v1', 'worker-test'),
    ('extension-v2', 'broker-v2'),
    ('browser-component', 'native-test'),
]:
    folder = out / name
    folder.mkdir()
    archive = (
        (Path(sys.argv[2]) if name == 'browser-component' and len(sys.argv) > 2 else captures)
        / name
        / 'archive'
    )
    server = browser = page = None
    logs = []
    case = {}
    try:
        manifest = json.loads((archive / 'manifest.json').read_text())
        case['unchangedCaptureStatus'] = manifest['status']
        case['resourceCount'] = len(manifest['resources'])
        with socket.socket() as s:
            s.bind(('127.0.0.1', 45918))
        log = (folder / 'replay.log').open('w')
        logs.append(log)
        server = subprocess.Popen(
            [
                NODE,
                str(archive / 'server.mjs'),
                '--manifest',
                str(archive / 'manifest.json'),
                '--port',
                '45918',
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:45918/__doppelgng__/report')
                break
            except Exception:
                time.sleep(0.1)
        browser, log, command = browser_launch(folder, False)
        logs.append(log)
        case['launch'] = command
        page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
        page.command('Page.enable')
        page.command('Network.enable')
        page.command('Page.navigate', {'url': 'http://127.0.0.1:45918/' + route + '/'})
        for _ in range(100):
            if page.evaluate('document.readyState==="complete"&&typeof brokerCall==="function"'):
                break
            time.sleep(0.05)
        else:
            raise RuntimeError('Captured interface did not become ready')
        case['visible'] = page.evaluate(
            '({title:document.title,text:document.body.innerText,input:document.querySelector("#vector").value,broker:document.body.dataset.broker||"extension",modelType:typeof model})'
        )
        page.evaluate('document.querySelector("#calculate").click();true')
        for _ in range(250):
            if page.evaluate('document.querySelector("#result").textContent.length>0'):
                break
            time.sleep(0.05)
        case['ordinaryButtonResult'] = page.evaluate(
            'document.querySelector("#result").textContent'
        )
        case['requests'] = [
            event['params']['request']['url']
            for event in page.events
            if event.get('method') == 'Network.requestWillBeSent'
        ]
        case['originalServiceRequested'] = any(
            url.startswith(('http://127.0.0.1:45911/', 'http://127.0.0.1:45912/'))
            for url in case['requests']
        )
        case['outcome'] = 'complete'
    except Exception as error:
        case['outcome'] = 'failed'
        case['error'] = repr(error)
        traceback.print_exc()
    finally:
        if page:
            try:
                page.command('Browser.close')
            except Exception:
                pass
            page.close()
        if browser:
            try:
                browser.wait(timeout=8)
            except subprocess.TimeoutExpired:
                browser.terminate()
        if server:
            server.terminate()
            server.wait(timeout=8)
        for log in logs:
            log.close()
        report['cases'][name] = case
        (out / 'results.json').write_text(json.dumps(report, indent=2))
        print(
            json.dumps(
                {
                    'case': name,
                    **{
                        key: value
                        for key, value in case.items()
                        if key not in ['launch', 'requests']
                    },
                }
            ),
            flush=True,
        )
print(json.dumps({'directory': str(out)}))
if any(case.get('outcome') != 'complete' for case in report['cases'].values()):
    raise SystemExit(1)
