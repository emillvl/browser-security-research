"""Run isolated browser experiments with the existing DoppelGNG runtime.
DoppelGNG source, classifications, and capture policy remain unchanged.
An explicit URL starts the website's visible test harness."""

from pathlib import Path
import os, sys, json, time

ROOT = Path(__file__).resolve().parent
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(
    0, os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[1] / '.doppelgng'))
)
sys.path.insert(0, str(ROOT))
from doppelgng.browser import Waterfox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from record import record

mode = sys.argv[1] if len(sys.argv) > 1 else 'experiments'
directory = ROOT / 'evidence' / ('waterfox-' + mode)
directory.mkdir(exist_ok=True)
record(
    'decision',
    'CROSS-ENGINE',
    'Start actual Waterfox using existing unmodified DoppelGNG browser library.',
    mode=mode,
)
with Waterfox(directory) as browser:
    browser.driver.get(
        'http://127.0.0.1:4381/?autorun=' + ('bench' if mode == 'benchmark' else 'experiments')
    )
    WebDriverWait(browser.driver, 90).until(
        lambda d: any(
            s in d.find_element(By.ID, 'status').text
            for s in ['Complete.', 'Measurements complete.', 'Interrupted', 'failure']
        )
    )
    status = browser.driver.find_element(By.ID, 'status').text
    data = json.loads(browser.driver.find_element(By.ID, 'result').text)
    data['driver_capabilities'] = {
        k: browser.driver.capabilities.get(k)
        for k in ['browserName', 'browserVersion', 'platformName', 'moz:geckodriverVersion']
    }
    data['verified_status'] = status
    browser.driver.save_screenshot(str(directory / 'completed.png'))
    (directory / 'results.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
record(
    'observation',
    'CROSS-ENGINE',
    'Waterfox test page reached terminal status.',
    [str((directory / 'results.json').relative_to(ROOT))],
    status=status,
)
print(
    json.dumps(
        {
            'status': status,
            'capabilities': data['driver_capabilities'],
            'tests': len(data.get('tests', [])),
            'error': data.get('error'),
        },
        indent=2,
    )
)
