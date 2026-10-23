"""P210: a separate content-script extension can observe and replace the public broker interface.
It has no debugger permission; this tests output/interface exposure separately from worker recovery.
"""

from cdp import *
import os, traceback

NODE = 'node'
out = ROOT / 'evidence' / ('content-observer-' + str(time.time_ns()))
out.mkdir()
server = browser = page = None
logs = []
report = {'hypothesis': __doc__}


def snapshot():
    return page.evaluate('JSON.parse(document.documentElement.dataset.p2Observer)')


def request(value):
    page.evaluate(
        'dispatchEvent(new CustomEvent("p2-observer-command",{detail:'
        + json.dumps(json.dumps(value))
        + '}));true'
    )


def wait(expression):
    for _ in range(100):
        if page.evaluate(expression):
            return
        time.sleep(0.05)
    raise RuntimeError('Observer control did not finish')


try:
    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    env = os.environ.copy()
    env['P2_RESEARCH_CREDENTIAL'] = json.loads(
        (ROOT / 'protections/extension/config.js').read_text().split('=', 1)[1].strip().rstrip(';')
    )
    log = (out / 'server.log').open('w')
    logs.append(log)
    server = subprocess.Popen(
        [NODE, str(ROOT / 'websites/server.mjs')], env=env, stdout=log, stderr=subprocess.STDOUT
    )
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:45911/worker-test/')
            break
        except Exception:
            time.sleep(0.1)
    browser, log, command = browser_launch(
        out, True, extra_extension_paths=[ROOT / 'protections/observer-extension']
    )
    logs.append(log)
    report['launch'] = command
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Runtime.enable')
    page.command('Page.navigate', {'url': 'http://127.0.0.1:45911/worker-test/'})
    wait(
        'document.readyState==="complete"&&typeof brokerCall==="function"&&!!document.documentElement.dataset.p2Observer'
    )
    report['normal'] = page.evaluate('brokerCall([100,200,300,400,500,600])')
    report['afterNormal'] = snapshot()
    target = next(
        t
        for t in targets(45915)
        if t['type'] == 'service_worker' and t['url'].endswith('/worker.js')
    )
    victim = target['url'].split('/')[2]
    request({'op': 'external-export', 'extensionId': victim})
    wait('!!JSON.parse(document.documentElement.dataset.p2Observer).externalResult')
    report['externalAccess'] = snapshot()['externalResult']
    request({'op': 'control'})
    wait('JSON.parse(document.documentElement.dataset.p2Observer).controlResult==="complete"')
    report['afterPositiveControl'] = snapshot()
    request({'op': 'forge', 'enabled': True})
    report['forgedInterfaceResult'] = page.evaluate('brokerCall([100,200,300,400,500,600])')
    time.sleep(0.1)
    request({'op': 'forge', 'enabled': False})
    report['afterForgery'] = snapshot()
    report['normalAfterDisable'] = page.evaluate('brokerCall([100,200,300,400,500,600])')
    report['browser'] = page.command('Browser.getVersion')
    report['outcome'] = 'complete'
except Exception as error:
    report['outcome'] = 'failed'
    report['error'] = repr(error)
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
    (out / 'results.json').write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {**{k: v for k, v in report.items() if k != 'launch'}, 'directory': str(out)}, indent=2
        )
    )
if report.get('outcome') != 'complete':
    raise SystemExit(1)
