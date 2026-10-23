"""P203: test execution in the real browser parent and distinguish page isolation from owner control."""

import shutil

from pathlib import Path
import sys, json, time, os, subprocess, socket, urllib.request, traceback, statistics, random
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.remote.client_config import ClientConfig
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
mode = sys.argv[1] if len(sys.argv) > 1 else 'guarded'
out = ROOT / 'evidence' / ('component-' + mode + '-' + str(time.time_ns()))
out.mkdir()
NODE = 'node'
report = {'mode': mode, 'hypothesis': __doc__}
driver = server = service = None
api = '''window.nativeCall=(input,op="evaluate")=>new Promise((resolve,reject)=>{const id=crypto.randomUUID(),timer=setTimeout(()=>{removeEventListener("ResearchResult",listener);reject(Error("Browser component timeout"));},5000);function listener(e){const v=JSON.parse(e.detail);if(v.id===id){clearTimeout(timer);removeEventListener("ResearchResult",listener);resolve(v.response);}}addEventListener("ResearchResult",listener);dispatchEvent(new CustomEvent("ResearchInvoke",{detail:JSON.stringify({id,op,input})}));});'''
serverLog = (out / 'server.log').open('w')


def call(op='evaluate', input=None):
    return driver.execute_async_script(
        'const done=arguments[arguments.length-1];nativeCall(arguments[0],arguments[1]).then(done,e=>done({error:e.message}));',
        input or [100, 200, 300, 400, 500, 600],
        op,
    )


try:
    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    env = os.environ.copy()
    env['P2_RESEARCH_CREDENTIAL'] = json.loads(
        (ROOT / 'protections/extension/config.js').read_text().split('=', 1)[1].strip().rstrip(';')
    )
    server = subprocess.Popen(
        [NODE, str(ROOT / 'websites/server.mjs')],
        stdout=serverLog,
        stderr=subprocess.STDOUT,
        env=env,
    )
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:45911/worker-test/')
            break
        except Exception:
            time.sleep(0.1)
    options = Options()
    options.binary_location = str(
        ROOT
        / (
            'browser/waterfox-owner/waterfox.exe'
            if mode == 'owner'
            else 'browser/waterfox-broker/waterfox.exe'
        )
    )
    options.add_argument('-headless')
    options.set_preference('browser.shell.checkDefaultBrowser', False)
    options.set_preference('browser.privateWindowSeparation.enabled', False)
    options.set_capability('acceptInsecureCerts', False)
    service = Service(
        os.environ.get('GECKODRIVER', shutil.which('geckodriver') or 'geckodriver.exe'),
        service_args=['--allow-system-access'] if mode == 'debug' else [],
        log_output=str(out / 'driver.log'),
    )
    service.start()
    start = time.perf_counter()
    driver = webdriver.Remote(
        command_executor=service.service_url,
        options=options,
        client_config=ClientConfig(remote_server_addr=service.service_url, timeout=35),
    )
    report['browserStartupMs'] = (time.perf_counter() - start) * 1000
    driver.set_script_timeout(12)
    driver.set_page_load_timeout(25)
    driver.command_executor._commands['P2_SET_CONTEXT'] = (
        'POST',
        '/session/$sessionId/moz/context',
    )
    report['capabilities'] = {
        k: driver.capabilities.get(k)
        for k in [
            'browserVersion',
            'browserName',
            'moz:processID',
            'moz:geckodriverVersion',
            'acceptInsecureCerts',
        ]
    }
    for port in [45911, 45912]:
        driver.get(f'http://127.0.0.1:{port}/native-test/')
        driver.execute_script(api)
        start = time.perf_counter()
        normal = call()
        report[str(port)] = {'normal': normal, 'firstCallMs': (time.perf_counter() - start) * 1000}
        report[str(port)].update(
            {
                'export': call('export'),
                'page': driver.execute_script('return pageHookSnapshot();'),
                'hookControl': driver.execute_async_script(
                    'hookControl().then(arguments[arguments.length-1]);'
                ),
            }
        )
        report[str(port)]['resourceRead'] = driver.execute_async_script(
            'const done=arguments[arguments.length-1];fetch("resource://copyresistance/Broker.sys.mjs").then(r=>r.text()).then(t=>done({read:true,characters:t.length}),e=>done({read:false,error:e.name}));'
        )
        report[str(port)]['fetchPositiveControl'] = driver.execute_async_script(
            'const done=arguments[arguments.length-1];fetch("/page.js").then(r=>r.text()).then(t=>done({read:true,characters:t.length}),e=>done({read:false,error:e.name}));'
        )
    if report['45911']['normal'].get('ok'):
        driver.get('http://127.0.0.1:45911/native-test/')
        driver.execute_script(api)
        driver.find_element('id', 'calculate').click()
        WebDriverWait(driver, 8).until(lambda d: '522' in d.find_element('id', 'result').text)
        report['ordinaryButton'] = driver.find_element('id', 'result').text
        driver.execute_script('document.querySelector("#result").textContent="";')
        driver.find_element('id', 'calculate').send_keys('\ue007')
        WebDriverWait(driver, 8).until(lambda d: '522' in d.find_element('id', 'result').text)
        report['ordinaryKeyboard'] = driver.find_element('id', 'result').text
        vectors = json.loads((ROOT / 'evidence/ground-truth.json').read_text())['vectors']
        observed = driver.execute_async_script(
            'const inputs=arguments[0],done=arguments[arguments.length-1];(async()=>{const values=[];for(const input of inputs)values.push(await nativeCall(input));return values;})().then(done,e=>done({error:e.message}));',
            [v['input'] for v in vectors],
        )
        report['normalHeldout'] = {
            'total': len(vectors),
            'matches': sum(
                v.get('result') == expected['output'] for v, expected in zip(observed, vectors)
            ),
        }
        report['warmSamplesMs'] = driver.execute_async_script(
            '''const done=arguments[arguments.length-1];(async()=>{const rows=[];for(let i=0;i<70;i++){const start=performance.now(),v=await nativeCall([100,200,300,400,500,600]);if(v.result.score!==522)throw Error('Wrong component output');if(i>=10)rows.push(performance.now()-start);}return rows;})().then(done,e=>done({error:e.message}));'''
        )
        # Direct frame calls and indirect access through its same-origin parent differ.
        driver.execute_script(
            'const f=document.createElement("iframe");f.src="/native-test/";f.title="Local context check";document.body.appendChild(f);'
        )
        WebDriverWait(driver, 8).until(
            lambda d: d.execute_script(
                'return !!document.querySelector("iframe").contentWindow?.nativeBrokerCall;'
            )
        )
        driver.switch_to.frame(0)
        driver.execute_script(api)
        report['frame'] = call()
        report['sameOriginFrameThroughParent'] = driver.execute_async_script(
            'const done=arguments[arguments.length-1];parent.nativeBrokerCall([100,200,300,400,500,600]).then(done,e=>done({error:e.message}));'
        )
        driver.switch_to.default_content()
        driver.execute_script(
            'const f=document.createElement("iframe");f.src="http://127.0.0.1:45912/native-test/";f.title="Cross-origin control";document.body.appendChild(f);'
        )
        WebDriverWait(driver, 8).until(
            lambda d: d.execute_script('return document.querySelectorAll("iframe").length===2;')
        )
        driver.switch_to.frame(1)
        report['crossOriginFrameParentAccess'] = driver.execute_script(
            'try{return {allowed:typeof parent.nativeBrokerCall};}catch(e){return {error:e.name};}'
        )
        driver.execute_script(api)
        report['crossOriginFrameDirect'] = call()
        driver.switch_to.default_content()
        if mode == 'debug':
            uri = 'resource://copyresistance/Broker.sys.mjs'
            driver.execute('P2_SET_CONTEXT', {'context': 'chrome'})
            report['configuration'] = driver.execute_script(
                'return Cc["@mozilla.org/preferences-service;1"].getService(Ci.nsIPrefBranch).getStringPref("research.component.status","absent");'
            )
            report['recoveredModel'] = driver.execute_script(
                'return ChromeUtils.importESModule(arguments[0]).Broker.program;', uri
            )
            report['runtimeMutation'] = driver.execute_script(
                'ChromeUtils.importESModule(arguments[0]).Broker.evaluate=()=>({score:-888,band:"owner-runtime"});return true;',
                uri,
            )
            driver.execute('P2_SET_CONTEXT', {'context': 'content'})
            report['afterMutation'] = call()
        recovered = report.get('recoveredModel') or report['45911']['export'].get('program')
        if recovered:
            reference = json.loads((ROOT / 'evidence/ground-truth.json').read_text())['model']
            rng = random.Random(18092026)

            def score(model, input):
                total = 0
                for tree in model['trees']:
                    while 'value' not in tree:
                        tree = (
                            tree['left']
                            if input[tree['feature']] <= tree['threshold']
                            else tree['right']
                        )
                    total += tree['value']
                return total // len(model['trees'])

            matches = 0
            for _ in range(1000):
                vector = [rng.randrange(1001) for _ in range(6)]
                matches += score(reference, vector) == score(recovered, vector)
            report['offlineClone'] = {
                'matches': matches,
                'total': 1000,
                'modelBytes': len(json.dumps(recovered, separators=(',', ':'))),
            }
        # Send read-only requests to the author-owned live target.
        driver.get('https://emilvaliyev.com/')
        report['liveCompatibility'] = {
            'title': driver.title,
            'url': driver.current_url,
            'headings': driver.execute_script(
                'return [...document.querySelectorAll("h1,h2")].map(x=>x.textContent.trim());'
            ),
            'textCharacters': len(driver.find_element('tag name', 'body').text),
        }
    report['outcome'] = 'complete'
except Exception as error:
    report['outcome'] = 'failed'
    report['error'] = repr(error)
    traceback.print_exc()
finally:
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
    if service:
        service.stop()
    if server:
        server.terminate()
        server.wait(timeout=8)
    serverLog.close()
    (out / 'results.json').write_text(json.dumps(report, indent=2))
    compact = {k: v for k, v in report.items() if k not in ['recoveredModel', 'warmSamplesMs']}
    compact = json.loads(json.dumps(compact))
    compact['directory'] = str(out)
    for key in ['45911', '45912']:
        if 'program' in compact.get(key, {}).get('export', {}):
            compact[key]['export']['program'] = {
                'modelId': compact[key]['export']['program']['id'],
                'trees': len(compact[key]['export']['program']['trees']),
            }
    if isinstance(report.get('warmSamplesMs'), list):
        compact['warmMedianMs'] = statistics.median(report['warmSamplesMs'])
    print(json.dumps(compact, indent=2))
if report.get('outcome') != 'complete':
    sys.exit(1)
