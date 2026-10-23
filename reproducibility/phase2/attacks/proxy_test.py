"""P207: combine copied public assets with an online proxy and a bounded offline output cache.
All accounts and services are owned fixtures. An accepted credentialed request is authorized reuse,
not an authorization bypass or recovery of backend source.
"""

from cdp import *
import random, traceback, hashlib

NODE = 'node'
out = ROOT / 'evidence' / ('proxy-' + str(time.time_ns()))
out.mkdir()
archive = ROOT / 'evidence/capture-guarded-1792348636401144700/archive'
report = {'hypothesis': __doc__}
server = proxy = browser = page = None
logs = []


def fetch_json(url, value=None, headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(value).encode() if value is not None else None,
        headers={'Content-Type': 'application/json', **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req) as response:
            return {'status': response.status, 'body': json.load(response)}
    except urllib.error.HTTPError as error:
        return {'status': error.code, 'body': json.load(error)}


try:
    for port in [45911, 45912, 45915, 45920]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    for name, command in [
        ('original', [NODE, str(ROOT / 'websites/suite.mjs')]),
        ('proxy', [NODE, str(ROOT / 'attacks/online_proxy.mjs'), str(archive)]),
    ]:
        log = (out / (name + '.log')).open('w')
        logs.append(log)
        p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        if name == 'original':
            server = p
            url = 'http://127.0.0.1:45911/environment'
        else:
            proxy = p
            url = 'http://127.0.0.1:45920/clone/metrics'
        for _ in range(100):
            try:
                urllib.request.urlopen(url)
                break
            except Exception:
                time.sleep(0.1)
    report['forgedOriginWithoutSession'] = fetch_json(
        'http://127.0.0.1:45911/api/execute', {}, {'Origin': 'http://127.0.0.1:45911'}
    )
    browser, log, _ = browser_launch(out, False)
    logs.append(log)
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Network.enable')
    page.command('Page.navigate', {'url': 'http://127.0.0.1:45920/suite/plain/'})
    for _ in range(100):
        if page.evaluate('document.body?.dataset.ready==="true"'):
            break
        time.sleep(0.05)
    report['clonePage'] = page.evaluate(
        '({url:location.href,title:document.title,mode:research.mode})'
    )
    report['proxyWithoutSession'] = page.evaluate(
        'fetch("/api/execute",{method:"POST",credentials:"omit",headers:{"Content-Type":"application/json"},body:"{}"}).then(async r=>({status:r.status,body:await r.json()}))'
    )
    page.evaluate('research.login("alice","Research-Alice-Only")')
    rng = random.Random(207)
    vectors = [[rng.randrange(1001) for _ in range(6)] for _ in range(100)]
    observed = page.evaluate(
        '(async()=>{const rows=[];for(const input of '
        + json.dumps(vectors)
        + ')rows.push((await research.calculate("score",input)).result);return rows;})()'
    )
    source = "import{fixtureModel,evaluateModel}from'./phase2/websites/workload.mjs';let raw='';for await(const p of process.stdin)raw+=p;const m=fixtureModel();console.log(JSON.stringify(JSON.parse(raw).map(x=>evaluateModel(m,x))));"
    truth = json.loads(
        subprocess.check_output(
            [NODE, '--input-type=module', '-e', source],
            input=json.dumps(vectors).encode(),
            cwd=str(ROOT.parent),
        )
    )
    report['onlineClone'] = {
        'matches': sum(a == b for a, b in zip(observed, truth)),
        'total': len(truth),
        'backendSourceRecovered': False,
    }
    report['route'] = page.evaluate('research.calculate("route",{start:0,end:17,congestion:3})')
    report['freshConcurrent'] = page.evaluate(
        'Promise.all(Array.from({length:20},()=>research.calculate("score",[100,200,300,400,500,600]).then(v=>({ok:true,result:v.result}),e=>({error:e.message}))))'
    )
    # Stateful operations pass through independent public-protocol code and remain owned by the original account.
    report['workflow'] = page.evaluate(
        '''(async()=>{const state=await research.request('/api/state'),held=await research.calculate('reserve',{product:'P01',quantity:1,expectedVersion:state.version}),requestId=crypto.randomUUID(),payload={op:'commit',input:{id:held.result.reservation.id},requestId};return {held,commit:await research.execute(payload),retry:await research.execute(payload)};})()'''
    )
    page.evaluate('research.login("bob","Research-Bob-Only")')
    report['quota'] = page.evaluate(
        '''(async()=>{const rows=[];for(let i=0;i<13;i++)rows.push(await research.calculate('score',[100,200,300,400,500,600]).then(v=>({status:200,remaining:v.remaining}),e=>({status:e.status,error:e.message})));return rows;})()'''
    )
    page.evaluate('research.login("bob","Research-Bob-Only")')
    report['quotaNewSession'] = page.evaluate(
        'research.calculate("score",[100,200,300,400,500,600]).then(v=>({unexpected:v}),e=>({status:e.status,error:e.message}))'
    )
    report['proxyMetricsOnline'] = fetch_json('http://127.0.0.1:45920/clone/metrics')
    report['screenshotBytes'] = len(
        __import__('base64').b64decode(
            page.command('Page.captureScreenshot', {'format': 'png'})['data']
        )
    )
    server.terminate()
    server.wait(timeout=8)
    server = None
    cached = [
        fetch_json('http://127.0.0.1:45920/clone/cached-score', {'input': v}) for v in vectors
    ]
    report['offlineCache'] = {
        'matches': sum(
            v['status'] == 200 and v['body'].get('result') == t for v, t in zip(cached, truth)
        ),
        'total': len(truth),
    }
    report['uncachedOffline'] = fetch_json(
        'http://127.0.0.1:45920/clone/cached-score', {'input': [1000, 1, 1000, 1, 1000, 1]}
    )
    report['normalOfflineRequest'] = page.evaluate(
        'research.calculate("route",{start:7,end:22,congestion:11}).then(v=>({unexpected:v}),e=>({status:e.status,error:e.message}))'
    )
    report['requestURLs'] = [
        e['params']['request']['url']
        for e in page.events
        if e.get('method') == 'Network.requestWillBeSent'
    ]
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
    for p in [server, proxy]:
        if p:
            p.terminate()
            p.wait(timeout=8)
    for log in logs:
        log.close()
    (out / 'results.json').write_text(json.dumps(report, indent=2))
    compact = {
        k: v
        for k, v in report.items()
        if k not in ['freshConcurrent', 'requestURLs', 'quota', 'workflow']
    }
    compact['directory'] = str(out)
    if 'quota' in report:
        compact['quotaStatuses'] = [r['status'] for r in report['quota']]
    if 'freshConcurrent' in report:
        compact['concurrentAccepted'] = sum(r.get('ok', False) for r in report['freshConcurrent'])
    if 'workflow' in report:
        compact['commitRetryCached'] = report['workflow']['retry'].get('cached')
    print(json.dumps(compact, indent=2))
if report.get('outcome') != 'complete':
    raise SystemExit(1)
