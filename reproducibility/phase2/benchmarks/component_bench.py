"""Matched timing comparison on the same disposable browser and model.
The benchmark deliberately publishes a plaintext control model; it is not a secrecy test.
Native calls include the real page-to-parent IPC. Both batch timings include one WebDriver round trip.
"""

import shutil

from pathlib import Path
import sys, json, time, subprocess, os, socket, urllib.request, random, statistics, ctypes
from ctypes import wintypes
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'evidence' / ('component-benchmark-' + str(time.time_ns()))
out.mkdir()
sys.path.insert(0, str(ROOT / 'attacks'))
NODE = 'node'
api = '''window.nativeCall=input=>new Promise((resolve,reject)=>{const id=crypto.randomUUID(),timer=setTimeout(()=>{removeEventListener("ResearchResult",listener);reject(Error("Component timeout"));},5000);function listener(e){const v=JSON.parse(e.detail);if(v.id===id){clearTimeout(timer);removeEventListener("ResearchResult",listener);resolve(v.response);}}addEventListener("ResearchResult",listener);dispatchEvent(new CustomEvent("ResearchInvoke",{detail:JSON.stringify({id,op:"evaluate",input})}));});'''
report = {
    'method': __doc__,
    'samples': {'page': [], 'parent': []},
    'callsPerBatch': 500,
    'pairedOrder': [],
}
driver = server = None
logs = []


def summary(rows):
    rows = sorted(rows)
    return {
        'n': len(rows),
        'medianBatchMs': statistics.median(rows),
        'p95BatchMs': rows[int(0.95 * len(rows) + 0.999) - 1],
        'medianPerCallMs': statistics.median(rows) / report['callsPerBatch'],
    }


def process_metrics(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x400 | 0x10, False, pid)
    if not handle:
        return {'unavailable': ctypes.get_last_error()}
    try:
        values = [wintypes.FILETIME() for _ in range(4)]
        okay = kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in values])
        result = {}
        if okay:
            result = {
                'kernelMs': ((values[2].dwHighDateTime << 32) | values[2].dwLowDateTime) / 10000,
                'userMs': ((values[3].dwHighDateTime << 32) | values[3].dwLowDateTime) / 10000,
            }

        class Memory(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in [
                    'PeakWorkingSetSize',
                    'WorkingSetSize',
                    'QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage',
                    'QuotaPeakNonPagedPoolUsage',
                    'QuotaNonPagedPoolUsage',
                    'PagefileUsage',
                    'PeakPagefileUsage',
                    'PrivateUsage',
                ]
            ]

        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        kernel.K32GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Memory),
            wintypes.DWORD,
        ]
        if kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            result.update(workingSetBytes=memory.WorkingSetSize, privateBytes=memory.PrivateUsage)
        return result
    finally:
        kernel.CloseHandle(handle)


try:
    for port in [45911, 45912]:
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    env = os.environ.copy()
    env['P2_BENCHMARK'] = '1'
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
    options = Options()
    options.binary_location = str(ROOT / 'browser/waterfox-broker/waterfox.exe')
    options.add_argument('-headless')
    options.set_preference('browser.privateWindowSeparation.enabled', False)
    options.set_preference('browser.shell.checkDefaultBrowser', False)
    options.set_capability('acceptInsecureCerts', False)
    start = time.perf_counter()
    driver = webdriver.Firefox(
        options=options,
        service=Service(
            os.environ.get('GECKODRIVER', shutil.which('geckodriver') or 'geckodriver.exe'),
            log_output=str(out / 'driver.log'),
        ),
    )
    report['startupMs'] = (time.perf_counter() - start) * 1000
    driver.set_script_timeout(25)
    report['browserVersion'] = driver.capabilities['browserVersion']
    report['parentPid'] = driver.capabilities['moz:processID']
    driver.get('http://127.0.0.1:45911/worker-test/')
    driver.execute_script(api)
    start = time.perf_counter()
    normal = driver.execute_async_script(
        'nativeCall([100,200,300,400,500,600]).then(arguments[arguments.length-1]);'
    )
    report['parentInitializationMs'] = (time.perf_counter() - start) * 1000
    assert normal['result']['score'] == 522
    start = time.perf_counter()
    control = driver.execute_async_script(
        '''const done=arguments[arguments.length-1];fetch('/benchmark/model').then(r=>r.json()).then(model=>{window.controlEvaluate=input=>{let sum=0;for(const tree of model.trees){let n=tree;while(n.value===undefined)n=input[n.feature]<=n.threshold?n.left:n.right;sum+=n.value;}const score=Math.floor(sum/model.trees.length);return{score,band:score<350?'low':score<650?'medium':'high'};};done({bytes:JSON.stringify(model).length,result:controlEvaluate([100,200,300,400,500,600])});});'''
    )
    report['pageInitializationMs'] = (time.perf_counter() - start) * 1000
    report['control'] = control
    # Warm both paths, then alternate their order deterministically within each pair.
    script = '''const mode=arguments[0],count=arguments[1],done=arguments[arguments.length-1];(async()=>{let checksum=0;for(let i=0;i<count;i++){const input=[100,200,300,400,500,600],v=mode==='parent'?(await nativeCall(input)).result:await Promise.resolve(controlEvaluate(input));checksum+=v.score;}return checksum;})().then(done,e=>done({error:e.message}));'''
    for mode in ['page', 'parent']:
        assert driver.execute_async_script(script, mode, 100) == 52200
    report['parentProcessBefore'] = process_metrics(report['parentPid'])
    rng = random.Random(1902026)
    for index in range(30):
        order = ['page', 'parent']
        rng.shuffle(order)
        report['pairedOrder'].append(order)
        for mode in order:
            before = time.perf_counter()
            checksum = driver.execute_async_script(script, mode, report['callsPerBatch'])
            elapsed = (time.perf_counter() - before) * 1000
            assert checksum == 522 * report['callsPerBatch']
            report['samples'][mode].append(elapsed)
    report['parentProcessAfter'] = process_metrics(report['parentPid'])
    report['processScope'] = (
        'Only the browser parent, covering the combined paired workload and browser activity; not whole-browser CPU or memory attribution.'
    )
    report['summaries'] = {k: summary(v) for k, v in report['samples'].items()}
    report['outcome'] = 'complete'
except Exception as error:
    report['error'] = repr(error)
    report['outcome'] = 'failed'
    raise
finally:
    if driver:
        driver.quit()
    if server:
        server.terminate()
        server.wait(timeout=8)
    for log in logs:
        log.close()
    (out / 'results.json').write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                **{k: v for k, v in report.items() if k not in ['samples', 'pairedOrder']},
                'directory': str(out),
            },
            indent=2,
        )
    )
