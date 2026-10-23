"""Register a privileged resource mapping rather than importing system modules through file URLs."""

from pathlib import Path
import shutil, json

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'browser/waterfox-broker'
version = ROOT / 'versions/browser-component-v2'
if not version.exists():
    version.mkdir()
    shutil.copy2(target / 'research.cfg', version / 'research.cfg')
    shutil.copytree(target / 'research-modules', version / 'research-modules')
config = '''// Dedicated isolated Phase II browser distribution only.
try {
 var p2Dir=Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("GreD",Ci.nsIFile);p2Dir.append("research-modules");
 var p2IO=Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
 p2IO.getProtocolHandler("resource").QueryInterface(Ci.nsIResProtocolHandler).setSubstitution("copyresistance",p2IO.newFileURI(p2Dir));
 ChromeUtils.registerWindowActor("Research",{parent:{esModuleURI:"resource://copyresistance/ResearchParent.sys.mjs"},child:{esModuleURI:"resource://copyresistance/ResearchChild.sys.mjs",events:{ResearchInvoke:{capture:true,wantUntrusted:true}}},matches:["http://127.0.0.1/*"],allFrames:true});
 Cc["@mozilla.org/preferences-service;1"].getService(Ci.nsIPrefBranch).setStringPref("research.component.status","registered-v3");
} catch(error) { Cu.reportError(error); }
'''
(target / 'research.cfg').write_text(config, encoding='utf-8')
print(
    'Registered the isolated component through the privileged resource scheme; the prior failed version is preserved.'
)
