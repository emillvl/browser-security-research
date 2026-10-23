importScripts("config.js");
const allowed = "http://127.0.0.1:45911",
  encoder = new TextEncoder(),
  decoder = new TextDecoder(),
  from64 = (s) =>
    Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
let privateKey,
  publicKey,
  model,
  expires = 0,
  highestVersion = 0,
  pending,
  lastCapsule;
async function post(path, data) {
  const r = await fetch(allowed + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
    v = await r.json();
  if (!r.ok) throw Error(v.error);
  return v;
}
async function ensurePair() {
  if (privateKey) return;
  const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
    "deriveKey",
  ]);
  privateKey = pair.privateKey;
  publicKey = await crypto.subtle.exportKey("jwk", pair.publicKey);
}
async function installCapsule(capsule) {
  const trusted = await crypto.subtle.importKey(
    "jwk",
    issuerKey,
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["verify"],
  );
  const message = [
    capsule.publicKey.x,
    capsule.publicKey.y,
    capsule.salt,
    capsule.iv,
    capsule.ciphertext,
  ].join("|");
  if (
    !(await crypto.subtle.verify(
      { name: "ECDSA", hash: "SHA-256" },
      trusted,
      from64(capsule.signature),
      encoder.encode(message),
    ))
  )
    throw Error("Issuer signature failed");
  const peer = await crypto.subtle.importKey(
      "jwk",
      capsule.publicKey,
      { name: "ECDH", namedCurve: "P-256" },
      false,
      [],
    ),
    hk = await crypto.subtle.deriveKey(
      { name: "ECDH", public: peer },
      privateKey,
      { name: "HKDF" },
      false,
      ["deriveKey"],
    );
  const key = await crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: from64(capsule.salt),
      info: encoder.encode("phase2-approved-v2"),
    },
    hk,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"],
  );
  const payload = JSON.parse(
    decoder.decode(
      await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: from64(capsule.iv) },
        key,
        from64(capsule.ciphertext),
      ),
    ),
  );
  if (payload.version < highestVersion) throw Error("Program rollback refused");
  if (payload.expires <= Date.now()) throw Error("Program lease expired");
  highestVersion = payload.version;
  model = payload.model;
  expires = payload.expires;
  lastCapsule = capsule;
  return { version: highestVersion, expires };
}
async function refresh() {
  await ensurePair();
  await post("/api/enroll", { credential: provisioningCredential, publicKey });
  return installCapsule(await post("/api/capsule", { publicKey }));
}
function rotateKeys() {
  privateKey = null;
  publicKey = null;
  model = null;
  expires = 0;
  pending = null;
}
function evaluateModel(input) {
  if (
    !Array.isArray(input) ||
    input.length !== 6 ||
    input.some((v) => !Number.isInteger(v) || v < 0 || v > 1000)
  )
    throw Error("Six integers required");
  let sum = 0;
  for (let n of model.trees) {
    while (n.value === undefined) n = input[n.feature] <= n.threshold ? n.left : n.right;
    sum += n.value;
  }
  const score = Math.floor(sum / model.trees.length);
  return { score, band: score < 350 ? "low" : score < 650 ? "medium" : "high" };
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (!sender.url || new URL(sender.url).origin !== allowed || sender.frameId !== 0) {
    respond({ error: "Origin or context denied" });
    return;
  }
  if (message.op !== "evaluate") {
    respond({ error: "Operation denied" });
    return;
  }
  (async () => {
    try {
      if (!model || Date.now() >= expires) {
        if (!pending) pending = refresh().finally(() => (pending = null));
        await pending;
      }
      respond({ ok: true, result: evaluateModel(message.input), version: highestVersion });
    } catch (error) {
      respond({ error: error.message });
    }
  })();
  return true;
});
