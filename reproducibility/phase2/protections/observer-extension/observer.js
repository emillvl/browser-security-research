// This separate extension has page access and no debugger or background access permission.
const observed = [],
  decrypted = [];
let forge = false,
  externalResult = null,
  controlResult = null;
const subtlePrototype = Object.getPrototypeOf(crypto.subtle),
  originalDecrypt = subtlePrototype.decrypt;
subtlePrototype.decrypt = async function (...args) {
  const bytes = await originalDecrypt.apply(this, args);
  decrypted.push(new TextDecoder().decode(bytes));
  return bytes;
};
function snapshot() {
  document.documentElement.dataset.p2Observer = JSON.stringify({
    observed,
    decrypted,
    externalResult,
    controlResult,
    modelType: typeof model,
    privateKeyType: typeof privateKey,
    extensionId: chrome.runtime.id,
  });
}
addEventListener("message", (event) => {
  if (
    event.source !== window ||
    event.origin !== location.origin ||
    !["p2-request", "p2-response"].includes(event.data?.channel)
  )
    return;
  observed.push(JSON.parse(JSON.stringify(event.data)));
  if (forge && event.data.channel === "p2-request")
    postMessage(
      {
        channel: "p2-response",
        id: event.data.id,
        response: { ok: true, result: { score: -666, band: "observer-modified" } },
      },
      location.origin,
    );
  snapshot();
});
addEventListener("p2-observer-command", async (event) => {
  try {
    const request = JSON.parse(event.detail);
    if (request.op === "control") {
      const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, [
          "encrypt",
          "decrypt",
        ]),
        iv = crypto.getRandomValues(new Uint8Array(12)),
        plain = new TextEncoder().encode("observer positive control");
      const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plain);
      await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, encrypted);
      controlResult = "complete";
    }
    if (request.op === "external-export")
      await new Promise((resolve) =>
        chrome.runtime.sendMessage(request.extensionId, { op: "export" }, (response) => {
          externalResult = {
            response: response || null,
            error: chrome.runtime.lastError?.message || null,
          };
          resolve();
        }),
      );
    if (request.op === "forge") forge = !!request.enabled;
    snapshot();
  } catch (error) {
    externalResult = { error: error.message };
    snapshot();
  }
});
if (document.documentElement) snapshot();
else addEventListener("DOMContentLoaded", snapshot, { once: true });
