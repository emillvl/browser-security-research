// Separate recipient-approval experiment. Administrative authority is never given to the page or extension.
import http from "node:http";
import { readFileSync, writeFileSync, appendFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  randomBytes,
  generateKeyPairSync,
  createECDH,
  createCipheriv,
  hkdfSync,
  createHash,
  sign,
  timingSafeEqual,
} from "node:crypto";
import { fixtureModel } from "./workload.mjs";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
  admin = process.env.P2_ADMIN_TOKEN;
if (!admin) throw Error("Research administrator token required");
const credential = randomBytes(32).toString("hex"),
  approved = new Set(),
  signer = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
let version = 1,
  epoch = 1;
const b64 = (x) => Buffer.from(x).toString("base64url"),
  fingerprint = (j) =>
    createHash("sha256")
      .update(j.x + "|" + j.y)
      .digest("hex"),
  record = path.join(root, "evidence", "provisioning-" + Date.now() + "-requests.jsonl");
writeFileSync(
  path.join(root, "protections/extension-v2/config.js"),
  `const provisioningCredential=${JSON.stringify(credential)};\nconst issuerKey=${JSON.stringify(signer.publicKey.export({ format: "jwk" }))};\n`,
);
const page =
  '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Approved recipient research</title><body><main><h1>Approved recipient calculation</h1><label>Feature vector <input id="vector" value="100,200,300,400,500,600"></label><button id="calculate">Calculate</button><output id="result" aria-live="polite"></output><script src="/page.js"></script></main></body></html>';
async function handle(req, res) {
  const start = performance.now(),
    u = new URL(req.url, "http://127.0.0.1");
  let bytes = 0;
  const send = (status, value, type = "application/json") => {
    const body = typeof value === "string" ? value : JSON.stringify(value);
    bytes = Buffer.byteLength(body);
    res.writeHead(status, {
      "Content-Type": type,
      "Content-Length": bytes,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    res.end(body);
  };
  res.on("finish", () =>
    appendFileSync(
      record,
      JSON.stringify({
        path: u.pathname,
        port: req.socket.localPort,
        status: res.statusCode,
        bytes,
        ms: performance.now() - start,
      }) + "\n",
    ),
  );
  try {
    if (u.pathname === "/robots.txt") return send(200, "User-agent: *\nAllow: /\n", "text/plain");
    if (u.pathname === "/sitemap.xml")
      return send(
        200,
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>http://127.0.0.1:45911/broker-v2/</loc></url></urlset>',
        "application/xml",
      );
    if (u.pathname === "/favicon.ico")
      return send(
        200,
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16"/></svg>',
        "image/svg+xml",
      );
    if (u.pathname === "/broker-v2/") return send(200, page, "text/html");
    if (u.pathname === "/page.js")
      return send(
        200,
        readFileSync(path.join(root, "websites/page.js"), "utf8"),
        "application/javascript",
      );
    if (u.pathname === "/benchmark/model")
      return process.env.P2_BENCHMARK === "1"
        ? send(200, fixtureModel(12648430 + (version - 1) * 9001))
        : send(404, { error: "No plaintext distribution" });
    let data = {};
    if (req.method === "POST") {
      let raw = "";
      for await (const part of req) {
        raw += part;
        if (raw.length > 20000) return send(413, { error: "Too large" });
      }
      data = JSON.parse(raw || "{}");
    }
    if (u.pathname.startsWith("/admin/")) {
      if (req.headers.authorization !== "Bearer " + admin)
        return send(401, { error: "Administrator authorization required" });
      if (u.pathname === "/admin/approve") {
        approved.add(data.fingerprint);
        return send(200, { approved: true });
      }
      if (u.pathname === "/admin/revoke") {
        approved.delete(data.fingerprint);
        return send(200, { revoked: true });
      }
      if (u.pathname === "/admin/publish") {
        if (!Number.isInteger(data.version) || data.version <= version)
          return send(409, { error: "Version must increase" });
        version = data.version;
        epoch++;
        return send(200, { version, epoch });
      }
      return send(404, { error: "Unknown administrator operation" });
    }
    if (u.pathname === "/api/enroll" || u.pathname === "/api/capsule") {
      if (req.method !== "POST") return send(405, { error: "POST required" });
      const j = data.publicKey;
      if (j?.kty !== "EC" || j.crv !== "P-256")
        return send(400, { error: "P-256 public key required" });
      const id = fingerprint(j);
      if (u.pathname === "/api/enroll") {
        const given = Buffer.from(data.credential || ""),
          expected = Buffer.from(credential);
        if (given.length !== expected.length || !timingSafeEqual(given, expected))
          return send(401, { error: "Provisioning credential required" });
        if (!approved.has(id)) return send(403, { error: "Recipient key not approved" });
        return send(200, { enrolled: true });
      }
      if (!approved.has(id)) return send(403, { error: "Recipient key not approved" });
      const peer = createECDH("prime256v1"),
        pub = peer.generateKeys(),
        salt = randomBytes(16),
        iv = randomBytes(12),
        shared = peer.computeSecret(
          Buffer.concat([
            Buffer.from([4]),
            Buffer.from(j.x, "base64url"),
            Buffer.from(j.y, "base64url"),
          ]),
        );
      const key = Buffer.from(
          hkdfSync("sha256", shared, salt, Buffer.from("phase2-approved-v2"), 32),
        ),
        cipher = createCipheriv("aes-256-gcm", key, iv),
        model = fixtureModel(12648430 + (version - 1) * 9001);
      const payload = { model, version, epoch, expires: Date.now() + 1200, recipient: id },
        ciphertext = Buffer.concat([
          cipher.update(JSON.stringify(payload)),
          cipher.final(),
          cipher.getAuthTag(),
        ]);
      const result = {
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
      };
      const message = [
        result.publicKey.x,
        result.publicKey.y,
        result.salt,
        result.iv,
        result.ciphertext,
      ].join("|");
      result.signature = b64(
        sign("sha256", Buffer.from(message), { key: signer.privateKey, dsaEncoding: "ieee-p1363" }),
      );
      return send(200, result);
    }
    return send(404, { error: "Not found" });
  } catch (error) {
    send(400, { error: error.message });
  }
}
for (const port of [45911, 45912]) {
  const server = http.createServer(handle);
  server.on("error", (e) => {
    process.stderr.write(e.stack);
    process.exitCode = 1;
  });
  server.listen(port, "127.0.0.1", () =>
    process.stdout.write("Approved-recipient service " + port + "\n"),
  );
}
