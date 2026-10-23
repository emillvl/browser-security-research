"""Record HTTP observations from the local test server."""

from pathlib import Path
import json, urllib.request, urllib.error, time
from record import record

ROOT = Path(__file__).resolve().parent
results = []


def get(name, url, headers=None, post=None):
    req = urllib.request.Request(
        url, headers=headers or {}, data=json.dumps(post).encode() if post is not None else None
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            status, data, h = r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, data, h = e.code, e.read(), dict(e.headers)
    results.append(
        {
            'test': name,
            'url': url,
            'request_headers': headers or {},
            'status': status,
            'body': data.decode('utf-8'),
            'bytes': len(data),
            'elapsed_ms': (time.perf_counter() - start) * 1000,
            'response_headers': h,
        }
    )


base = 'http://127.0.0.1:4381'
remote = 'http://127.0.0.1:4382'
get('CORS opaque resource via native HTTP', remote + '/untrusted.json')
get('Origin denied without allowed header', remote + '/remote-quote?x=17')
get('Origin header spoofed by native client', remote + '/remote-quote?x=17', {'Origin': base})
get('Collector header denied', base + '/adaptive.js', {'User-Agent': 'WebsiteProtectionProbe/1.0'})
get(
    'Same collector with browser-shaped header',
    base + '/adaptive.js',
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0.0.0 Safari/537.36'
    },
)
get(
    'No cookie signed request',
    base + '/api/signed',
    {'Content-Type': 'application/json'},
    {'nonce': 'copied', 'x': 5, 'signature': 'copied'},
)
get('Server environment', base + '/environment')
out = ROOT / 'evidence' / f'native-probe-{int(time.time()*1000)}.json'
out.write_text(json.dumps(results, indent=2), encoding='utf-8')
record(
    'observation',
    'NATIVE',
    'Ran independent HTTP controls against owned loopback server only.',
    [str(out.relative_to(ROOT))],
)
print(
    json.dumps(
        [{'test': r['test'], 'status': r['status'], 'bytes': r['bytes']} for r in results], indent=2
    )
)
