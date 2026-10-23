const enc = new TextEncoder(),
  dec = new TextDecoder(),
  proto = Object.getPrototypeOf(crypto.subtle),
  originalDecrypt = proto.decrypt;
let copied = [];
proto.decrypt = async function (...args) {
  const out = await originalDecrypt.apply(this, args);
  copied.push(dec.decode(out));
  return out;
};
const from64 = (s) =>
  Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const request = (op, x, extra = {}) =>
  new Promise((resolve, reject) => {
    const id = crypto.randomUUID(),
      timer = setTimeout(() => {
        removeEventListener("message", listener);
        reject(Error("Message timeout"));
      }, 5000);
    function listener(e) {
      if (
        e.source === window &&
        e.origin === location.origin &&
        e.data?.channel === "research-broker-response" &&
        e.data.id === id
      ) {
        clearTimeout(timer);
        removeEventListener("message", listener);
        resolve(e.data.response);
      }
    }
    addEventListener("message", listener);
    postMessage({ channel: "research-broker-request", id, op, x, ...extra }, location.origin);
  });
async function post(data) {
  const r = await fetch("http://127.0.0.1:4389/api/capsule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return { status: r.status, body: await r.json() };
}
async function decrypt(c, privateKey) {
  const other = await crypto.subtle.importKey(
      "jwk",
      c.publicKey,
      { name: "ECDH", namedCurve: "P-256" },
      false,
      [],
    ),
    hk = await crypto.subtle.deriveKey(
      { name: "ECDH", public: other },
      privateKey,
      { name: "HKDF" },
      false,
      ["deriveKey"],
    );
  const aes = await crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: from64(c.salt), info: enc.encode("broker-study-v1") },
    hk,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"],
  );
  return dec.decode(
    await crypto.subtle.decrypt({ name: "AES-GCM", iv: from64(c.iv) }, aes, from64(c.ciphertext)),
  );
}
let extensionOrigin;
addEventListener("message", (e) => {
  if (
    e.source === window &&
    e.origin === location.origin &&
    e.data?.channel === "research-broker-ready"
  )
    extensionOrigin = e.data.extensionOrigin;
});
setInterval(() => {
  if (!extensionOrigin) postMessage({ channel: "research-broker-ready-request" }, location.origin);
}, 100);
document.querySelector("#run").onclick = async () => {
  document.querySelector("#status").textContent = "Running";
  const result = {
    time: new Date().toISOString(),
    origin: location.origin,
    userAgent: navigator.userAgent,
  };
  try {
    if (location.port === "4390") {
      result.actualOtherOrigin = await request("quote", 5, {
        claimedOrigin: "http://127.0.0.1:4389",
      });
    } else {
      const first = await request("quote", 5);
      result.normal = first;
      result.pageDecryptHookCapturesDuringBroker = copied.length;
      result.exportRequest = await request("export", 5);
      result.invalidInput = await request("quote", 100);
      result.pageGlobals = {
        program: typeof window.program,
        programPromise: typeof window.programPromise,
        browserRuntime: typeof window.browser,
      };
      result.extensionOrigin = extensionOrigin;
      try {
        const r = await fetch(extensionOrigin + "background.js");
        result.pageFetchBackground = { status: r.status, text: await r.text() };
      } catch (e) {
        result.pageFetchBackground = { error: e.name };
      }
      const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
          "deriveKey",
        ]),
        publicKey = await crypto.subtle.exportKey("jwk", pair.publicKey);
      result.servicePolicy = await (await fetch("/policy")).json();
      const open = await post({ publicKey, policy: "open" });
      result.unprovisionedOpenPolicy = { status: open.status };
      if (open.status === 200)
        result.unprovisionedOpenPolicy.plaintext = await decrypt(open.body, pair.privateKey);
      else result.unprovisionedOpenPolicy.error = open.body.error;
      const beforePositive = copied.length,
        positiveKey = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, [
          "encrypt",
          "decrypt",
        ]),
        positiveIV = crypto.getRandomValues(new Uint8Array(12)),
        positiveCipher = await crypto.subtle.encrypt(
          { name: "AES-GCM", iv: positiveIV },
          positiveKey,
          enc.encode("page hook positive control"),
        );
      await crypto.subtle.decrypt({ name: "AES-GCM", iv: positiveIV }, positiveKey, positiveCipher);
      result.pageDecryptHookPositiveControl = copied.length - beforePositive;
      result.unprovisionedPinnedPolicy = await post({ publicKey, policy: "pinned" });
      const enroll = await fetch("/api/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ publicKey }),
      });
      result.missingProvisioningCredential = { status: enroll.status, body: await enroll.json() };
      const y0 = await request("quote", 0),
        y1 = await request("quote", 1),
        a = y1.value - y0.value,
        b = y0.value;
      let matches = 0;
      for (let x = 2; x < 100; x++) if ((a * x + b) % 1009 === (7 * x + 13) % 1009) matches++;
      result.learnedModel = {
        queries: 2,
        a,
        b,
        heldoutReferenceMatches: matches,
        heldoutReferenceTotal: 98,
      };
      let brokerMatches = 0;
      for (let x = 0; x < 100; x++) {
        const r = await request("quote", x);
        if (r.ok && r.value === (7 * x + 13) % 1009) brokerMatches++;
      }
      result.brokerMatches = brokerMatches;
      result.brokerTotal = 100;
      const timings = [];
      for (let i = 0; i < 18; i++) {
        const start = performance.now();
        for (let j = 0; j < 100; j++) {
          const r = await request("quote", j);
          if (!r.ok) throw Error(r.error);
        }
        const elapsed = performance.now() - start;
        if (i >= 3) timings.push(elapsed);
      }
      result.cachedBrokerBatchSamplesMs = timings;
      result.callsPerBatch = 100;
      result.warmupBatches = 3;
      result.policy =
        "Temporary extension with opaque result-only messaging, strict extension CSP and operator-provisioned recipient key. This is not hardware attestation or secrecy from a browser owner.";
    }
    document.querySelector("#result").textContent = JSON.stringify(result, null, 2);
    document.querySelector("#status").textContent = "Complete";
  } catch (e) {
    result.error = e.stack;
    document.querySelector("#result").textContent = JSON.stringify(result, null, 2);
    document.querySelector("#status").textContent = "Failed";
  }
};
