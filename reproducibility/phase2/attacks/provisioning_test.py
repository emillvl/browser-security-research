"""P206: approved-recipient provisioning, issuer authentication, rotation, revocation and owner recovery.
Administrator approval is a separate trusted authority. It does not attest an honest browser.
"""

from cdp import *
import os, secrets, shutil, hashlib, statistics, random, traceback

NODE = 'node'
out = ROOT / 'evidence' / ('provisioning-' + str(time.time_ns()))
out.mkdir()
admin = secrets.token_hex(32)
report = {'hypothesis': __doc__}
server = browser = page = worker = None
logs = []


def post(path, value, administrator=False):
    headers = {'Content-Type': 'application/json'}
    if administrator:
        headers['Authorization'] = 'Bearer ' + admin
    request = urllib.request.Request(
        'http://127.0.0.1:45911' + path, data=json.dumps(value).encode(), headers=headers
    )
    try:
        with urllib.request.urlopen(request) as response:
            return {'status': response.status, 'body': json.load(response)}
    except urllib.error.HTTPError as error:
        return {'status': error.code, 'body': json.load(error)}


def fingerprint(key):
    return hashlib.sha256((key['x'] + '|' + key['y']).encode()).hexdigest()


def navigate(port=45911):
    page.evaluate('if(document.body)document.body.dataset.p2Ready="old"')
    page.command('Page.navigate', {'url': f'http://127.0.0.1:{port}/broker-v2/'})
    for _ in range(100):
        if page.evaluate(
            'document.readyState==="complete"&&typeof brokerCall==="function"&&document.body?.dataset.p2Ready!=="old"&&document.documentElement.dataset.p2ExtensionReady==="true"'
        ):
            return
        time.sleep(0.05)
    raise RuntimeError('Page did not become ready')


def call():
    return page.evaluate('brokerCall([100,200,300,400,500,600])')


try:
    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    env = os.environ.copy()
    env['P2_ADMIN_TOKEN'] = admin
    log = (out / 'server.log').open('w')
    logs.append(log)
    server = subprocess.Popen(
        [NODE, str(ROOT / 'websites/provisioning.mjs')],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:45911/broker-v2/')
            break
        except Exception:
            time.sleep(0.1)
    package = out / 'extension'
    shutil.copytree(ROOT / 'protections/extension-v2', package)
    browser, log, command = browser_launch(out, True, extension_path=package)
    logs.append(log)
    report['launch'] = command
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Network.enable')
    navigate()
    report['beforeApproval'] = call()
    report['browser'] = page.command('Browser.getVersion')
    worker = CDP(
        next(
            t['webSocketDebuggerUrl']
            for t in targets(45915)
            if t['type'] == 'service_worker' and t['url'].endswith('/worker.js')
        )
    )
    worker.command('Runtime.enable')
    worker.command('Network.enable')
    key = worker.evaluate('publicKey')
    identity = fingerprint(key)
    credential = json.loads(
        (package / 'config.js').read_text().splitlines()[0].split('=', 1)[1].strip().rstrip(';')
    )
    other = page.evaluate(
        '(async()=>{const p=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},false,["deriveKey"]);return crypto.subtle.exportKey("jwk",p.publicKey);})()'
    )
    report['wrongCredential'] = post(
        '/api/enroll', {'credential': 'invalid-research-value', 'publicKey': other}
    )
    report['copiedCredentialUnapprovedKey'] = post(
        '/api/enroll', {'credential': credential, 'publicKey': other}
    )
    report['unapprovedCapsule'] = post('/api/capsule', {'publicKey': other})
    report['unauthorizedApproval'] = post('/admin/approve', {'fingerprint': fingerprint(other)})
    report['approval'] = post('/admin/approve', {'fingerprint': identity}, True)
    report['normal'] = call()
    report['pageIsolation'] = page.evaluate('pageHookSnapshot()')
    report['hookControl'] = page.evaluate('hookControl()')
    report['privateKeyExport'] = worker.evaluate(
        'crypto.subtle.exportKey("jwk",privateKey).then(()=>"unexpected",e=>e.name)'
    )
    report['exportOperation'] = page.evaluate('brokerCall([],"export")')
    old = worker.evaluate('lastCapsule')
    (out / 'first-capsule.json').write_text(json.dumps(old))
    tampered = json.loads(json.dumps(old))
    encoded = tampered['ciphertext']
    tampered['ciphertext'] = ('B' if encoded[0] != 'B' else 'C') + encoded[1:]
    report['tamperedCapsule'] = worker.evaluate(
        'installCapsule(' + json.dumps(tampered) + ').then(()=>"unexpected",e=>e.message)'
    )
    report['publish'] = post('/admin/publish', {'version': 2}, True)
    report['refreshV2'] = worker.evaluate('refresh()')
    report['newVersion'] = call()
    report['rollback'] = worker.evaluate(
        'installCapsule(' + json.dumps(old) + ').then(()=>"unexpected",e=>e.message)'
    )
    model = worker.evaluate('model')
    (out / 'recovered-v2-model.json').write_text(json.dumps(model))
    report['revoke'] = post('/admin/revoke', {'fingerprint': identity}, True)
    report['withinLeaseAfterRevoke'] = call()
    time.sleep(1.3)
    report['afterLeaseAfterRevoke'] = call()
    report['revokedCapsule'] = post('/api/capsule', {'publicKey': key})
    report['cachedModelStillReadable'] = worker.evaluate('({id:model.id,trees:model.trees.length})')
    worker.evaluate('rotateKeys().then(()=>true)')
    report['afterUnapprovedRotation'] = call()
    rotated = worker.evaluate('publicKey')
    report['changedRecipient'] = fingerprint(rotated) != identity
    post('/admin/approve', {'fingerprint': fingerprint(rotated)}, True)
    report['approvedRotation'] = call()
    # A complete clean browser restart tests persisted CryptoKey state and normal startup.
    # Reuse only the profile created by this run; no personal browser is connected.
    worker.close()
    worker = None
    page.command('Browser.close')
    page.close()
    page = None
    browser.wait(timeout=8)
    browser, log, restart_command = browser_launch(
        out, True, extension_path=package, reuse_profile=True
    )
    logs.append(log)
    report['restartProcedure'] = {
        'kind': 'Clean isolated browser process restart',
        'sameProfile': True,
        'command': restart_command,
    }
    page = CDP(next(t['webSocketDebuggerUrl'] for t in targets(45915) if t['type'] == 'page'))
    page.command('Page.enable')
    page.command('Network.enable')
    navigate()
    report['afterWorkerRestart'] = call()
    worker = CDP(
        next(
            t['webSocketDebuggerUrl']
            for t in targets(45915)
            if t['type'] == 'service_worker' and t['url'].endswith('/worker.js')
        )
    )
    worker.command('Runtime.enable')
    worker.command('Network.enable')
    report['restartRetainsRecipient'] = fingerprint(worker.evaluate('publicKey')) == fingerprint(
        rotated
    )
    report['restartedPrivateKeyExport'] = worker.evaluate(
        'crypto.subtle.exportKey("jwk",privateKey).then(()=>"unexpected",e=>e.name)'
    )
    page.evaluate('document.querySelector("#calculate").click()')
    for _ in range(100):
        if page.evaluate('document.querySelector("#result").textContent.length>0'):
            break
        time.sleep(0.05)
    report['ordinaryButton'] = page.evaluate('document.querySelector("#result").textContent')
    report['frame'] = page.evaluate(
        '''(async()=>{const f=document.createElement('iframe');f.src='/broker-v2/';document.body.appendChild(f);await new Promise(r=>f.onload=r);return {direct:await f.contentWindow.brokerCall([100,200,300,400,500,600]),throughParent:await f.contentWindow.eval('parent.brokerCall([100,200,300,400,500,600])')};})()'''
    )
    navigate(45912)
    report['wrongOrigin'] = call()
    navigate()

    # A captured model remains independently usable after revocation; no server or signing key is used here.
    def clone(input):
        total = 0
        for node in model['trees']:
            while 'value' not in node:
                node = (
                    node['left'] if input[node['feature']] <= node['threshold'] else node['right']
                )
            total += node['value']
        return total // len(model['trees'])

    source = "import {fixtureModel,evaluateModel}from './phase2/websites/workload.mjs';let raw='';for await(const p of process.stdin)raw+=p;const m=fixtureModel(12657431);console.log(JSON.stringify(JSON.parse(raw).map(x=>evaluateModel(m,x).score)));"
    rng = random.Random(206)
    vectors = [[rng.randrange(1001) for _ in range(6)] for _ in range(1000)]
    truth = json.loads(
        subprocess.check_output(
            [NODE, '--input-type=module', '-e', source],
            input=json.dumps(vectors).encode(),
            cwd=str(ROOT.parent),
        )
    )
    report['offlineAfterRevocation'] = {
        'matches': sum(clone(v) == t for v, t in zip(vectors, truth)),
        'total': len(vectors),
    }
    # Deliberately declassify a known control model only for the following performance phase.
    page.evaluate(
        'window.controlModel='
        + json.dumps(model)
        + ';window.controlEvaluate=input=>{let total=0;for(let n of controlModel.trees){while(n.value===undefined)n=input[n.feature]<=n.threshold?n.left:n.right;total+=n.value;}return Math.floor(total/controlModel.trees.length);};true'
    )
    report['benchmark'] = {
        'note': 'Same browser and model, after explicit control-model injection. No secrecy claim derives from this phase. Includes 1200-ms renewal policy.',
        'callsPerBatch': 100,
        'page': [],
        'extension': [],
    }
    rng = random.Random(207)
    for _ in range(30):
        order = ['page', 'extension']
        rng.shuffle(order)
        for mode in order:
            before = time.perf_counter()
            value = page.evaluate(
                '(async()=>{let sum=0;for(let i=0;i<100;i++)sum+='
                + (
                    'controlEvaluate([100,200,300,400,500,600])'
                    if mode == 'page'
                    else '(await brokerCall([100,200,300,400,500,600])).result.score'
                )
                + ';return sum;})()'
            )
            report['benchmark'][mode].append((time.perf_counter() - before) * 1000)
            if value != clone([100, 200, 300, 400, 500, 600]) * 100:
                raise RuntimeError('Wrong benchmark output')
    report['benchmark']['summaries'] = {
        mode: {
            'n': 30,
            'medianBatchMs': statistics.median(report['benchmark'][mode]),
            'p95BatchMs': sorted(report['benchmark'][mode])[28],
            'medianPerCallMs': statistics.median(report['benchmark'][mode]) / 100,
        }
        for mode in ['page', 'extension']
    }
    report['pageHeap'] = page.command('Runtime.getHeapUsage')
    report['workerHeap'] = worker.command('Runtime.getHeapUsage')
    report['workerNetwork'] = [
        {
            'url': e['params']['request']['url'],
            'requestBodyBytes': len(e['params']['request'].get('postData', '').encode()),
        }
        for e in worker.events
        if e.get('method') == 'Network.requestWillBeSent'
    ]
    report['outcome'] = 'complete'
except Exception as error:
    report['outcome'] = 'failed'
    report['error'] = repr(error)
    traceback.print_exc()
finally:
    if worker:
        worker.close()
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
    compact = {
        k: v
        for k, v in report.items()
        if k not in ['launch', 'workerNetwork', 'pageHeap', 'workerHeap', 'benchmark']
    }
    compact['directory'] = str(out)
    if 'benchmark' in report:
        compact['benchmark'] = report['benchmark'].get('summaries', {})
    print(json.dumps(compact, indent=2))
if report.get('outcome') != 'complete':
    raise SystemExit(1)
