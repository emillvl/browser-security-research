import json
import re


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected browser template anchor exactly once: ' + old)
    return source.replace(old, new, 1)


def with_credential(source, config):
    credential = json.loads(config.split('=', 1)[1].strip().rstrip(';'))
    if not isinstance(credential, str) or not re.fullmatch(r'[0-9a-f]{64}', credential):
        raise ValueError('Expected a fresh 32-byte local provisioning credential')
    return replace_once(source, '"__PROVISIONING_CREDENTIAL__"', json.dumps(credential))


def component_v2_source(source):
    source = replace_once(
        source,
        'const { Services } = ChromeUtils.importESModule("resource://gre/modules/Services.sys.mjs");',
        'const appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULRuntime);',
    )
    source = replace_once(source, 'Services.appinfo.processType', 'appInfo.processType')
    return replace_once(source, 'Services.appinfo.processID', 'appInfo.processID')


def owner_source(source):
    source = replace_once(
        source,
        '    if (origin !== "http://127.0.0.1:45911" || isFrame) return { error: "Origin or frame denied" };\n',
        '',
    )
    source = replace_once(
        source,
        '    if (message.op !== "evaluate") return { error: "Operation denied" };\n',
        '',
    )
    return replace_once(
        source,
        '      await this.pending;\n',
        '      await this.pending;\n'
        '      if (message.op === "export") return { ok: true, program: this.program };\n',
    )
