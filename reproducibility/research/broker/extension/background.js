const allowedOrigin = "http://127.0.0.1:4389";
let programPromise;
const enc = new TextEncoder(),
  dec = new TextDecoder();
const from64 = (s) =>
  Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
async function post(path, data) {
  const r = await fetch(allowedOrigin + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await r.json();
  if (!r.ok) throw Error(body.error);
  return body;
}
async function load() {
  const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
    "deriveKey",
  ]);
  const publicKey = await crypto.subtle.exportKey("jwk", pair.publicKey);
  await post("/api/enroll", { publicKey, enrollmentSecret });
  const c = await post("/api/capsule", { publicKey, policy: "pinned" }),
    other = await crypto.subtle.importKey(
      "jwk",
      c.publicKey,
      { name: "ECDH", namedCurve: "P-256" },
      false,
      [],
    );
  const hk = await crypto.subtle.deriveKey(
    { name: "ECDH", public: other },
    pair.privateKey,
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
  const bytes = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: from64(c.iv) },
    aes,
    from64(c.ciphertext),
  );
  const program = JSON.parse(dec.decode(bytes));
  if (program.version !== 1 || !Array.isArray(program.code))
    throw Error("Invalid instruction format");
  return program.code;
}
function execute(b, x) {
  const stack = [];
  for (let p = 0, steps = 0; steps++ < 100; ) {
    switch (b[p++]) {
      case 0:
        if (stack.length !== 1) throw Error("Invalid stack");
        return stack.pop();
      case 1:
        stack.push(b[p++]);
        break;
      case 2:
        stack.push(stack.pop() * x);
        break;
      case 3:
        stack.push(stack.pop() + stack.pop());
        break;
      case 4: {
        const m = stack.pop();
        stack.push(stack.pop() % m);
        break;
      }
      default:
        throw Error("Invalid opcode");
    }
  }
  throw Error("Instruction limit");
}
browser.runtime.onMessage.addListener(async (m, sender) => {
  if (
    !sender.url ||
    new URL(sender.url).origin !== allowedOrigin ||
    new URL(sender.url).pathname !== "/broker/" ||
    sender.frameId !== 0
  )
    return { ok: false, error: "Origin or frame denied" };
  if (m.op !== "quote") return { ok: false, error: "Operation denied" };
  if (!Number.isInteger(m.x) || m.x < 0 || m.x > 99) return { ok: false, error: "Input denied" };
  try {
    if (!programPromise) programPromise = load();
    const code = await programPromise;
    return { ok: true, value: execute(code, m.x) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});
