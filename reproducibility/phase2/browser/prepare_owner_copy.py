"""Change the custom research policy in a separate browser copy for the owner countertest."""

from pathlib import Path
import shutil, hashlib, json
from preparation import owner_source

ROOT = Path(__file__).resolve().parents[1]
original = ROOT / 'browser/waterfox-broker'
target = ROOT / 'browser/waterfox-owner'
if target.exists():
    raise RuntimeError(
        'The owner-countertest copy already exists; preserve it instead of overwriting it'
    )
text = owner_source((original / 'research-modules/Broker.sys.mjs').read_text(encoding='utf-8'))
shutil.copytree(original, target)
module = target / 'research-modules/Broker.sys.mjs'
module.write_text(text, encoding='utf-8')
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
receipt = {
    'pristineExecutableSHA256': digest(ROOT / 'browser/waterfox-pristine/waterfox.exe'),
    'guardedExecutableSHA256': digest(original / 'waterfox.exe'),
    'ownerExecutableSHA256': digest(target / 'waterfox.exe'),
    'changedFile': 'research-modules/Broker.sys.mjs',
    'guardedModuleSHA256': digest(original / 'research-modules/Broker.sys.mjs'),
    'ownerModuleSHA256': digest(module),
    'scope': 'Only the custom research component in this extra copy. No personal browser or profile is modified.',
}
assert (
    len(
        {
            receipt[k]
            for k in [
                'pristineExecutableSHA256',
                'guardedExecutableSHA256',
                'ownerExecutableSHA256',
            ]
        }
    )
    == 1
)
(ROOT / 'evidence/owner-copy-receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
