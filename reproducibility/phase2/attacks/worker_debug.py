from pathlib import Path
import sys, time, json, hashlib, statistics, math

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from log import ROOT, event
from cdp import CDP, targets, browser_launch

out = ROOT / 'evidence' / ('worker-' + str(time.time_ns()))
out.mkdir()
event(
    'hypothesis',
    'P201',
    'I will compare page-level denial with operator recovery and mutation of an encrypted decision model in a real extension service worker.',
    [str(out.relative_to(ROOT))],
)
results = {}
process = None
try:
    process, log, command = browser_launch(out)
    results['launch_command'] = command
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    results['browser'] = page.command('Browser.getVersion')
    page.command('Page.enable')
    page.command('Page.navigate', {'url': 'http://127.0.0.1:45911/worker-test/'})
    for _ in range(100):
        if page.evaluate('document.readyState==="complete" && typeof brokerCall==="function"'):
            break
        time.sleep(0.1)
    results['normal'] = page.evaluate('brokerCall([100,200,300,400,500,600])')
    results['page_before_control'] = page.evaluate(
        '({plaintextCaptures:pageDecryptCaptures.length,modelType:typeof model,privateKeyType:typeof privateKey})'
    )
    results['page_export_request'] = page.evaluate('brokerCall([100,200,300,400,500,600],"export")')
    results['hook_positive_control'] = page.evaluate('hookControl()')
    current = targets(45915)
    results['targets'] = [{k: t.get(k) for k in ['id', 'type', 'url']} for t in current]
    worker_target = next(
        t for t in current if t['type'] == 'service_worker' and t['url'].endswith('/worker.js')
    )
    worker = CDP(worker_target['webSocketDebuggerUrl'])
    worker.command('Debugger.enable')
    worker.command('Runtime.enable')
    recovered = worker.evaluate('model')
    results['recovered_model'] = recovered
    results['private_key_export'] = worker.evaluate(
        'crypto.subtle.exportKey("jwk",privateKey).then(()=>"unexpected export",e=>e.name)'
    )
    source_records = []
    for e in worker.events[:]:
        if e.get('method') == 'Debugger.scriptParsed' and e['params'].get('url', '').endswith(
            '/worker.js'
        ):
            src = worker.command('Debugger.getScriptSource', {'scriptId': e['params']['scriptId']})[
                'scriptSource'
            ]
            (out / 'recovered-worker.js').write_text(src, encoding='utf-8')
            source_records.append(
                {
                    'url': e['params']['url'],
                    'bytes': len(src.encode()),
                    'sha256': hashlib.sha256(src.encode()).hexdigest(),
                }
            )
    results['script_source'] = source_records
    ground = json.loads((ROOT / 'evidence/ground-truth.json').read_text())

    def clone(input):
        total = 0
        for tree in recovered['trees']:
            node = tree
            while 'value' not in node:
                node = (
                    node['left'] if input[node['feature']] <= node['threshold'] else node['right']
                )
            total += node['value']
        score = total // len(recovered['trees'])
        return {
            'score': score,
            'band': 'low' if score < 350 else 'medium' if score < 650 else 'high',
        }

    results['offline_clone'] = {
        'matches': sum(clone(v['input']) == v['output'] for v in ground['vectors']),
        'total': len(ground['vectors']),
        'model_bytes': len(json.dumps(recovered, separators=(',', ':')).encode()),
    }
    results['mutation'] = worker.evaluate(
        'evaluateModel = function(){return {score:-777,band:"operator-modified"}}; "replacement installed"'
    )
    results['after_mutation'] = page.evaluate('brokerCall([100,200,300,400,500,600])')
    page.command('Page.captureScreenshot', {'format': 'png'})
    worker.close()
    page.command('Browser.close')
    page.close()
    results['outcome'] = 'complete'
except Exception as error:
    results['error'] = repr(error)
    results['outcome'] = 'failed'
    raise
finally:
    (out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=15)
    event(
        'observation' if results.get('outcome') == 'complete' else 'failure',
        'P201',
        'I preserved the actual worker-debugging run and its terminal state.',
        [str((out / 'results.json').relative_to(ROOT))],
        outcome=results.get('outcome'),
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in results.items()
                if k not in ['recovered_model', 'launch_command', 'targets']
            },
            indent=2,
        )
    )
