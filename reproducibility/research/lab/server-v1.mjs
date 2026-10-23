import http from "node:http";
import { readFileSync, writeFileSync, appendFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import os from "node:os";
import {
  randomBytes,
  createECDH,
  hkdfSync,
  createCipheriv,
  createPublicKey,
  verify,
  createHmac,
  createHash,
} from "node:crypto";

const root = path.dirname(fileURLToPath(import.meta.url));
const evidence = path.join(root, "../evidence");
mkdirSync(evidence, { recursive: true });
const started = new Date().toISOString();
const sessions = new Map();
const oracleKey = randomBytes(32);
let requestSequence = 0;
const source =
  "/* Capsule research control */\nglobalThis.protectedQuote = function quote(x) { return (7*x+13)%1009; };\n";
const plain = "function quote(x){return (7*x+13)%1009;}\nglobalThis.quote=quote;\n";
const vm =
  "globalThis.quoteVM=function(x){const b=[1,7,2,1,13,3,1,1009,4,0],s=[];for(let p=0;;){switch(b[p++]){case 0:return s.pop();case 1:s.push(b[p++]);break;case 2:s.push(s.pop()*x);break;case 3:s.push(s.pop()+s.pop());break;case 4:{let m=s.pop();s.push(s.pop()%m);break;}}}};";
const b64 = (b) => Buffer.from(b).toString("base64url");
const hash = (b) => createHash("sha256").update(b).digest("hex");
function quote(x) {
  return (7 * x + 13) % 1009;
}
const wasm = Buffer.from([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 6, 1, 96, 1, 127, 1, 127, 3, 2, 1, 0, 7, 9, 1, 5, 113, 117, 111,
  116, 101, 0, 0, 10, 16, 1, 14, 0, 32, 0, 65, 7, 108, 65, 13, 106, 65, 241, 7, 112, 11,
]);
writeFileSync(path.join(root, "quote.wasm"), wasm);
const style =
  "body{font:17px system-ui;max-width:1060px;margin:42px auto;padding:0 28px;color:#162434;background:#f7f8fa}h1{font-size:32px}button,input{font:inherit;padding:10px;margin:5px}button{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border:1px solid #ccd4dc;font-size:13px}a{color:#075bb0}iframe{width:100%;height:210px;border:1px solid #aaa}small{color:#4b5967}label{display:inline-block}output{display:block;margin:15px 0;font-size:24px}.sr{position:absolute;left:-10000px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:9px;text-align:left}";
function html(title, body, scripts = "") {
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${title}</title><style>${style}</style><body><h1>${title}</h1>${body}${scripts}</body></html>`;
}
function sid(req) {
  return /(?:^|;\s*)research_session=([^;]+)/.exec(req.headers.cookie || "")?.[1];
}
function session(req) {
  const s = sessions.get(sid(req));
  return s && s.expires > Date.now() ? s : null;
}
async function body(req) {
  let chunks = [],
    n = 0;
  for await (const c of req) {
    n += c.length;
    if (n > 2_000_000) throw Error("body limit");
    chunks.push(c);
  }
  return JSON.parse(Buffer.concat(chunks).toString() || "{}");
}
function record(kind, experiment, claim, extra = {}) {
  appendFileSync(
    path.join(root, "../chronology.jsonl"),
    JSON.stringify({ time: new Date().toISOString(), kind, experiment, claim, ...extra }) + "\n",
  );
}
function service(req, res, port) {
  const begin = performance.now(),
    cpu = process.cpuUsage();
  const id = ++requestSequence;
  let bytes = 0;
  const send = (status, data, type = "application/json", headers = {}) => {
    const buf = Buffer.isBuffer(data)
      ? data
      : Buffer.from(typeof data === "string" ? data : JSON.stringify(data));
    bytes = buf.length;
    res.writeHead(status, {
      "Content-Type": type,
      "Content-Length": buf.length,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...headers,
    });
    res.end(req.method === "HEAD" ? undefined : buf);
  };
  res.on("finish", () => {
    const used = process.cpuUsage(cpu);
    appendFileSync(
      path.join(evidence, "server-requests.jsonl"),
      JSON.stringify({
        time: new Date().toISOString(),
        id,
        method: req.method,
        path: req.url,
        port,
        status: res.statusCode,
        bytes,
        elapsed_ms: performance.now() - begin,
        cpu_user_us: used.user,
        cpu_system_us: used.system,
        rss_bytes: process.memoryUsage().rss,
      }) + "\n",
    );
  });
  (async () => {
    const u = new URL(req.url, `http://127.0.0.1:${port}`),
      p = u.pathname;
    if (p === "/favicon.ico") return send(204, "", "text/plain");
    if (p === "/robots.txt") return send(200, "User-agent: *\nDisallow: /robots/\n", "text/plain");
    if (p === "/")
      return send(
        200,
        html(
          "Browser protection experiments",
          `<p>Controlled website experiments executed by this browser. Results are saved locally with raw samples. No third party requests.</p><p id="status" role="status">Ready</p><button id="run">Run all experiments</button><button id="bench">Run performance measurements</button><p><a href="/baseline/">Plain website</a> · <a href="/protected/">Service protected website</a> · <a href="/robots/">Robots excluded page</a> · <a href="/csp/">CSP and integrity checks</a> · <a href="/rendered/">Canvas and accessibility</a></p><pre id="result" aria-live="polite">No results yet</pre>`,
          `<script src="/client.js"></script>`,
        ),
        "text/html",
      );
    if (p === "/client.js")
      return send(200, readFileSync(path.join(root, "client.js")), "application/javascript");
    if (p === "/plain.js") return send(200, plain, "application/javascript");
    if (p === "/vm.js") return send(200, vm, "application/javascript");
    if (p === "/quote.wasm") return send(200, wasm, "application/wasm");
    if (p === "/cross.js")
      return send(200, "globalThis.crossOriginExecutable=true;", "application/javascript");
    if (p === "/untrusted.json")
      return send(200, { message: "Readable by native HTTP but no CORS permission" });
    if (p === "/sri-good.js")
      return send(
        200,
        'document.querySelector("#sri-good").textContent="Allowed script executed";',
        "application/javascript",
      );
    if (p === "/sri-bad.js")
      return send(
        200,
        'document.querySelector("#sri-bad").textContent="Tampered script executed";',
        "application/javascript",
      );
    if (p === "/csp.js")
      return send(
        200,
        `setTimeout(()=>{document.querySelector('#csp-result').textContent=JSON.stringify({inlineBlocked:!globalThis.inlineRan,goodIntegrity:document.querySelector('#sri-good').textContent,badIntegrity:document.querySelector('#sri-bad').textContent,sourceReadable:true});},300);`,
        "application/javascript",
      );
    if (p === "/csp/") {
      const good = createHash("sha384")
        .update('document.querySelector("#sri-good").textContent="Allowed script executed";')
        .digest("base64");
      return send(
        200,
        html(
          "Browser integrity experiment",
          '<p id="sri-good">Pending good script</p><p id="sri-bad">Tampered script blocked</p><pre id="csp-result">Pending</pre>',
          `<script>globalThis.inlineRan=true;</script><script src="/sri-good.js" integrity="sha384-${good}"></script><script src="/sri-bad.js" integrity="sha384-${Buffer.alloc(48).toString("base64")}"></script><script src="/csp.js"></script>`,
        ),
        "text/html",
        {
          "Content-Security-Policy":
            "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'",
        },
      );
    }
    if (p === "/robots/")
      return send(
        200,
        html(
          "Robots exclusion control",
          '<p id="copyable">This text and script remain available to a normal browser.</p>',
          '<script src="/plain.js"></script>',
        ),
        "text/html",
      );
    if (p === "/baseline/" || p === "/protected/") {
      const protectedPage = p === "/protected/";
      return send(
        200,
        html(
          "Quote demonstration",
          `<p>Enter an integer from 0 to 99.</p><label>Input <input id="x" type="number" value="5" min="0" max="99"></label><button id="quote">Calculate quote</button><output id="answer">48</output><p id="service-state">${protectedPage ? "Service computation" : "Client computation"}</p>`,
          protectedPage
            ? '<script src="/protected-client.js"></script>'
            : '<script src="/plain.js"></script><script src="/baseline-client.js"></script>',
        ),
        "text/html",
      );
    }
    if (p === "/baseline-client.js")
      return send(
        200,
        'document.querySelector("#quote").onclick=()=>document.querySelector("#answer").textContent=quote(+document.querySelector("#x").value);',
        "application/javascript",
      );
    if (p === "/protected-client.js")
      return send(
        200,
        `document.querySelector('#quote').onclick=async()=>{try{const r=await fetch('http://127.0.0.1:4382/remote-quote?x='+encodeURIComponent(document.querySelector('#x').value),{credentials:'include'});if(!r.ok)throw Error('Service '+r.status);document.querySelector('#answer').textContent=(await r.json()).value;}catch(e){document.querySelector('#answer').textContent='Service unavailable';}};`,
        "application/javascript",
      );
    if (p === "/remote-quote") {
      const origin = req.headers.origin;
      if (origin !== "http://127.0.0.1:4381")
        return send(403, { error: "Research origin required" });
      return send(200, { value: quote(Number(u.searchParams.get("x"))) }, "application/json", {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        Vary: "Origin",
      });
    }
    if (p === "/rendered/")
      return send(
        200,
        html(
          "Pixel output and accessible output",
          '<canvas id="pixels" width="800" height="200" aria-label="Quote demonstration rendered as pixels"></canvas><button id="accessible">Enable accessible text</button><p id="fallback"></p>',
          `<script src="/canvas.js"></script>`,
        ),
        "text/html",
      );
    if (p === "/canvas.js")
      return send(
        200,
        `let c=document.querySelector('canvas').getContext('2d');c.fillStyle='#183044';c.fillRect(0,0,800,200);c.fillStyle='white';c.font='32px sans-serif';c.fillText('Quote result 48',40,90);document.querySelector('#accessible').onclick=()=>document.querySelector('#fallback').textContent='Quote result 48';`,
        "application/javascript",
      );
    if (p === "/broker-frame/")
      return send(
        200,
        html(
          "Isolated execution frame",
          "<p>Frame method quote is available. This is origin isolation, not protection from the browser owner.</p>",
          `<script src="/frame.js"></script>`,
        ),
        "text/html",
        {
          "Content-Security-Policy":
            "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors http://127.0.0.1:4381",
        },
      );
    if (p === "/frame.js")
      return send(
        200,
        `const allowed='http://127.0.0.1:4381';addEventListener('message',e=>{if(e.origin!==allowed)return;if(e.data.op==='quote')e.source.postMessage({id:e.data.id,result:(7*e.data.x+13)%1009},e.origin);});`,
        "application/javascript",
      );
    if (p === "/api/capsule" && req.method === "POST") {
      const data = await body(req),
        j = data.publicKey;
      const ecdh = createECDH("prime256v1");
      const pub = ecdh.generateKeys();
      const clientPoint = Buffer.concat([
        Buffer.from([4]),
        Buffer.from(j.x, "base64url"),
        Buffer.from(j.y, "base64url"),
      ]);
      const secret = ecdh.computeSecret(clientPoint),
        salt = randomBytes(16),
        info = Buffer.from("website-protection-study-v1");
      const key = Buffer.from(hkdfSync("sha256", secret, salt, info, 32)),
        iv = randomBytes(12);
      const cipher = createCipheriv("aes-256-gcm", key, iv),
        ciphertext = Buffer.concat([cipher.update(source), cipher.final(), cipher.getAuthTag()]);
      return send(200, {
        publicKey: {
          kty: "EC",
          crv: "P-256",
          x: b64(pub.subarray(1, 33)),
          y: b64(pub.subarray(33, 65)),
          ext: true,
        },
        salt: b64(salt),
        iv: b64(iv),
        ciphertext: b64(ciphertext),
      });
    }
    if (p === "/api/session" && req.method === "POST") {
      const data = await body(req),
        id = b64(randomBytes(18));
      sessions.set(id, {
        id,
        key: data.publicKey ? createPublicKey({ key: data.publicKey, format: "jwk" }) : null,
        expires: Date.now() + 180000,
        nonce: null,
        used: new Set(),
        remaining: 8,
      });
      return send(200, { id, remaining: 8, expiresMs: 180000 }, "application/json", {
        "Set-Cookie": `research_session=${id}; HttpOnly; SameSite=Strict; Path=/`,
      });
    }
    if (p === "/api/challenge") {
      const s = session(req);
      if (!s) return send(401, { error: "No authorized demo session" });
      const value = b64(randomBytes(16));
      s.nonce = { value, expires: Date.now() + 2000 };
      return send(200, { nonce: value, session: s.id, expiresMs: 2000 });
    }
    if (p === "/api/signed" && req.method === "POST") {
      const s = session(req);
      if (!s) return send(401, { error: "Session required" });
      const data = await body(req);
      if (s.used.has(data.nonce)) return send(409, { error: "Nonce already consumed" });
      if (!s.nonce || s.nonce.value !== data.nonce)
        return send(403, { error: "Unknown challenge" });
      if (Date.now() > s.nonce.expires) return send(410, { error: "Expired challenge" });
      const message = Buffer.from(`${s.id}|POST|/api/signed|${data.nonce}|${data.x}`);
      if (
        !s.key ||
        !verify(
          "sha256",
          message,
          { key: s.key, dsaEncoding: "ieee-p1363" },
          Buffer.from(data.signature || "", "base64url"),
        )
      )
        return send(403, { error: "Invalid signature" });
      s.used.add(data.nonce);
      return send(200, { value: quote(data.x), remaining: s.remaining });
    }
    if (p === "/api/oracle") {
      const s = session(req);
      if (!s) return send(401, { error: "Session required" });
      if (s.remaining <= 0) return send(429, { error: "Session query budget exhausted" });
      const x = Number(u.searchParams.get("x"));
      if (!Number.isInteger(x) || x < 0 || x > 999)
        return send(400, { error: "Domain 0 through 999" });
      s.remaining--;
      const keyed = u.searchParams.get("kind") === "keyed";
      const value = keyed
        ? createHmac("sha256", oracleKey).update(String(x)).digest("hex").slice(0, 16)
        : quote(x);
      return send(200, { value, remaining: s.remaining });
    }
    if (p === "/api/bench")
      return send(200, {
        value: quote(Number(u.searchParams.get("x") || 5)),
        serverNs: process.hrtime.bigint().toString(),
      });
    if (p === "/api/save" && req.method === "POST") {
      const data = await body(req),
        run = `browser-${Date.now()}`;
      writeFileSync(path.join(evidence, run + ".json"), JSON.stringify(data, null, 2));
      record(
        "observation",
        data.kind === "benchmark" ? "PERF" : "BROWSER",
        `Saved real browser ${data.kind || "experiment"} results.`,
        { evidence: [`evidence/${run}.json`] },
      );
      return send(200, { saved: run + ".json" });
    }
    if (p === "/environment")
      return send(200, {
        started,
        node: process.version,
        platform: os.platform(),
        release: os.release(),
        architecture: os.arch(),
        cpus: os.cpus().map((c) => c.model),
        logicalCpus: os.cpus().length,
        totalMemoryBytes: os.totalmem(),
        rssBytes: process.memoryUsage().rss,
        prototype: "Node stdlib HTTP server on loopback ports 4381 and 4382",
      });
    return send(404, { error: "Not found" });
  })().catch((e) => {
    record("failure", "SERVER", e.message);
    if (!res.headersSent) send(500, { error: e.message });
    else res.destroy();
  });
}
for (const port of [4381, 4382])
  http
    .createServer((req, res) => service(req, res, port))
    .listen(port, "127.0.0.1", () => console.log(`Research server http://127.0.0.1:${port}`));
writeFileSync(
  path.join(evidence, "server-environment.json"),
  JSON.stringify(
    {
      started,
      node: process.version,
      platform: os.platform(),
      release: os.release(),
      architecture: os.arch(),
      cpuModel: os.cpus()[0]?.model,
      logicalCpus: os.cpus().length,
      totalMemoryBytes: os.totalmem(),
    },
    null,
    2,
  ),
);
record(
  "decision",
  "LAB",
  "Started real-browser test server. No non-loopback listener or external requests.",
);
