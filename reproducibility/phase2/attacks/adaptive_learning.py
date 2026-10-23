"""P209: four adaptive rounds of 128 queries versus 512 new random queries at equal final budgets.
Selection uses disagreement among prefixes of an already learned boosting model. It sees no hidden
fixture constants or held-out labels. Both final learners use 2,048 shared initial observations.
"""

import sys

from cdp import *
import random, traceback

NODE = 'node'
PYTHON = sys.executable
base = ROOT / 'evidence/learning-1792348353553058500'
initial = json.loads((base / 'queried-pairs.json').read_text())
model = json.loads((base / 'learned-offline-model.json').read_text())
out = ROOT / 'evidence' / ('adaptive-' + str(time.time_ns()))
out.mkdir()
report = {'hypothesis': __doc__, 'rounds': []}
server = browser = page = None
logs = []
used = {tuple(row['input']) for row in initial['training']}
heldoutInputs = {tuple(row['input']) for row in initial['heldout']}
rng = random.Random(209)


def predict_tree(tree, row):
    while isinstance(tree, list):
        tree = tree[2] if row[tree[0]] <= tree[1] else tree[3]
    return tree


def disagreement(learned, row):
    total = learned['mean']
    prefix = []
    for i, tree in enumerate(learned['trees']):
        total += learned['rate'] * predict_tree(tree, row)
        if i in [29, 59, 89]:
            prefix.append(total)
    return max(prefix) - min(prefix)


def fresh_vectors(count):
    result = []
    while len(result) < count:
        row = tuple(rng.randrange(1001) for _ in range(6))
        if row in used or row in heldoutInputs:
            continue
        result.append(list(row))
        used.add(row)
    return result


def query(vectors):
    rows = []
    for at in range(0, len(vectors), 128):
        rows += page.evaluate(
            '(async()=>{const rows=[];for(const input of '
            + json.dumps(vectors[at : at + 128])
            + ')rows.push({input,output:(await research.calculate("score",input)).result});return rows;})()'
        )
    return rows


def train(folder, rows):
    folder.mkdir()
    file = folder / 'queried-pairs.json'
    file.write_text(json.dumps({'training': rows, 'heldout': initial['heldout']}, indent=2))
    with (folder / 'learner.log').open('w') as log:
        subprocess.run(
            [PYTHON, str(ROOT / 'attacks/learn_behavior.py'), str(file), json.dumps([len(rows)])],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    return json.loads((folder / 'learned-offline-model.json').read_text()), json.loads(
        (folder / 'learning-results.json').read_text()
    )


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
    randomControl = fresh_vectors(512)
    active = list(initial['training'])
    for step in range(4):
        candidates = fresh_vectors(2048)
        selected = sorted(candidates, key=lambda row: disagreement(model, row), reverse=True)[:128]
        observed = query(selected)
        active += observed
        model, result = train(out / ('round-' + str(step + 1)), active)
        report['rounds'].append(
            {'newQueries': 128, 'totalQueries': len(active), 'metrics': result['curves'][0]}
        )
        print('Adaptive round ' + str(step + 1) + ' completed', flush=True)
    control = list(initial['training']) + query(randomControl)
    _, controlResult = train(out / 'random-control', control)
    report['adaptiveFinal'] = report['rounds'][-1]['metrics']
    report['randomFinal'] = controlResult['curves'][0]
    report['sharedInitialQueries'] = 2048
    report['additionalQueriesEach'] = 512
    report['combinedOracleQueries'] = 3072
    report['heldout'] = 1000
    report['accountState'] = page.evaluate('research.request("/api/state")')
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
            {
                **{
                    k: v
                    for k, v in report.items()
                    if k not in ['rounds', 'accountState', 'browser']
                },
                'directory': str(out),
            },
            indent=2,
        )
    )
if report.get('outcome') != 'complete':
    raise SystemExit(1)
