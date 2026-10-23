"""P202: compare public client execution with an independently attacked server-only deployment.
Hypothesis: withholding the program plus account authorization stops unauthenticated extraction
and duplicate execution; it does not stop an authorized operator from reusing displayed results.
The tool launches only disposable research browsers and two owned loopback services.
"""

from pathlib import Path
import sys, json, time, subprocess, urllib.request, statistics, traceback, base64
from cdp import CDP, browser_launch, targets, ROOT

NODE = 'node'
mode = sys.argv[1] if len(sys.argv) > 1 else 'guarded'
out = ROOT / 'evidence' / ('standard-' + mode + '-' + str(time.time_ns()))
out.mkdir()
report = {'mode': mode, 'hypothesis': __doc__, 'pages': {}, 'started': time.time()}
server = browser = None
page = None
logs = []


def wait(expression, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        time.sleep(0.05)
    raise TimeoutError(expression)


def navigate(path):
    page.evaluate('if(document.body)document.body.dataset.ready="navigating"')
    page.command('Page.navigate', {'url': 'http://127.0.0.1:45911' + path})
    wait('document.body?.dataset.ready==="true"&&location.pathname===' + json.dumps(path))


def summarize(values):
    values = sorted(values)
    return {
        'n': len(values),
        'median': statistics.median(values),
        'p95': values[max(0, int(len(values) * 0.95 + 0.999) - 1)],
        'min': values[0],
        'max': values[-1],
    }


try:
    import socket

    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    log = (out / 'server.log').open('w', encoding='utf-8')
    logs.append(log)
    cmd = [NODE, str(ROOT / 'websites/suite.mjs')] + (['--baseline'] if mode == 'baseline' else [])
    server = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            report['environment'] = json.load(
                urllib.request.urlopen('http://127.0.0.1:45911/environment')
            )
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError('Suite did not start')
    browser, blog, launch = browser_launch(out, False)
    logs.append(blog)
    report['launch'] = launch
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Runtime.enable')
    page.command('Network.enable')
    page.command('Network.setCacheDisabled', {'cacheDisabled': True})
    report['browser'] = page.command('Browser.getVersion')
    for kind in ['plain', 'spa', 'calculation', 'wasm', 'protected', 'account', 'worker', 'multi']:
        navigate('/suite/' + kind + '/')
        entry = {}
        if mode != 'baseline':
            entry['login'] = page.evaluate('research.login("alice","Research-Alice-Only")')
        entry['score'] = page.evaluate('research.calculate("score",[100,200,300,400,500,600])')
        entry['route'] = page.evaluate('research.calculate("route",{start:0,end:17,congestion:3})')
        entry['wasm'] = page.evaluate('research.wasm()?.transform(123,456)??null')
        entry['frameReady'] = page.evaluate('document.body.dataset.frameReady??null')
        entry['errors'] = page.evaluate('document.querySelector("#error").textContent')
        entry['layouts'] = []
        for width, height in [(1440, 900), (390, 844), (320, 740)]:
            page.command(
                'Emulation.setDeviceMetricsOverride',
                {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False},
            )
            entry['layouts'].append(
                page.evaluate(
                    '({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth})'
                )
            )
        page.command('Emulation.clearDeviceMetricsOverride')
        report['pages'][kind] = entry
    navigate('/suite/protected/')
    page.evaluate('research.login("alice","Research-Alice-Only")')
    if mode == 'guarded':
        report['attacks'] = page.evaluate(
            (ROOT / 'attacks/suite_checks.js').read_text(encoding='utf-8')
        )
    else:
        report['publicModel'] = page.evaluate(
            '(async()=>{const module=await import("/public-workload.mjs");return {bytes:JSON.stringify(module.model).length,model:module.model}})()'
        )
        report['apiBaseline'] = page.evaluate(
            'research.request("/api/anonymous",{op:"score",input:[100,200,300,400,500,600]})'
        )
    # Exercise the score form with browser keyboard events.
    page.evaluate('document.querySelector("#inputs").focus()')
    page.command(
        'Input.dispatchKeyEvent',
        {
            'type': 'rawKeyDown',
            'key': 'Enter',
            'code': 'Enter',
            'windowsVirtualKeyCode': 13,
            'nativeVirtualKeyCode': 13,
        },
    )
    page.command(
        'Input.dispatchKeyEvent',
        {
            'type': 'char',
            'text': '\r',
            'unmodifiedText': '\r',
            'key': 'Enter',
            'code': 'Enter',
            'windowsVirtualKeyCode': 13,
        },
    )
    page.command(
        'Input.dispatchKeyEvent',
        {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13},
    )
    wait('document.querySelector("#output").textContent.includes("522")')
    report['keyboard'] = page.evaluate(
        '({focused:document.activeElement.id,output:document.querySelector("#output").textContent,error:document.querySelector("#error").textContent})'
    )
    report['accessibility'] = page.command('Accessibility.getFullAXTree')
    # Matched same-server workload: one anonymous HTTP request vs the signed challenge+execute pair.
    report['benchmark'] = page.evaluate(
        '''(async()=>{
 const input=[100,200,300,400,500,600],samples=[],warm=[];
 const measurement=await research.request('/api/metrics/start',{});
 for(let i=0;i<70;i++){const before=performance.now();const v=research.mode==='baseline'?await research.request('/api/anonymous',{op:'score',input}):await research.calculate('score',input);if(v.result.score!==522)throw Error('Benchmark wrong output');(i<10?warm:samples).push(performance.now()-before);}
 return {warm,samples,service:await research.request('/api/metrics/stop',measurement)};
 })()'''
    )
    report['benchmark']['summaryMs'] = summarize(report['benchmark']['samples'])
    report['heap'] = page.command('Runtime.getHeapUsage')
    report['resources'] = page.evaluate(
        'performance.getEntriesByType("resource").map(r=>({name:r.name,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize,duration:r.duration}))'
    )
    report['coldNavigationMs'] = []
    report['authenticationMs'] = []
    for _ in range(10):
        before = time.perf_counter()
        navigate('/suite/protected/')
        report['coldNavigationMs'].append((time.perf_counter() - before) * 1000)
        report['authenticationMs'].append(
            page.evaluate(
                '(async()=>{const t=performance.now();await research.login("alice","Research-Alice-Only");return performance.now()-t;})()'
            )
        )
    report['coldNavigationSummaryMs'] = summarize(report['coldNavigationMs'])
    report['authenticationSummaryMs'] = summarize(report['authenticationMs'])
    report['screenshot'] = str(out / 'browser.png')
    (out / 'browser.png').write_bytes(
        base64.b64decode(
            page.command(
                'Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True}
            )['data']
        )
    )
    report['consoleExceptions'] = [
        e for e in page.events if e.get('method') == 'Runtime.exceptionThrown'
    ]
    report['outcome'] = 'complete'
except Exception as error:
    report['outcome'] = 'failed'
    report['error'] = repr(error)
    traceback.print_exc()
    if page:
        try:
            report['failurePage'] = page.evaluate(
                '({url:location.href,text:document.body.innerText,focus:document.activeElement.outerHTML})'
            )
        except Exception:
            pass
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
    report['elapsedSeconds'] = time.time() - report['started']
    (out / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    compact = {
        k: v
        for k, v in report.items()
        if k
        in [
            'mode',
            'outcome',
            'error',
            'elapsedSeconds',
            'coldNavigationSummaryMs',
            'authenticationSummaryMs',
        ]
    }
    compact['resultDirectory'] = str(out)
    if 'benchmark' in report:
        compact['benchmark'] = report['benchmark']['summaryMs']
    print(json.dumps(compact, indent=2))
if report['outcome'] != 'complete':
    sys.exit(1)
