import shutil
from pathlib import Path
import json, sys, time, os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(
    0, os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[2] / '.doppelgng'))
)
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from log import event

mode = sys.argv[1] if len(sys.argv) > 1 else 'guarded'
out = ROOT / 'evidence' / ('browser-' + mode + '-' + str(time.time_ns()))
out.mkdir()
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
if mode == 'debug':
    options.add_argument('--allow-system-access')
results = {'mode': mode}
driver = None
event(
    'hypothesis',
    'P203',
    'I will test the real privileged parent broker, origin/context enforcement, page instrumentation and operator removal of the guard as separate outcomes.',
    [str(out.relative_to(ROOT))],
    mode=mode,
)
native_api = '''window.nativeCall=(input,op="evaluate")=>new Promise((resolve,reject)=>{const id=crypto.randomUUID(),timer=setTimeout(()=>{removeEventListener("ResearchResult",listener);reject(Error("Native broker timeout"));},8000);function listener(e){const value=JSON.parse(e.detail);if(value.id===id){clearTimeout(timer);removeEventListener("ResearchResult",listener);resolve(value.response);}}addEventListener("ResearchResult",listener);dispatchEvent(new CustomEvent("ResearchInvoke",{detail:JSON.stringify({id,op,input})}));});'''
try:
    driver = webdriver.Firefox(
        options=options,
        service=Service(
            os.environ.get('GECKODRIVER', shutil.which('geckodriver') or 'geckodriver.exe'),
            log_output=str(out / 'driver.log'),
        ),
    )
    driver.set_script_timeout(20)
    results['capabilities'] = {
        k: driver.capabilities.get(k)
        for k in ['browserVersion', 'moz:geckodriverVersion', 'browserName']
    }
    for port in [45911, 45912]:
        driver.get(f'http://127.0.0.1:{port}/worker-test/')
        driver.execute_script(native_api)

        def call(op='evaluate'):
            return driver.execute_async_script(
                'const done=arguments[arguments.length-1];nativeCall([100,200,300,400,500,600],arguments[0]).then(done,e=>done({error:e.message}));',
                op,
            )

        results[str(port)] = {
            'normal': call(),
            'export': call('export'),
            'page': driver.execute_script(
                'return {plaintextCaptures:pageDecryptCaptures.length,chromeUtilsType:typeof ChromeUtils,brokerType:typeof Broker}'
            ),
            'hookControl': driver.execute_async_script(
                'hookControl().then(arguments[arguments.length-1]);'
            ),
        }
        driver.save_screenshot(str(out / f'{port}.png'))
    if mode == 'debug':
        driver.set_context('chrome')
        results['owner_recovered_model'] = driver.execute_script(
            'return ChromeUtils.importESModule("resource://copyresistance/Broker.sys.mjs").Broker.program;'
        )
        results['owner_changed_runtime'] = driver.execute_script(
            'ChromeUtils.importESModule("resource://copyresistance/Broker.sys.mjs").Broker.evaluate=()=>({score:-888,band:"owner-runtime"});return true;'
        )
        driver.set_context('content')
    results['outcome'] = 'complete'
except Exception as error:
    results['error'] = repr(error)
    results['outcome'] = 'failed'
    raise
finally:
    (out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    if driver:
        driver.quit()
    event(
        'observation' if results.get('outcome') == 'complete' else 'failure',
        'P203',
        'I saved the browser-component run, including normal results and failure state.',
        [str((out / 'results.json').relative_to(ROOT))],
        mode=mode,
        outcome=results.get('outcome'),
    )
    print(json.dumps({k: v for k, v in results.items() if k != 'owner_recovered_model'}, indent=2))
