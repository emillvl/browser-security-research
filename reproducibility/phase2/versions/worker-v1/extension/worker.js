importScripts("config.js");
let model, privateKey, loadPromise;
const allowed = "http://127.0.0.1:45911",
  encoder = new TextEncoder();
const from64 = (s) =>
  Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
async function post(path, data) {
  const r = await fetch(allowed + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await r.json();
  if (!r.ok) throw Error(result.error);
  return result;
}
async function loadModel() {
  const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
    "deriveKey",
  ]);
  privateKey = pair.privateKey;
  const publicKey = await crypto.subtle.exportKey("jwk", pair.publicKey);
  await post("/api/enroll", { credential: provisioningCredential, publicKey });
  const capsule = await post("/api/capsule", { publicKey });
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
      info: encoder.encode("phase2-worker-v1"),
    },
    hk,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"],
  );
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: from64(capsule.iv) },
    key,
    from64(capsule.ciphertext),
  );
  model = JSON.parse(new TextDecoder().decode(plaintext));
  return model;
}
function evaluateModel(model, input) {
  if (
    !Array.isArray(input) ||
    input.length !== 6 ||
    input.some((v) => !Number.isInteger(v) || v < 0 || v > 1000)
  )
    throw Error("Invalid input");
  let sum = 0;
  for (const tree of model.trees) {
    let node = tree;
    while (node.value === undefined)
      node = input[node.feature] <= node.threshold ? node.left : node.right;
    sum += node.value;
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
      if (!loadPromise) loadPromise = loadModel();
      await loadPromise;
      respond({ ok: true, result: evaluateModel(model, message.input) });
    } catch (error) {
      respond({ error: error.message });
    }
  })();
  return true;
});
