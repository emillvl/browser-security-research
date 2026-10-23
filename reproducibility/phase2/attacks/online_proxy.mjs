// Copy the local fixture's public files and reuse its authenticated upstream service.
import http from "node:http";
import path from "node:path";
import { pathToFileURL } from "node:url";
const archive = process.argv[2],
  cache = new Map();
if (!archive) throw Error("An existing owned capture is required");
const { createPreviewServer } = await import(pathToFileURL(path.join(archive, "server.mjs")).href);
const replay = createPreviewServer(path.join(archive, "manifest.json"));
const counters = { upstreamRequests: 0, successfulPureExecutions: 0, cacheHits: 0 };
const send = (res, status, value) => {
  const body = JSON.stringify(value);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
};
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://127.0.0.1:45920");
    if (url.pathname === "/clone/metrics")
      return send(res, 200, { ...counters, cacheEntries: cache.size });
    if (url.pathname === "/clone/cached-score") {
      let raw = "";
      for await (const p of req) raw += p;
      const input = JSON.parse(raw).input,
        key = JSON.stringify(["score", input]);
      if (!cache.has(key)) return send(res, 503, { error: "No cached observation" });
      counters.cacheHits++;
      return send(res, 200, { result: cache.get(key), source: "Previously observed output" });
    }
    if (!url.pathname.startsWith("/api/")) return replay.emit("request", req, res);
    let body = "";
    for await (const p of req) body += p;
    const headers = { ...req.headers, origin: "http://127.0.0.1:45911" };
    delete headers.host;
    delete headers["content-length"];
    delete headers["transfer-encoding"];
    counters.upstreamRequests++;
    const upstream = await fetch("http://127.0.0.1:45911" + url.pathname + url.search, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : body,
      redirect: "manual",
    });
    const bytes = Buffer.from(await upstream.arrayBuffer()),
      outHeaders = Object.fromEntries(upstream.headers);
    delete outHeaders["content-encoding"];
    delete outHeaders["content-length"];
    delete outHeaders["transfer-encoding"];
    outHeaders["Content-Length"] = bytes.length;
    if (url.pathname === "/api/execute" && upstream.status === 200) {
      const envelope = JSON.parse(body),
        value = JSON.parse(bytes);
      if (["score", "route"].includes(envelope.payload.op) && value.result) {
        cache.set(JSON.stringify([envelope.payload.op, envelope.payload.input]), value.result);
        counters.successfulPureExecutions++;
      }
    }
    res.writeHead(upstream.status, outHeaders);
    res.end(bytes);
  } catch (error) {
    send(res, 503, { error: "The original service is unavailable" });
  }
});
server.listen(45920, "127.0.0.1", () =>
  process.stdout.write("Owned online clone listening 45920\n"),
);
