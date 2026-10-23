import http from "node:http";
import { readFileSync, writeFileSync, appendFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  randomBytes,
  createECDH,
  hkdfSync,
  createCipheriv,
  createHash,
  timingSafeEqual,
} from "node:crypto";
const root = path.dirname(fileURLToPath(import.meta.url)),
  ev = path.join(root, "../evidence");
mkdirSync(ev, { recursive: true });
const bootstrap = randomBytes(32).toString("hex");
let pinned = null;
const openEnabled = !process.argv.includes("--pinned-only");
writeFileSync(
  path.join(root, "extension/config.js"),
  `const enrollmentSecret=${JSON.stringify(bootstrap)};\n`,
);
const program = Buffer.from(
  JSON.stringify({ version: 1, code: [1, 7, 2, 1, 13, 3, 1, 1009, 4, 0] }),
);
const b64 = (x) => Buffer.from(x).toString("base64url"),
  fingerprint = (j) =>
    createHash("sha256")
      .update(j.x + "|" + j.y)
      .digest("hex");
const capsule = (j) => {
  const e = createECDH("prime256v1"),
    pub = e.generateKeys(),
    shared = e.computeSecret(
      Buffer.concat([
        Buffer.from([4]),
        Buffer.from(j.x, "base64url"),
        Buffer.from(j.y, "base64url"),
      ]),
    );
  const salt = randomBytes(16),
    iv = randomBytes(12),
    key = Buffer.from(hkdfSync("sha256", shared, salt, Buffer.from("broker-study-v1"), 32)),
    c = createCipheriv("aes-256-gcm", key, iv);
  return {
    publicKey: {
      kty: "EC",
      crv: "P-256",
      x: b64(pub.subarray(1, 33)),
      y: b64(pub.subarray(33, 65)),
      ext: true,
    },
    salt: b64(salt),
    iv: b64(iv),
    ciphertext: b64(Buffer.concat([c.update(program), c.final(), c.getAuthTag()])),
  };
};
async function handler(req, res) {
  let status = 500,
    output = "";
  const u = new URL(req.url, "http://127.0.0.1");
  const send = (s, data, type = "application/json") => {
    status = s;
    output = Buffer.isBuffer(data) ? data : typeof data === "string" ? data : JSON.stringify(data);
    res.writeHead(s, {
      "Content-Type": type,
      "Content-Length": Buffer.byteLength(output),
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    res.end(output);
  };
  res.on("finish", () =>
    appendFileSync(
      path.join(ev, "broker-requests.jsonl"),
      JSON.stringify({
        time: new Date().toISOString(),
        port: req.socket.localPort,
        path: u.pathname,
        method: req.method,
        status,
        bytes: Buffer.byteLength(output),
      }) + "\n",
    ),
  );
  try {
    if (u.pathname === "/policy")
      return send(200, {
        openRecipientEnabled: openEnabled,
        recipientAuthorization: "Operator-provisioned ephemeral key",
        hardwareAttestation: false,
      });
    if (u.pathname === "/broker/")
      return send(
        200,
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Execution broker experiment</title><body><h1>Execution broker experiment</h1><button id="run">Run broker tests</button><p id="status">Ready</p><pre id="result"></pre><script src="/page.js"></script></body></html>',
        "text/html",
      );
    if (u.pathname === "/page.js")
      return send(200, readFileSync(path.join(root, "page.js")), "application/javascript");
    if (u.pathname === "/api/capsule" || u.pathname === "/api/enroll") {
      if (req.method !== "POST") return send(405, { error: "POST required" });
      let raw = "";
      for await (const c of req) {
        raw += c;
        if (raw.length > 8192) return send(413, { error: "Too large" });
      }
      const d = JSON.parse(raw),
        j = d.publicKey;
      if (
        !j ||
        j.kty !== "EC" ||
        j.crv !== "P-256" ||
        typeof j.x !== "string" ||
        typeof j.y !== "string"
      )
        return send(400, { error: "P-256 public key required" });
      const fp = fingerprint(j);
      if (u.pathname === "/api/enroll") {
        const supplied = Buffer.from(d.enrollmentSecret || ""),
          expected = Buffer.from(bootstrap);
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
          return send(401, { error: "Provisioning credential required" });
        if (pinned && pinned !== fp) return send(409, { error: "A key is already provisioned" });
        pinned = fp;
        return send(200, { enrolled: true });
      }
      if (d.policy === "open" && !openEnabled)
        return send(403, { error: "Open recipient policy is disabled" });
      if (d.policy !== "open" && fp !== pinned)
        return send(403, { error: "Recipient key not provisioned" });
      return send(200, capsule(j));
    }
    return send(404, { error: "Not found" });
  } catch (e) {
    return send(400, { error: e.message });
  }
}
for (const port of [4389, 4390])
  http
    .createServer(handler)
    .listen(port, "127.0.0.1", () =>
      process.stdout.write(`Broker research listening 127.0.0.1:${port}\n`),
    );
appendFileSync(
  path.join(root, "../chronology.jsonl"),
  JSON.stringify({
    time: new Date().toISOString(),
    kind: "decision",
    experiment: "E21",
    claim:
      "Started isolated extension-broker service with open-recipient control and explicitly provisioned recipient policy.",
  }) + "\n",
);
