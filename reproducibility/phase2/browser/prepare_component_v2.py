"""A reversible privileged component in the dedicated test distribution, not an engine source build."""

from pathlib import Path
import shutil, json, hashlib
from preparation import component_v2_source, with_credential

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'browser/waterfox-broker'
source = with_credential(
    component_v2_source((ROOT / 'browser/modules/Broker.sys.mjs').read_text(encoding='utf-8')),
    (ROOT / 'protections/extension/config.js').read_text(encoding='utf-8'),
)
version = ROOT / 'versions/browser-component-v1'
if not version.exists():
    version.mkdir()
    shutil.copy2(target / 'research.cfg', version / 'research.cfg')
    shutil.copytree(target / 'research-modules', version / 'research-modules')
modules = target / 'research-modules'
(modules / 'Broker.sys.mjs').write_text(source, encoding='utf-8')
parent = (
    (ROOT / 'browser/modules/ResearchParent.sys.mjs')
    .read_text()
    .replace('resource://copyresistance/Broker.sys.mjs', './Broker.sys.mjs')
)
(modules / 'ResearchParent.sys.mjs').write_text(parent, encoding='utf-8')
shutil.copy2(ROOT / 'browser/modules/ResearchChild.sys.mjs', modules / 'ResearchChild.sys.mjs')
config = '''// Dedicated isolated Phase II browser distribution only.
try {
 var p2File=Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("GreD",Ci.nsIFile);p2File.append("research-modules");
 var p2IO=Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
 var p2Module=name=>{var f=p2File.clone();f.append(name);return p2IO.newFileURI(f).spec;};
 ChromeUtils.registerWindowActor("Research",{parent:{esModuleURI:p2Module("ResearchParent.sys.mjs")},child:{esModuleURI:p2Module("ResearchChild.sys.mjs"),events:{ResearchInvoke:{capture:true,wantUntrusted:true}}},matches:["http://127.0.0.1/*"],allFrames:true});
 Cc["@mozilla.org/preferences-service;1"].getService(Ci.nsIPrefBranch).setStringPref("research.component.status","registered-v2");
} catch(error) { Cu.reportError(error); }
'''
(target / 'research.cfg').write_text(config, encoding='utf-8')
receipt = {
    'version': 2,
    'changes': [
        'research.cfg',
        'research-modules/Broker.sys.mjs',
        'research-modules/ResearchParent.sys.mjs',
    ],
    'executableSHA256': hashlib.sha256((target / 'waterfox.exe').read_bytes()).hexdigest(),
    'brokerModuleURI': (modules / 'Broker.sys.mjs').as_uri(),
    'rollback': 'Use the pristine distribution; remove only this isolated test copy when no longer needed.',
}
(ROOT / 'evidence/browser-component-v2.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({k: v for k, v in receipt.items() if k != 'brokerModuleURI'}, indent=2))
