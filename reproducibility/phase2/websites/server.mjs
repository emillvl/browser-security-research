import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync, writeFileSync, appendFileSync } from "node:fs";
import {
  randomBytes,
  createECDH,
  createCipheriv,
  hkdfSync,
  createHash,
  timingSafeEqual,
} from "node:crypto";
import { fixtureModel, evaluateModel, vector } from "./workload.mjs";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
  model = fixtureModel(),
  credential = process.env.P2_RESEARCH_CREDENTIAL || randomBytes(32).toString("hex"),
  recipients = new Set();
const b64 = (x) => Buffer.from(x).toString("base64url"),
  fingerprint = (j) =>
    createHash("sha256")
      .update(j.x + "|" + j.y)
      .digest("hex");
writeFileSync(
  path.join(root, "protections/extension/config.js"),
  `const provisioningCredential=${JSON.stringify(credential)};\n`,
);
writeFileSync(
  path.join(root, "evidence/ground-truth-" + Date.now() + ".json"),
  JSON.stringify(
    {
      model,
      vectors: Array.from({ length: 100 }, (_, i) => ({
        input: vector(i),
        output: evaluateModel(model, vector(i)),
      })),
    },
    null,
    2,
  ),
);
const page =
  '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Dispatch model worker test</title><body><nav><a href="/worker-test/">Worker calculation</a></nav><main><h1>Dispatch model worker test</h1><p>Controlled six-feature decision model.</p><label>Feature vector <input id="vector" value="100,200,300,400,500,600"></label><button id="calculate">Calculate</button><output id="result" aria-live="polite"></output><script src="/page.js"></script></main></body></html>';
async function handler(req, res) {
  const start = performance.now(),
    u = new URL(req.url, "http://127.0.0.1");
  let bytes = 0;
  const send = (status, data, type = "application/json") => {
    const out = typeof data === "string" || Buffer.isBuffer(data) ? data : JSON.stringify(data);
    bytes = Buffer.byteLength(out);
    res.writeHead(status, {
      "Content-Type": type,
      "Content-Length": bytes,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    res.end(out);
  };
  res.on("finish", () =>
    appendFileSync(
      path.join(root, "evidence/requests.jsonl"),
      JSON.stringify({
        time: new Date().toISOString(),
        port: req.socket.localPort,
        method: req.method,
        path: u.pathname,
        status: res.statusCode,
        bytes,
        elapsedMs: performance.now() - start,
      }) + "\n",
    ),
  );
  try {
    if (u.pathname === "/robots.txt") return send(200, "User-agent: *\nAllow: /\n", "text/plain");
    if (u.pathname === "/sitemap.xml") {
      const routes = ["worker-test", "native-test"],
        listed = routes.includes(process.env.P2_CAPTURE_ROUTE)
          ? [process.env.P2_CAPTURE_ROUTE]
          : routes;
      return send(
        200,
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
          listed.map((route) => `<url><loc>http://127.0.0.1:45911/${route}/</loc></url>`).join("") +
          "</urlset>",
        "application/xml",
      );
    }
    if (u.pathname === "/favicon.ico")
      return send(
        200,
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16"/></svg>',
        "image/svg+xml",
      );
    if (u.pathname === "/worker-test/") return send(200, page, "text/html");
    if (u.pathname === "/native-test/")
      return send(
        200,
        page
          .replace("<body>", '<body data-broker="native">')
          .replaceAll("Dispatch model worker test", "Dispatch model browser component test")
          .replaceAll("/worker-test/", "/native-test/"),
        "text/html",
      );
    if (u.pathname === "/page.js")
      return send(200, readFileSync(path.join(root, "websites/page.js")), "application/javascript");
    if (u.pathname === "/benchmark/model")
      return process.env.P2_BENCHMARK === "1"
        ? send(200, model)
        : send(404, { error: "No plaintext distribution" });
    if (u.pathname === "/api/public-model")
      return send(200, { error: "The model is not public" }, "application/json");
    if (u.pathname === "/api/enroll" || u.pathname === "/api/capsule") {
      if (req.method !== "POST") return send(405, { error: "POST required" });
      let raw = "";
      for await (const part of req) {
        raw += part;
        if (raw.length > 10000) return send(413, { error: "Request too large" });
      }
      const d = JSON.parse(raw),
        j = d.publicKey;
      if (!j || j.crv !== "P-256") return send(400, { error: "P-256 key required" });
      const id = fingerprint(j);
      if (u.pathname === "/api/enroll") {
        const supplied = Buffer.from(d.credential || ""),
          expected = Buffer.from(credential);
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
          return send(401, { error: "Provisioning required" });
        recipients.add(id);
        return send(200, { enrolled: true });
      }
      if (!recipients.has(id)) return send(403, { error: "Recipient not enrolled" });
      const e = createECDH("prime256v1"),
        pub = e.generateKeys(),
        secret = e.computeSecret(
          Buffer.concat([
            Buffer.from([4]),
            Buffer.from(j.x, "base64url"),
            Buffer.from(j.y, "base64url"),
          ]),
        ),
        salt = randomBytes(16),
        iv = randomBytes(12),
        key = Buffer.from(hkdfSync("sha256", secret, salt, Buffer.from("phase2-worker-v1"), 32)),
        cipher = createCipheriv("aes-256-gcm", key, iv);
      const ciphertext = Buffer.concat([
        cipher.update(JSON.stringify(model)),
        cipher.final(),
        cipher.getAuthTag(),
      ]);
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
    return send(404, { error: "Not found" });
  } catch (error) {
    return send(400, { error: error.message });
  }
}
for (const port of [45911, 45912]) {
  const server = http.createServer(handler);
  server.on("error", (error) => {
    process.stderr.write(error.stack + "\n");
    process.exitCode = 1;
  });
  server.listen(port, "127.0.0.1", () =>
    process.stdout.write(`Phase II owned site listening 127.0.0.1:${port}\n`),
  );
}
