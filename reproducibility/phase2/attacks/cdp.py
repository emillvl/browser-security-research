import json, time, urllib.request, socket, subprocess
from pathlib import Path
import websocket

ROOT = Path(__file__).resolve().parents[1]


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=30, suppress_origin=True)
        self.counter = 0
        self.events = []

    def command(self, method, params=None):
        self.counter += 1
        identifier = self.counter
        self.ws.send(json.dumps({'id': identifier, 'method': method, 'params': params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == identifier:
                if 'error' in message:
                    raise RuntimeError(json.dumps(message['error']))
                return message.get('result', {})
            self.events.append(message)

    def evaluate(self, expression):
        result = self.command(
            'Runtime.evaluate',
            {'expression': expression, 'awaitPromise': True, 'returnByValue': True},
        )
        if 'exceptionDetails' in result:
            raise RuntimeError(json.dumps(result['exceptionDetails']))
        return result.get('result', {}).get('value')

    def close(self):
        self.ws.close()


def targets(port):
    return json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))


def browser_launch(
    out,
    extension=True,
    port=45915,
    extension_path=None,
    reuse_profile=False,
    extra_extension_paths=None,
):
    # Leave an existing listener running.
    with socket.socket() as check:
        check.bind(('127.0.0.1', port))
    profile = out / 'profile'
    if reuse_profile and not profile.is_dir():
        raise RuntimeError('Only an existing isolated research profile can be restarted')
    profile.mkdir(parents=True, exist_ok=reuse_profile)
    command = [
        str(ROOT / 'browser/chrome-win64/chrome.exe'),
        f'--remote-debugging-port={port}',
        '--remote-debugging-address=127.0.0.1',
        f'--user-data-dir={profile}',
        '--headless=new',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-networking',
    ]
    if extension:
        extension_path = Path(extension_path) if extension_path else ROOT / 'protections/extension'
        paths = ','.join(str(p) for p in [extension_path, *list(extra_extension_paths or [])])
        command += ['--load-extension=' + paths, '--disable-extensions-except=' + paths]
    log = (out / 'browser.log').open('a' if reuse_profile else 'w', encoding='utf-8')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            if targets(port):
                return process, log, command
        except Exception:
            pass
        if process.poll() is not None:
            raise RuntimeError('Isolated browser exited: ' + str(process.returncode))
        time.sleep(0.1)
    process.terminate()
    raise RuntimeError('Browser protocol did not start')
