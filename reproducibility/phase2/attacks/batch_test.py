"""P208: amortize lease issuance while preserving a separate bound signature and nonce per operation."""

from cdp import *
import statistics, traceback

NODE = 'node'
out = ROOT / 'evidence' / ('batch-' + str(time.time_ns()))
out.mkdir()
report = {'hypothesis': __doc__}
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
    report['checks'] = page.evaluate(
        '''(async()=>{
 const p=()=>({op:'score',input:[100,200,300,400,500,600],requestId:crypto.randomUUID()}),capture=promise=>promise.then(v=>({status:200,value:v}),e=>({status:e.status,error:e.message})),r={};
 r.empty=await capture(research.request('/api/challenges',{hashes:[]}));r.oversized=await capture(research.request('/api/challenges',{hashes:Array(17).fill('0'.repeat(64))}));
 const prepared=await research.prepareBatch(Array.from({length:16},p));r.tampered=await capture(research.request('/api/execute',{...prepared[0],payload:{...prepared[0].payload,input:[1,2,3,4,5,6]}}));
 r.valid=await Promise.all(prepared.map(v=>capture(research.request('/api/execute',v))));r.replay=await capture(research.request('/api/execute',prepared[0]));
 const outstanding=[];for(let i=0;i<4;i++)outstanding.push(...await research.prepareBatch(Array.from({length:16},p)));r.cap=await capture(research.prepareBatch([p()]));r.concurrent64=await Promise.all(outstanding.map(v=>capture(research.request('/api/execute',v))));
 const expired=await research.prepareBatch([p()]);await new Promise(resolve=>setTimeout(resolve,1650));r.expired=await capture(research.request('/api/execute',expired[0]));
 const retired=await research.prepareBatch([p()]);await research.rotate();r.retired=await capture(research.request('/api/execute',retired[0]));r.recovery=await research.calculate('score',[100,200,300,400,500,600]);return r;
 })()'''
    )
    report['benchmark'] = page.evaluate(
        '''(async()=>{
 performance.setResourceTimingBufferSize(20000);const report={individual:[],batch:[],callsPerSample:16};
 for(let round=0;round<35;round++)for(const mode of round%2?['batch','individual']:['individual','batch']){
  const rows=Array.from({length:16},()=>({op:'score',input:[100,200,300,400,500,600],requestId:crypto.randomUUID()})),measurement=await research.request('/api/metrics/start',{}),before=performance.now();
  if(mode==='batch'){for(const envelope of await research.prepareBatch(rows)){const v=await research.request('/api/execute',envelope);if(v.result.score!==522)throw Error('Wrong batch output');}}
  else for(const payload of rows){const v=await research.execute(payload);if(v.result.score!==522)throw Error('Wrong individual output');}
  const ms=performance.now()-before,service=await research.request('/api/metrics/stop',measurement);if(round>=5)report[mode].push({ms,service});
 }
 report.resourceTimings=performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/')&&!r.name.includes('/metrics/')).map(r=>({name:r.name,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize}));return report;
 })()'''
    )
    report['benchmark']['summary'] = {
        mode: {
            'n': len(report['benchmark'][mode]),
            'medianBatchMs': statistics.median(r['ms'] for r in report['benchmark'][mode]),
            'p95BatchMs': sorted(r['ms'] for r in report['benchmark'][mode])[28],
            'applicationRequestsPer16': 32 if mode == 'individual' else 17,
            'nodeCpuMs': sum(
                r['service']['cpuUserMs'] + r['service']['cpuSystemMs']
                for r in report['benchmark'][mode]
            ),
        }
        for mode in ['individual', 'batch']
    }
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
    checks = report.get('checks', {})
    print(
        json.dumps(
            {
                'directory': str(out),
                'outcome': report.get('outcome'),
                'error': report.get('error'),
                'valid': sum(r['status'] == 200 for r in checks.get('valid', [])),
                'concurrent64': sum(r['status'] == 200 for r in checks.get('concurrent64', [])),
                'negative': {k: v for k, v in checks.items() if k not in ['valid', 'concurrent64']},
                'benchmark': report.get('benchmark', {}).get('summary'),
            },
            indent=2,
        )
    )
if report.get('outcome') != 'complete':
    raise SystemExit(1)
