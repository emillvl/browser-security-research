window.addEventListener("message", (e) => {
  if (e.source !== window || e.origin !== location.origin || e.data?.channel !== "p2-request")
    return;
  chrome.runtime.sendMessage({ op: e.data.op, input: e.data.input }, (response) =>
    window.postMessage(
      {
        channel: "p2-response",
        id: e.data.id,
        response: response || { error: chrome.runtime.lastError?.message },
      },
      location.origin,
    ),
  );
});
// Readiness is a test synchronization signal, not an authorization decision.
function markReady() {
  document.documentElement.dataset.p2ExtensionReady = "true";
}
if (document.documentElement) markReady();
else addEventListener("DOMContentLoaded", markReady, { once: true });
