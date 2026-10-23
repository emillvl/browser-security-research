"""Exercise captured subsets without changing DoppelGNG classifications or contacting the original service."""

from cdp import *
import traceback

NODE = 'node'
archives = {
    'baseline': ROOT / 'evidence/capture-baseline-1792348435497183400/archive',
    'guarded': ROOT / 'evidence/capture-guarded-1792348636401144700/archive',
}
out = ROOT / 'evidence' / ('offline-replay-' + str(time.time_ns()))
out.mkdir()
report = {'hypothesis': __doc__, 'cases': {}}
# Stop the original service before replay.
with socket.socket() as s:
    if s.connect_ex(('127.0.0.1', 45911)) == 0:
        raise RuntimeError('Finish the original-service test before attempting offline replay')
truth = json.loads((ROOT / 'evidence/ground-truth.json').read_text())['vectors']
for name, archive in archives.items():
    server = browser = page = None
    logs = []
    case = {}
    folder = out / name
    folder.mkdir()
    try:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 45918))
        manifest = json.loads((archive / 'manifest.json').read_text())
        case['unchangedCaptureStatus'] = manifest['status']
        case['resources'] = len(manifest['resources'])
        case['pages'] = len(manifest.get('pages', {}))
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
        page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
        page.command('Page.enable')
        page.command('Network.enable')
        page.command('Runtime.enable')
        page.command('Page.navigate', {'url': 'http://127.0.0.1:45918/suite/plain/'})
        ready = False
        for _ in range(100):
            if page.evaluate('document.body?.dataset.ready==="true"'):
                ready = True
                break
            time.sleep(0.05)
        case['ready'] = ready
        case['visible'] = page.evaluate(
            '({title:document.title,text:document.body?.innerText,mode:document.body?.dataset.protected})'
        )
        if ready and name == 'baseline':
            observed = page.evaluate(
                '(async()=>{const out=[];for(const input of '
                + json.dumps([v['input'] for v in truth])
                + ')out.push((await research.calculate("score",input)).result);return out;})()'
            )
            case['offlineScores'] = {
                'matches': sum(v == expected['output'] for v, expected in zip(observed, truth)),
                'total': len(truth),
            }
            case['route'] = page.evaluate(
                'research.calculate("route",{start:0,end:17,congestion:3})'
            )
        if ready and name == 'guarded':
            case['login'] = page.evaluate(
                'research.login("alice","Research-Alice-Only").then(v=>({accepted:true,value:v}),e=>({accepted:false,error:e.message}))'
            )
        case['requestURLs'] = [
            e['params']['request']['url']
            for e in page.events
            if e.get('method') == 'Network.requestWillBeSent'
        ]
        case['originalServiceRequested'] = any(
            url.startswith('http://127.0.0.1:45911/') for url in case['requestURLs']
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
print(json.dumps({**report, 'directory': str(out)}, indent=2))
