window.addEventListener("message", async (e) => {
  if (
    e.source !== window ||
    e.origin !== location.origin ||
    !e.data ||
    e.data.channel !== "research-broker-request"
  )
    return;
  const m = e.data;
  let response;
  try {
    response = await browser.runtime.sendMessage({ op: m.op, x: m.x });
  } catch (error) {
    response = { ok: false, error: error.message };
  }
  window.postMessage({ channel: "research-broker-response", id: m.id, response }, location.origin);
});
window.addEventListener("message", (e) => {
  if (
    e.source === window &&
    e.origin === location.origin &&
    e.data?.channel === "research-broker-ready-request"
  )
    window.postMessage(
      { channel: "research-broker-ready", extensionOrigin: browser.runtime.getURL("/") },
      location.origin,
    );
});
