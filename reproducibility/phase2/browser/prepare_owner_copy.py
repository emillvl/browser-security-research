"""Change the custom research policy in a separate browser copy for the owner countertest."""

from pathlib import Path
import shutil, hashlib, json

ROOT = Path(__file__).resolve().parents[1]
original = ROOT / 'browser/waterfox-broker'
target = ROOT / 'browser/waterfox-owner'
if target.exists():
    raise RuntimeError(
        'The owner-countertest copy already exists; preserve it instead of overwriting it'
    )
shutil.copytree(original, target)
module = target / 'research-modules/Broker.sys.mjs'
text = module.read_text(encoding='utf-8')
guard = "  if(origin!=='http://127.0.0.1:45911'||isFrame)return {error:'Origin or frame denied'};"
operation = "  if(message.op!=='evaluate')return {error:'Operation denied'};"
if text.count(guard) != 1 or text.count(operation) != 1:
    raise RuntimeError('The expected research policy was not found exactly once')
text = text.replace(
    guard, '  // Owner countertest: the custom origin and frame policy has been removed.'
)
text = text.replace(
    operation, '  // Owner countertest: the custom operation allowlist has been removed.'
)
anchor = 'await this.pending;return {ok:true,result:this.evaluate(message.input)'
if text.count(anchor) != 1:
    raise RuntimeError('The expected custom execution path was not found')
text = text.replace(
    anchor,
    "await this.pending;if(message.op==='export')return {ok:true,program:this.program};return {ok:true,result:this.evaluate(message.input)",
)
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
