from pathlib import Path
import shutil, json, hashlib, sys
from preparation import with_credential

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from log import event

base = ROOT / 'browser/waterfox-pristine'
target = ROOT / 'browser/waterfox-broker'
if target.exists():
    raise RuntimeError(
        'Dedicated broker distribution already exists; preserve it and select another version'
    )
source = with_credential(
    (ROOT / 'browser/modules/Broker.sys.mjs').read_text(encoding='utf-8'),
    (ROOT / 'protections/extension/config.js').read_text(encoding='utf-8'),
)
shutil.copytree(base, target)
modules = target / 'research-modules'
shutil.copytree(ROOT / 'browser/modules', modules)
broker = modules / 'Broker.sys.mjs'
broker.write_text(source, encoding='utf-8')
config = """// Dedicated Phase II privileged browser-component experiment.
var {Services}=ChromeUtils.importESModule('resource://gre/modules/Services.sys.mjs');
var dir=Services.dirsvc.get('GreD',Ci.nsIFile);dir.append('research-modules');
Services.io.getProtocolHandler('resource').QueryInterface(Ci.nsIResProtocolHandler).setSubstitution('copyresistance',Services.io.newFileURI(dir));
ChromeUtils.registerWindowActor('Research',{parent:{esModuleURI:'resource://copyresistance/ResearchParent.sys.mjs'},child:{esModuleURI:'resource://copyresistance/ResearchChild.sys.mjs',events:{ResearchInvoke:{capture:true,wantUntrusted:true}}},matches:['http://127.0.0.1/*'],allFrames:true});
"""
(target / 'research.cfg').write_text(config, encoding='utf-8')
(target / 'defaults/pref/research.js').write_text(
    'pref("general.config.filename","research.cfg");\npref("general.config.obscure_value",0);\npref("general.config.sandbox_enabled",false);\n',
    encoding='utf-8',
)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
receipt = {
    'base_binary_sha256': sha(base / 'waterfox.exe'),
    'modified_binary_sha256': sha(target / 'waterfox.exe'),
    'changes': ['defaults/pref/research.js', 'research.cfg', 'research-modules/*'],
    'boundary': 'Privileged browser parent JSWindowActor and ES module. This modifies the isolated distribution, not C++ engine binaries.',
    'rollback': 'Discard the dedicated distribution and profile; the pristine source copy and original tool runtime are unchanged.',
}
assert receipt['base_binary_sha256'] == receipt['modified_binary_sha256']
(ROOT / 'evidence/browser-modification.json').write_text(
    json.dumps(receipt, indent=2), encoding='utf-8'
)
event(
    'decision',
    'P203',
    'I installed a privileged parent-component broker in a dedicated browser copy, preserving its original executable and pristine distribution.',
    ['evidence/browser-modification.json'],
)
print(json.dumps(receipt, indent=2))
