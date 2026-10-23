"""Run a temporary addon in a fresh Waterfox profile without changing existing profiles."""

import os

from pathlib import Path
import sys, json, zipfile, time

ROOT = Path(__file__).resolve().parent
sys.path.insert(
    0, os.environ.get('DOPPELGNG_ROOT', str(Path(__file__).resolve().parents[1] / '.doppelgng'))
)
sys.path.insert(0, str(ROOT))
from doppelgng.browser import Waterfox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from record import record

out = ROOT / 'evidence' / (sys.argv[1] if len(sys.argv) > 1 else 'broker')
out.mkdir(exist_ok=True)
xpi = ROOT / 'broker' / 'execution-broker.xpi'
with zipfile.ZipFile(xpi, 'w', zipfile.ZIP_DEFLATED) as z:
    for file in (ROOT / 'broker' / 'extension').iterdir():
        z.write(file, file.name)
record(
    'decision',
    'E21',
    'Run real Waterfox with temporary isolated execution broker extension.',
    [str(xpi.relative_to(ROOT))],
)
results = {}
with Waterfox(out) as browser:
    driver = browser.driver
    addon = driver.install_addon(str(xpi), temporary=True)
    results['addonId'] = addon
    results['capabilities'] = {
        k: driver.capabilities.get(k)
        for k in ['browserName', 'browserVersion', 'platformName', 'moz:geckodriverVersion']
    }
    for port in [4389, 4390]:
        driver.get(f'http://127.0.0.1:{port}/broker/')
        time.sleep(0.4)
        driver.find_element(By.ID, 'run').click()
        WebDriverWait(driver, 90).until(
            lambda d: d.find_element(By.ID, 'status').text in ['Complete', 'Failed']
        )
        item = json.loads(driver.find_element(By.ID, 'result').text)
        results[str(port)] = item
        driver.save_screenshot(str(out / f'{port}-complete.png'))
        (out / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        if 'error' in item:
            raise RuntimeError(item['error'])
    driver.uninstall_addon(addon)
record(
    'observation',
    'E21',
    'Executed actual temporary-extension broker tests on two distinct loopback origins. Raw results preserved.',
    [str((out / 'results.json').relative_to(ROOT))],
)
print(json.dumps(results, indent=2))
