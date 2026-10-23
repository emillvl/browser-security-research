"""Check the recorded Phase II observations without rerunning attacks or redefining tool verdicts.
A passing audit means the reported observations agree with their evidence, not that attacks failed.
"""

from pathlib import Path
import json, time, hashlib, collections, math

ROOT = Path(__file__).resolve().parents[1]
sources = {
    'baseline': 'evidence/standard-baseline-1792348217555590900/results.json',
    'standard': 'evidence/standard-guarded-1792415411486650200/results.json',
    'batch': 'evidence/batch-1792414384486226700/results.json',
    'worker': 'evidence/worker-1792346830634517400/results.json',
    'provision': 'evidence/provisioning-1792414896485955600/results.json',
    'component': 'evidence/component-guarded-1792414911098068500/results.json',
    'debug': 'evidence/component-debug-1792412592316627400/results.json',
    'owner': 'evidence/component-owner-1792412581289366600/results.json',
    'observer': 'evidence/content-observer-1792415241204840100/results.json',
    'proxy': 'evidence/proxy-1792414219748826600/results.json',
    'offline': 'evidence/offline-replay-1792412654477572100/results.json',
    'offlineBrokers': 'evidence/offline-brokers-1792415341823639600/results.json',
    'adaptive': 'evidence/adaptive-1792414590869420100/results.json',
    'native': 'binary/recovery-results.json',
    'enclave': 'binary/enclave-build-1792412264077479400/loader-results.json',
    'softwareAttestation': 'evidence/attestation-software-model-1792412395015913100.json',
}
data = {name: json.loads((ROOT / path).read_text()) for name, path in sources.items()}
checks = []


def equal(name, actual, expected):
    checks.append(
        {'name': name, 'passed': actual == expected, 'actual': actual, 'expected': expected}
    )


score = {'score': 522, 'band': 'medium'}
standard = data['standard']
attacks = standard['attacks']
for name, page in standard['pages'].items():
    equal(name + ' ordinary score', page['score']['result'], score)
    equal(name + ' route', page['route']['result'], {'distance': 32, 'route': [0, 16, 15, 17]})
    equal(name + ' Wasm matches baseline', page['wasm'], data['baseline']['pages'][name]['wasm'])
    equal(name + ' responsive overflow', [v['overflow'] for v in page['layouts']], [False] * 3)
    equal(name + ' visible error', page['errors'], '')
for name, status in {
    'invalidLogin': 401,
    'noSession': 401,
    'noCsrf': 403,
    'publicProgram': 404,
    'anonymous': 404,
    'forgedPayload': 403,
    'expired': 410,
    'retired': 403,
    'staleVersion': 409,
    'reusedIdDifferentPayload': 409,
    'foreignSignedEnvelope': 403,
    'foreignReservation': 403,
    'quotaAfterNewSession': 429,
}.items():
    equal('standard ' + name, attacks[name].get('status'), status)
equal(
    'duplicate race',
    dict(collections.Counter(v['status'] for v in attacks['duplicateRace'])),
    {200: 1, 409: 19},
)
equal(
    'fresh concurrency',
    dict(collections.Counter(v['status'] for v in attacks['independentConcurrent'])),
    {200: 20},
)
equal(
    'quota after one charged denied reservation attempt',
    dict(collections.Counter(v['status'] for v in attacks['quota'])),
    {200: 11, 429: 2},
)
equal('quota first subsequent success leaves ten slots', attacks['quota'][0]['remaining'], 10)
for name in ('idempotent', 'commitRetry'):
    equal(name + ' cached', attacks[name].get('cached'), True)
for name, state in [('cancelled', 'cancelled'), ('committed', 'committed')]:
    equal(name + ' state', attacks[name]['result']['reservation']['state'], state)
equal('reservation expiry', attacks['expiredReservation']['state'], 'expired')
equal('keyboard score', '522' in standard['keyboard']['output'], True)
equal('input labels', all(row['labels'] > 0 for row in attacks['labels']), True)
equal('live result semantics', attacks['resultStatusSemantics'], True)
equal('program hook capture count', attacks['programDecryptCaptures'], 0)
equal('program hook control', attacks['decryptPositiveControl'], ['independent page hook control'])
equal('standard browser exceptions', len(standard['consoleExceptions']), 0)
b = data['batch']['checks']
for name, status in {
    'empty': 400,
    'oversized': 400,
    'tampered': 403,
    'replay': 409,
    'cap': 429,
    'expired': 410,
    'retired': 403,
}.items():
    equal('batch ' + name, b[name].get('status'), status)
equal('batch valid', dict(collections.Counter(v['status'] for v in b['valid'])), {200: 16})
equal(
    'batch concurrency',
    dict(collections.Counter(v['status'] for v in b['concurrent64'])),
    {200: 64},
)
equal('batch key recovery', b['recovery']['result'], score)
equal('worker independent clone', data['worker']['offline_clone']['matches'], 100)
equal('worker runtime substitution', data['worker']['after_mutation']['result']['score'], -777)
p = data['provision']
for name, status in {
    'wrongCredential': 401,
    'copiedCredentialUnapprovedKey': 403,
    'unapprovedCapsule': 403,
    'unauthorizedApproval': 401,
    'revokedCapsule': 403,
}.items():
    equal('provision ' + name, p[name]['status'], status)
equal('capsule signature', p['tamperedCapsule'], 'Issuer signature failed')
equal('capsule rollback', p['rollback'], 'Program rollback refused')
equal(
    'expired lease after revoke',
    p['afterLeaseAfterRevoke'],
    {'error': 'Recipient key not approved'},
)
equal('persisted approved recipient', p['restartRetainsRecipient'], True)
equal('persistent key export', p['restartedPrivateKeyExport'], 'InvalidAccessError')
equal('restart normal calculation', p['afterWorkerRestart']['result']['score'], 489)
equal(
    'post-revocation offline clone', p['offlineAfterRevocation'], {'matches': 1000, 'total': 1000}
)
equal('extension direct frame denied', p['frame']['direct'], {'error': 'Origin or context denied'})
equal('extension indirect parent call', p['frame']['throughParent']['result']['score'], 489)
c = data['component']
equal(
    'real parent execution',
    c['45911']['normal']['execution']['pid'],
    c['capabilities']['moz:processID'],
)
equal('native process type', c['45911']['normal']['execution']['processType'], 0)
equal('component ordinary results', c['normalHeldout'], {'total': 100, 'matches': 100})
equal('component direct frame denied', c['frame'], {'error': 'Origin or frame denied'})
equal('component parent relay', c['sameOriginFrameThroughParent']['result'], score)
equal(
    'component cross-origin parent access',
    c['crossOriginFrameParentAccess'],
    {'error': 'SecurityError'},
)
for name in ('debug', 'owner'):
    equal(name + ' component offline clone', data[name]['offlineClone']['matches'], 1000)
equal('parent runtime substitution', data['debug']['afterMutation']['result']['score'], -888)
o = data['observer']
equal('content-script plaintext capture', o['afterNormal']['decrypted'], [])
equal(
    'content-script hook control',
    o['afterPositiveControl']['decrypted'],
    ['observer positive control'],
)
equal('content-script forged displayed answer', o['forgedInterfaceResult']['result']['score'], -666)
equal('content-script recovery', o['normalAfterDisable']['result'], score)
proxy = data['proxy']
equal(
    'online proxy clone',
    proxy['onlineClone'],
    {'matches': 100, 'total': 100, 'backendSourceRecovered': False},
)
equal('proxy without session', proxy['proxyWithoutSession']['status'], 401)
equal('proxy offline cache', proxy['offlineCache'], {'matches': 100, 'total': 100})
equal('proxy unseen input offline', proxy['uncachedOffline']['status'], 503)
equal('proxy new session quota', proxy['quotaNewSession']['status'], 429)
equal(
    'public offline program',
    data['offline']['cases']['baseline']['offlineScores'],
    {'matches': 100, 'total': 100},
)
for name, case in data['offlineBrokers']['cases'].items():
    equal(name + ' preserved incomplete capture', case['unchangedCaptureStatus'], 'incomplete')
    equal(name + ' offline source absent', case['originalServiceRequested'], False)
    equal(
        name + ' copied interface without runtime',
        case['ordinaryButtonResult'],
        'Browser component timeout' if name == 'browser-component' else 'Broker timeout',
    )
for name, base in [
    ('extension-v1', 'capture-brokers-1792414983720464800'),
    ('extension-v2', 'capture-brokers-1792414983720464800'),
    ('browser-component', 'capture-brokers-1792415252546021900'),
]:
    manifest = json.loads((ROOT / 'evidence' / base / name / 'archive/manifest.json').read_text())
    failed = [page for page in manifest['pages'].values() if page['state'] == 'failed']
    equal(
        name + ' capture visual observations',
        all(
            obs['checks']['visual'] for page in failed for obs in page['validation']['observations']
        ),
        True,
    )
    equal(
        name + ' capture title identifies route',
        failed[0]['title'],
        {
            'extension-v1': 'Dispatch model worker test',
            'extension-v2': 'Approved recipient research',
            'browser-component': 'Dispatch model browser component test',
        }[name],
    )
equal('adaptive exact held-out scores', data['adaptive']['adaptiveFinal']['exactScore'], 3)
equal('equal-budget random exact scores', data['adaptive']['randomFinal']['exactScore'], 9)
equal('Ghidra recovered native function', data['native']['matches'], 1000)
e = data['enclave']
equal('VBS allocation', e['create']['success'], True)
equal('VBS unsigned image rejected', e['load']['windowsError'], 577)
equal('actual hardware attestation not performed', e['attestationPerformed'], False)
s = data['softwareAttestation']
equal('software model explicit label', s['hardwareAttestation'], False)
equal('software owner counterexample', s['softwareOwnerCountertest']['capsuleAccepted'], True)
pairs = json.loads((ROOT / 'evidence/learning-1792348353553058500/queried-pairs.json').read_text())
distribution = {}
for field in ('score', 'band'):
    counts = collections.Counter(row['output'][field] for row in pairs['heldout'])
    n = sum(counts.values())
    distribution[field] = {
        'samples': n,
        'distinct': len(counts),
        'empiricalMarginalEntropyBits': -sum((v / n) * math.log2(v / n) for v in counts.values()),
    }
report = {
    'scope': __doc__,
    'checks': checks,
    'passed': sum(c['passed'] for c in checks),
    'total': len(checks),
    'allObservationsConsistent': all(c['passed'] for c in checks),
    'distribution': distribution,
    'entropyLimitation': 'Empirical marginal entropy of held-out outputs, not mutual information about source or an extraction lower bound.',
    'sources': {
        name: {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
        for name, path in sources.items()
    },
}
output = ROOT / 'evidence' / ('observations-audit-' + str(time.time_ns()) + '.json')
output.write_text(json.dumps(report, indent=2))
print(
    json.dumps(
        {
            'directory': str(output),
            'checksPassed': report['passed'],
            'checksTotal': report['total'],
            'failures': [c for c in checks if not c['passed']],
            'distribution': distribution,
        },
        indent=2,
    )
)
if not report['allObservationsConsistent']:
    raise SystemExit(1)
