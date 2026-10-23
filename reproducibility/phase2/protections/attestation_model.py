"""P204 SOFTWARE MODEL ONLY: signed evidence and recipient-bound provisioning.
There is no hardware attestation, protected memory, or real device identity in this model.
The mock authority's key is software-held; the final countertest explicitly grants its owner that key.
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json, base64, hashlib, os, time, threading, copy
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def public(key):
    return base64.urlsafe_b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()


def decode(text):
    return base64.urlsafe_b64decode(text)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Rejected(Exception):
    pass


class Provider:
    def __init__(self, authority):
        self.authority = authority.public_key()
        self.expected = digest(
            (ROOT / 'browser/waterfox-broker/research-modules/Broker.sys.mjs').read_bytes()
        )
        self.epoch = 1
        self.minimumVersion = 2
        self.challenges = {}
        self.lock = threading.Lock()

    def challenge(self, account='authorized-research-account', now=None):
        nonce = os.urandom(24).hex()
        self.challenges[nonce] = {
            'account': account,
            'expires': (time.monotonic() if now is None else now) + 1.5,
            'used': False,
        }
        return nonce

    def release(self, evidence, signature, account='authorized-research-account', now=None):
        with self.lock:
            try:
                self.authority.verify(signature, canonical(evidence))
            except Exception:
                raise Rejected('Untrusted or altered evidence signature')
            c = self.challenges.get(evidence.get('nonce'))
            if not c:
                raise Rejected('Unknown challenge')
            if c['used']:
                raise Rejected('Consumed challenge')
            if (time.monotonic() if now is None else now) > c['expires']:
                raise Rejected('Expired challenge')
            if evidence.get('account') != account or c['account'] != account:
                raise Rejected('Account binding')
            if evidence.get('audience') != 'phase2-program-provider':
                raise Rejected('Provider audience binding')
            if evidence.get('measurement') != self.expected:
                raise Rejected('Unexpected program measurement')
            if evidence.get('debug') is not False:
                raise Rejected('Debug execution refused')
            if evidence.get('securityVersion', 0) < self.minimumVersion:
                raise Rejected('Retired security version')
            if evidence.get('epoch') != self.epoch:
                raise Rejected('Revoked provisioning epoch')
            if evidence.get('operation') != 'dispatch-score':
                raise Rejected('Operation binding')
            recipient = x25519.X25519PublicKey.from_public_bytes(decode(evidence['recipient']))
            ephemeral = x25519.X25519PrivateKey.generate()
            salt = os.urandom(16)
            nonce = os.urandom(12)
            key = HKDF(
                algorithm=hashes.SHA256(), length=32, salt=salt, info=b'phase2-software-model'
            ).derive(ephemeral.exchange(recipient))
            aad = {
                'recipient': evidence['recipient'],
                'measurement': self.expected,
                'epoch': self.epoch,
                'operation': evidence['operation'],
            }
            model = json.loads((ROOT / 'evidence/ground-truth.json').read_text())['model']
            plain = canonical(model)
            ciphertext = AESGCM(key).encrypt(nonce, plain, canonical(aad))
            c['used'] = True
            return {
                'public': public(ephemeral),
                'salt': salt,
                'iv': nonce,
                'ciphertext': ciphertext,
                'aad': aad,
            }


authority = ed25519.Ed25519PrivateKey.generate()
provider = Provider(authority)
recipient = x25519.X25519PrivateKey.generate()


def evidence(**updates):
    value = {
        'nonce': provider.challenge(),
        'account': 'authorized-research-account',
        'audience': 'phase2-program-provider',
        'measurement': provider.expected,
        'debug': False,
        'securityVersion': 2,
        'epoch': provider.epoch,
        'operation': 'dispatch-score',
        'recipient': public(recipient),
    }
    value.update(updates)
    return value


def sign(value, key=authority):
    return key.sign(canonical(value))


def decrypt(capsule, key=recipient):
    peer = x25519.X25519PublicKey.from_public_bytes(decode(capsule['public']))
    secret = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=capsule['salt'], info=b'phase2-software-model'
    ).derive(key.exchange(peer))
    return AESGCM(secret).decrypt(capsule['iv'], capsule['ciphertext'], canonical(capsule['aad']))


def attempt(value, signature=None, **args):
    try:
        provider.release(value, signature if signature is not None else sign(value), **args)
        return {'accepted': True}
    except Rejected as error:
        return {'accepted': False, 'reason': str(error)}


report = {'label': __doc__, 'hardwareAttestation': False, 'tests': {}}
v = evidence()
capsule = provider.release(v, sign(v))
recovered = json.loads(decrypt(capsule))
report['normal'] = {
    'modelId': recovered['id'],
    'trees': len(recovered['trees']),
    'plaintextBytes': len(decrypt(capsule)),
    'ciphertextBytes': len(capsule['ciphertext']),
}
report['tests']['replay'] = attempt(v)
for name, change in [
    ('wrongMeasurement', {'measurement': '0' * 64}),
    ('debug', {'debug': True}),
    ('rollback', {'securityVersion': 1}),
    ('wrongAudience', {'audience': 'another-provider'}),
    ('wrongOperation', {'operation': 'export-account-data'}),
    ('retiredEpoch', {'epoch': 0}),
]:
    report['tests'][name] = attempt(evidence(**change))
v = evidence()
sig = sign(v)
altered = {**v, 'recipient': public(x25519.X25519PrivateKey.generate())}
report['tests']['recipientSubstitution'] = attempt(altered, sig)
report['tests']['legitimateAfterFailedSubstitution'] = attempt(v, sig)
v = evidence()
report['tests']['untrustedIssuer'] = attempt(v, sign(v, ed25519.Ed25519PrivateKey.generate()))
report['tests']['foreignAccount'] = attempt(evidence(), account='another-account')
old = evidence(nonce=provider.challenge(now=0))
report['tests']['expired'] = attempt(old, now=2)
for name, value, key in [
    ('wrongRecipient', capsule, x25519.X25519PrivateKey.generate()),
    (
        'tamperedCiphertext',
        {
            **capsule,
            'ciphertext': capsule['ciphertext'][:-1] + bytes([capsule['ciphertext'][-1] ^ 1]),
        },
        recipient,
    ),
    ('tamperedMetadata', {**capsule, 'aad': {**capsule['aad'], 'epoch': 99}}, recipient),
]:
    try:
        decrypt(value, key)
        report['tests'][name] = {'decrypted': True}
    except Exception as error:
        report['tests'][name] = {'decrypted': False, 'error': type(error).__name__}
v = evidence()
sig = sign(v)
with ThreadPoolExecutor(max_workers=20) as pool:
    race = list(pool.map(lambda _: attempt(v, sig), range(20)))
report['duplicateRace'] = {
    'accepted': sum(x['accepted'] for x in race),
    'rejected': sum(not x['accepted'] for x in race),
    'scope': 'One Python process with a lock, not a distributed verifier',
}
# The mock signing key lets the software owner forge the program measurement.
actual = digest((ROOT / 'browser/waterfox-owner/research-modules/Broker.sys.mjs').read_bytes())
forged = evidence(measurement=provider.expected)
released = provider.release(forged, sign(forged))
report['softwareOwnerCountertest'] = {
    'actualModifiedModuleMeasurement': actual,
    'claimedApprovedMeasurement': provider.expected,
    'different': actual != provider.expected,
    'softwareIssuerKeyGrantedToOwner': True,
    'capsuleAccepted': True,
    'decryptedModel': json.loads(decrypt(released))['id'],
    'interpretation': 'This demonstrates the missing trust assumption in the software model; it does not forge real hardware attestation.',
}
out = ROOT / 'evidence' / ('attestation-software-model-' + str(time.time_ns()) + '.json')
out.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
