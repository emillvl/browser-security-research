"""P205: collect fresh authorized browser queries for a larger behavioral clone.
Fixed budgets and independently held-out vectors are declared before querying.
"""

from cdp import *
import random, traceback

NODE = 'node'
out = ROOT / 'evidence' / ('learning-' + str(time.time_ns()))
out.mkdir()
rng = random.Random(20261018)
training = [[rng.randrange(1001) for _ in range(6)] for _ in range(2048)]
heldout = [[rng.randrange(1001) for _ in range(6)] for _ in range(1000)]
dataset = {'hypothesis': __doc__, 'training': [], 'heldout': []}
server = browser = page = None
logs = []
try:
    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    log = (out / 'server.log').open('w')
    logs.append(log)
    server = subprocess.Popen(
        [NODE, str(ROOT / 'websites/suite.mjs')], stdout=log, stderr=subprocess.STDOUT
    )
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:45911/environment')
            break
        except Exception:
            time.sleep(0.1)
    browser, log, _ = browser_launch(out, False)
    logs.append(log)
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Page.navigate', {'url': 'http://127.0.0.1:45911/suite/protected/'})
    for _ in range(100):
        if page.evaluate('document.body?.dataset.ready==="true"'):
            break
        time.sleep(0.05)
    page.evaluate('research.login("alice","Research-Alice-Only")')
    for name, vectors in [('training', training), ('heldout', heldout[:100])]:
        for offset in range(0, len(vectors), 128):
            batch = vectors[offset : offset + 128]
            pairs = page.evaluate(
                '(async()=>{const rows=[];for(const input of '
                + json.dumps(batch)
                + '){const output=(await research.calculate("score",input)).result;rows.push({input,output});}return rows;})()'
            )
            if name == 'training':
                dataset['training'] += pairs
            else:
                dataset['heldoutOnlineAudit'] = pairs
        print(name + ': ' + str(len(vectors)) + ' real browser queries completed', flush=True)
    # Ground truth is evaluated only after all black-box observations are collected; it is not a learner feature.
    source = "import {fixtureModel,evaluateModel} from './phase2/websites/workload.mjs';let raw='';for await(const p of process.stdin)raw+=p;const m=fixtureModel();console.log(JSON.stringify(JSON.parse(raw).map(input=>({input,output:evaluateModel(m,input)}))));"
    rows = json.loads(
        subprocess.check_output(
            [NODE, '--input-type=module', '-e', source],
            input=json.dumps(heldout).encode(),
            cwd=str(ROOT.parent),
        )
    )
    dataset['heldout'] = rows
    dataset['onlineAuditMatches'] = sum(
        a == b for a, b in zip(dataset['heldoutOnlineAudit'], rows[:100])
    )
    dataset['accountState'] = page.evaluate('research.request("/api/state")')
    dataset['browser'] = page.command('Browser.getVersion')
    dataset['outcome'] = 'complete'
except Exception as e:
    dataset['error'] = repr(e)
    dataset['outcome'] = 'failed'
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
    (out / 'queried-pairs.json').write_text(json.dumps(dataset, indent=2))
    print(str(out), flush=True)
if dataset.get('outcome') != 'complete':
    raise RuntimeError(dataset.get('error'))
