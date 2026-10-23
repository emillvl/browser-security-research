let pageDecryptCaptures = [];
const p = Object.getPrototypeOf(crypto.subtle),
  originalDecrypt = p.decrypt;
p.decrypt = async function (...args) {
  const bytes = await originalDecrypt.apply(this, args);
  pageDecryptCaptures.push(new TextDecoder().decode(bytes));
  return bytes;
};
function brokerCall(input, op = "evaluate") {
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID(),
      timer = setTimeout(() => {
        removeEventListener("message", listener);
        reject(Error("Broker timeout"));
      }, 10000);
    function listener(e) {
      if (
        e.source === window &&
        e.origin === location.origin &&
        e.data?.channel === "p2-response" &&
        e.data.id === id
      ) {
        clearTimeout(timer);
        removeEventListener("message", listener);
        resolve(e.data.response);
      }
    }
    addEventListener("message", listener);
    postMessage({ channel: "p2-request", id, op, input }, location.origin);
  });
}
document.querySelector("#calculate").onclick = async () => {
  try {
    document.querySelector("#result").textContent = JSON.stringify(
      await brokerCall(document.querySelector("#vector").value.split(",").map(Number)),
    );
  } catch (error) {
    document.querySelector("#result").textContent = error.message;
  }
};
async function hookControl() {
  const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, [
      "encrypt",
      "decrypt",
    ]),
    iv = crypto.getRandomValues(new Uint8Array(12)),
    bytes = new TextEncoder().encode("page positive control"),
    ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes);
  await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
  return pageDecryptCaptures.slice();
}
