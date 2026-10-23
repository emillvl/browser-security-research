// Program bytes and cryptographic operations live in the privileged browser parent.
const appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULRuntime);
Cu.importGlobalProperties(["crypto", "fetch", "TextEncoder", "TextDecoder"]);
const credential = "__PROVISIONING_CREDENTIAL__";
const encoder = new TextEncoder(),
  from64 = (s) =>
    Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
async function post(path, data) {
  const response = await fetch("http://127.0.0.1:45911" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const output = await response.json();
  if (!response.ok) throw Error(output.error);
  return output;
}
export const Broker = {
  program: null,
  pending: null,
  async load() {
    const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
        "deriveKey",
      ]),
      publicKey = await crypto.subtle.exportKey("jwk", pair.publicKey);
    await post("/api/enroll", { credential, publicKey });
    const capsule = await post("/api/capsule", { publicKey }),
      other = await crypto.subtle.importKey(
        "jwk",
        capsule.publicKey,
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
      ),
      key = await crypto.subtle.deriveKey(
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
    this.program = JSON.parse(
      new TextDecoder().decode(
        await crypto.subtle.decrypt(
          { name: "AES-GCM", iv: from64(capsule.iv) },
          key,
          from64(capsule.ciphertext),
        ),
      ),
    );
  },
  evaluate(input) {
    if (
      !Array.isArray(input) ||
      input.length !== 6 ||
      input.some((v) => !Number.isInteger(v) || v < 0 || v > 1000)
    )
      throw Error("Invalid input");
    let sum = 0;
    for (const tree of this.program.trees) {
      let node = tree;
      while (node.value === undefined)
        node = input[node.feature] <= node.threshold ? node.left : node.right;
      sum += node.value;
    }
    const score = Math.floor(sum / this.program.trees.length);
    return { score, band: score < 350 ? "low" : score < 650 ? "medium" : "high" };
  },
  async run(message, origin, isFrame) {
    if (origin !== "http://127.0.0.1:45911" || isFrame) return { error: "Origin or frame denied" };
    if (message.op !== "evaluate") return { error: "Operation denied" };
    try {
      if (!this.pending) this.pending = this.load();
      await this.pending;
      return {
        ok: true,
        result: this.evaluate(message.input),
        execution: { processType: appInfo.processType, pid: appInfo.processID },
      };
    } catch (error) {
      return { error: error.message };
    }
  },
};
