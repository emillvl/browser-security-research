import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import os from "node:os";
import { readFileSync, writeFileSync, appendFileSync, existsSync } from "node:fs";
import { randomBytes, scryptSync, timingSafeEqual, createPublicKey, verify } from "node:crypto";
import { forest, catalogue, pureOperation, canonical, hash } from "./application.mjs";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
  sessions = new Map(),
  metrics = new Map(),
  accounts = new Map();
const baseline = process.argv.includes("--baseline");
for (const [name, password, quota] of [
  ["alice", "Research-Alice-Only", 5000],
  ["bob", "Research-Bob-Only", 12],
])
  accounts.set(name, {
    name,
    salt: "research-" + name,
    password: scryptSync(password, "research-" + name, 32),
    used: 0,
    quota,
    reservations: new Map(),
    cache: new Map(),
    version: 0,
  });
const stock = new Map(catalogue.map((x) => [x.id, x.stock]));
let sequence = 0;
const sessionOf = (req) =>
  sessions.get(/(?:^|;\s*)p2_session=([^;]+)/.exec(req.headers.cookie || "")?.[1]);
const b64 = (x) => Buffer.from(x).toString("base64url");
const environment = {
  node: process.version,
  os: os.release(),
  cpu: os.cpus()[0].model,
  memory: os.totalmem(),
  pid: process.pid,
  started: new Date().toISOString(),
  baseline,
  architecture: "Authenticated single-process service; no hardware attestation",
};
const runName = "suite-" + Date.now();
writeFileSync(
  path.join(root, "evidence", runName + "-environment.json"),
  JSON.stringify(environment, null, 2),
);
function cleanExpired(account) {
  for (const r of account.reservations.values())
    if (r.state === "held" && Date.now() > r.expires) {
      r.state = "expired";
      stock.set(r.product, stock.get(r.product) + r.quantity);
      account.version++;
    }
}
function cleanAll() {
  for (const a of accounts.values()) cleanExpired(a);
}
function execute(account, payload) {
  if (!payload || typeof payload.requestId !== "string" || payload.requestId.length > 80)
    return { status: 400, output: { error: "Request identifier required" } };
  const digest = hash(payload),
    prior = account.cache.get(payload.requestId);
  if (prior) {
    if (prior.digest !== digest)
      return { status: 409, output: { error: "Identifier reused with different payload" } };
    return { status: prior.status, output: { ...prior.output, cached: true } };
  }
  if (account.used >= account.quota)
    return { status: 429, output: { error: "Account quota exhausted" } };
  account.used++;
  let result;
  try {
    result = operation(account, payload);
  } catch (error) {
    result = { status: 400, error: error.message };
  }
  const status = result.status || 200,
    output = result.error
      ? result
      : { result, account: account.name, remaining: account.quota - account.used };
  account.cache.set(payload.requestId, { digest, status, output });
  return { status, output };
}
function operation(account, payload) {
  if (payload.op === "score" || payload.op === "route")
    return pureOperation(payload.op, payload.input);
  cleanAll();
  const input = payload.input || {};
  if (payload.op === "reserve") {
    if (input.expectedVersion !== account.version)
      return { status: 409, error: "State version conflict", version: account.version };
    if (
      !stock.has(input.product) ||
      !Number.isInteger(input.quantity) ||
      input.quantity < 1 ||
      input.quantity > 10
    )
      return { status: 400, error: "Invalid reservation" };
    if (stock.get(input.product) < input.quantity)
      return { status: 409, error: "Insufficient stock" };
    const id = b64(randomBytes(16));
    stock.set(input.product, stock.get(input.product) - input.quantity);
    const r = {
      id,
      owner: account.name,
      product: input.product,
      quantity: input.quantity,
      state: "held",
      expires: Date.now() + 1800,
    };
    account.reservations.set(id, r);
    account.version++;
    return { reservation: r, version: account.version };
  }
  if (payload.op === "commit" || payload.op === "cancel") {
    const r = account.reservations.get(input.id);
    if (!r) return { status: 403, error: "Reservation not owned" };
    if (r.state !== "held") return { status: 409, error: "Reservation is " + r.state };
    r.state = payload.op === "commit" ? "committed" : "cancelled";
    if (payload.op === "cancel") stock.set(r.product, stock.get(r.product) + r.quantity);
    account.version++;
    return { reservation: r, version: account.version };
  }
  return { status: 400, error: "Unknown operation" };
}
function html(kind) {
  const protectedMode = !baseline;
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Dispatch research ${kind}</title><link rel="stylesheet" href="/suite.css"><body data-kind="${kind}" data-protected="${protectedMode}"><nav aria-label="Research applications">${["plain", "spa", "calculation", "wasm", "protected", "account", "worker", "multi"].map((n) => `<a href="/suite/${n}/">${n}</a>`).join(" ")}</nav><main><h1>Dispatch operations</h1><p id="architecture">Application: ${kind}</p><form id="login"><label>Account <input name="account" autocomplete="username" value="alice"></label><label>Password <input name="password" type="password" autocomplete="current-password"></label><button>Sign in</button></form><p id="session" aria-live="polite">Signed out</p><div id="views"><button data-view="score">Dispatch score</button><button data-view="route">Route planner</button><button data-view="stock">Reservations</button></div><section id="score-view"><h2>Dispatch score</h2><form id="score-form"><label>Six operating inputs <input id="inputs" value="100,200,300,400,500,600" required></label><button>Calculate score</button></form></section><section id="route-view" hidden><h2>Route planner</h2><form id="route-form"><label>Start <input id="start" type="number" min="0" max="23" value="0"></label><label>Destination <input id="end" type="number" min="0" max="23" value="17"></label><label>Congestion <input id="congestion" type="number" min="0" max="20" value="3"></label><button>Plan route</button></form></section><section id="stock-view" hidden><h2>Reservations</h2><form id="reserve-form"><label>Product <select id="product">${catalogue.map((p) => `<option value="${p.id}">${p.name}</option>`).join("")}</select></label><label>Quantity <input id="quantity" type="number" min="1" max="10" value="1"></label><button>Reserve stock</button></form><button id="commit">Commit reservation</button><button id="cancel">Cancel reservation</button></section><output id="output" role="status" aria-live="polite">Ready</output><p id="error" role="alert"></p><div id="embedded"></div><button id="recover">Retry initialization</button><pre id="details"></pre></main><script type="module" src="/suite-client.mjs"></script></body></html>`;
}
async function handle(req, res) {
  const start = performance.now(),
    u = new URL(req.url, "http://127.0.0.1");
  let bytes = 0;
  const send = (status, data, type = "application/json", extra = {}) => {
    const out = Buffer.isBuffer(data) || typeof data === "string" ? data : JSON.stringify(data);
    bytes = Buffer.byteLength(out);
    res.writeHead(status, {
      "Content-Type": type,
      "Content-Length": bytes,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...extra,
    });
    res.end(out);
  };
  res.on("finish", () =>
    appendFileSync(
      path.join(root, "evidence", runName + "-requests.jsonl"),
      JSON.stringify({
        time: new Date().toISOString(),
        sequence: ++sequence,
        port: req.socket.localPort,
        path: u.pathname,
        method: req.method,
        status: res.statusCode,
        bytes,
        ms: performance.now() - start,
      }) + "\n",
    ),
  );
  try {
    if (u.pathname === "/robots.txt") return send(200, "User-agent: *\nAllow: /\n", "text/plain");
    if (u.pathname === "/favicon.ico" || u.pathname === "/favicon.svg")
      return send(
        200,
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16" fill="#234"/><path d="M4 4h8v8H4z" fill="white"/></svg>',
        "image/svg+xml",
      );
    if (u.pathname === "/sitemap.xml")
      return send(
        200,
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
          ["plain", "spa", "calculation", "wasm", "protected", "account", "worker", "multi"]
            .map((kind) => "<url><loc>http://127.0.0.1:45911/suite/" + kind + "/</loc></url>")
            .join("") +
          "</urlset>",
        "application/xml",
      );
    if (u.pathname.startsWith("/suite/") && u.pathname.endsWith("/"))
      return send(200, html(u.pathname.split("/")[2]), "text/html");
    if (u.pathname === "/suite.css")
      return send(
        200,
        "body{font:16px system-ui;max-width:900px;margin:30px auto;padding:0 18px}nav{display:flex;flex-wrap:wrap;gap:12px}label{display:block;margin:12px 0}input,select,button{font:inherit;padding:8px;max-width:100%}button{margin:6px}output{display:block;margin:20px 0;white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere}section[hidden]{display:none}iframe{width:100%;box-sizing:border-box}input,select{box-sizing:border-box}@media(max-width:500px){body{margin:16px auto}}",
        "text/css",
      );
    if (u.pathname === "/suite-client.mjs")
      return send(
        200,
        readFileSync(path.join(root, "websites/suite-client.mjs")),
        "application/javascript",
      );
    if (u.pathname === "/public-workload.mjs")
      return baseline
        ? send(
            200,
            `export const model=${JSON.stringify(forest)};export function evaluate(input){if(!Array.isArray(input)||input.length!==6||input.some(v=>!Number.isInteger(v)||v<0||v>1000))throw Error('Six integers from 0 through 1000 required');let total=0;for(let tree of model.trees){while(tree.value===undefined)tree=input[tree.feature]<=tree.threshold?tree.left:tree.right;total+=tree.value;}const score=Math.floor(total/model.trees.length);return {score,band:score<350?'low':score<650?'medium':'high'}}`,
            "application/javascript",
          )
        : send(404, { error: "No program distribution" });
    if (u.pathname === "/public-route.mjs")
      return baseline
        ? send(
            200,
            readFileSync(path.join(root, "websites/route-client.mjs")),
            "application/javascript",
          )
        : send(404, { error: "No program distribution" });
    if (u.pathname === "/plan-worker.js")
      return send(
        200,
        "onmessage=e=>postMessage({id:e.data.id,normalized:e.data.input.map(Number),worker:true});",
        "application/javascript",
      );
    if (u.pathname === "/frame/")
      return send(
        200,
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Second-origin operations helper</title><p>Second-origin frame ready</p><script>addEventListener("message",e=>{if(e.origin!=="http://127.0.0.1:45911")return;e.source.postMessage({id:e.data.id,helper:"ready"},e.origin)})</script></html>',
        "text/html",
      );
    if (u.pathname === "/transform.wasm" && existsSync(path.join(root, "binary/transform.wasm")))
      return send(200, readFileSync(path.join(root, "binary/transform.wasm")), "application/wasm");
    if (u.pathname === "/environment") return send(200, environment);
    if (!u.pathname.startsWith("/api/")) return send(404, { error: "Not found" });
    let d = {};
    if (req.method === "POST") {
      let raw = "";
      for await (const p of req) {
        raw += p;
        if (raw.length > 50000) return send(413, { error: "Too large" });
      }
      d = raw ? JSON.parse(raw) : {};
    }
    if (u.pathname === "/api/login") {
      const a = accounts.get(d.account),
        candidate = scryptSync(String(d.password || ""), a?.salt || "absent", 32);
      if (!a || !timingSafeEqual(candidate, a.password))
        return send(401, { error: "Invalid credentials" });
      if (req.method !== "POST") return send(405, { error: "POST required" });
      const id = b64(randomBytes(24)),
        session = {
          id,
          account: a,
          csrf: b64(randomBytes(24)),
          expires: Date.now() + 1800000,
          key: null,
          keyId: 0,
          challenges: new Map(),
        };
      sessions.set(id, session);
      return send(
        200,
        { session: id, csrf: session.csrf, account: a.name, remaining: a.quota - a.used },
        "application/json",
        { "Set-Cookie": "p2_session=" + id + "; HttpOnly; SameSite=Strict; Path=/" },
      );
    }
    const s = sessionOf(req);
    if (u.pathname === "/api/anonymous")
      return baseline
        ? send(200, { result: pureOperation(d.op, d.input) })
        : send(404, { error: "No anonymous execution" });
    if (u.pathname === "/api/metrics/start") {
      const id = b64(randomBytes(8));
      metrics.set(id, {
        cpu: process.cpuUsage(),
        time: performance.now(),
        rss: process.memoryUsage().rss,
      });
      return send(200, { id });
    }
    if (u.pathname === "/api/metrics/stop") {
      const m = metrics.get(d.id);
      if (!m) return send(404, { error: "Window not found" });
      const cpu = process.cpuUsage(m.cpu);
      metrics.delete(d.id);
      return send(200, {
        cpuUserMs: cpu.user / 1000,
        cpuSystemMs: cpu.system / 1000,
        elapsedMs: performance.now() - m.time,
        rssBefore: m.rss,
        rssAfter: process.memoryUsage().rss,
      });
    }
    if (!s || s.expires < Date.now()) return send(401, { error: "Authenticated session required" });
    if (u.pathname === "/api/state") {
      cleanAll();
      return send(200, {
        version: s.account.version,
        reservations: [...s.account.reservations.values()],
        stock: Object.fromEntries(stock),
        remaining: s.account.quota - s.account.used,
      });
    }
    if (req.method !== "POST") return send(405, { error: "POST required" });
    if (req.headers.origin !== "http://127.0.0.1:45911" || req.headers["x-p2-csrf"] !== s.csrf)
      return send(403, { error: "Origin or CSRF denied" });
    if (u.pathname === "/api/logout") {
      sessions.delete(s.id);
      return send(200, { ok: true }, "application/json", {
        "Set-Cookie": "p2_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0",
      });
    }
    if (u.pathname === "/api/direct") {
      if (!baseline) return send(404, { error: "Proof required" });
      const v = execute(s.account, d);
      return send(v.status, v.output);
    }
    if (u.pathname === "/api/key") {
      if (d.publicKey?.kty !== "EC" || d.publicKey?.crv !== "P-256")
        return send(400, { error: "P-256 required" });
      s.key = createPublicKey({ key: d.publicKey, format: "jwk" });
      s.keyId++;
      s.challenges.clear();
      return send(200, { keyId: s.keyId });
    }
    if (u.pathname === "/api/challenge") {
      if (!s.key) return send(403, { error: "Key enrollment required" });
      for (const [k, v] of s.challenges) if (Date.now() > v.expires + 3000) s.challenges.delete(k);
      if ([...s.challenges.values()].filter((c) => !c.used && c.expires >= Date.now()).length >= 64)
        return send(429, { error: "Outstanding challenge cap" });
      if (!/^[0-9a-f]{64}$/.test(d.hash)) return send(400, { error: "Payload digest required" });
      const nonce = b64(randomBytes(18)),
        entry = { hash: d.hash, expires: Date.now() + 1500, used: false, keyId: s.keyId };
      s.challenges.set(nonce, entry);
      return send(200, { nonce, session: s.id, keyId: s.keyId, expiresMs: 1500 });
    }
    if (u.pathname === "/api/execute") {
      const c = s.challenges.get(d.nonce);
      if (!c) return send(403, { error: "Unknown challenge" });
      if (c.used) return send(409, { error: "Challenge consumed" });
      if (Date.now() > c.expires) return send(410, { error: "Challenge expired" });
      if (d.keyId !== s.keyId || c.keyId !== s.keyId) return send(403, { error: "Retired key" });
      const digest = hash(d.payload);
      if (digest !== c.hash) return send(403, { error: "Input binding failed" });
      const message = Buffer.from(`${s.id}|POST|/api/execute|${d.nonce}|${s.keyId}|${digest}`);
      if (
        !verify(
          "sha256",
          message,
          { key: s.key, dsaEncoding: "ieee-p1363" },
          Buffer.from(d.signature || "", "base64url"),
        )
      )
        return send(403, { error: "Signature failed" });
      c.used = true;
      const value = execute(s.account, d.payload);
      return send(value.status, value.output);
    }
    return send(404, { error: "Not found" });
  } catch (error) {
    return send(400, { error: error.message });
  }
}
for (const port of [45911, 45912]) {
  const server = http.createServer(handle);
  server.on("error", (e) => {
    process.stderr.write(e.stack + "\n");
    process.exitCode = 1;
  });
  server.listen(port, "127.0.0.1", () =>
    process.stdout.write(`Phase II suite listening 127.0.0.1:${port}\n`),
  );
}
