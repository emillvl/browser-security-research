// Public presentation and request protocol. Protected deployments receive no model.
const $ = (selector) => document.querySelector(selector),
  protectedMode = document.body.dataset.protected === "true",
  kind = document.body.dataset.kind;
const encoder = new TextEncoder(),
  canonical = (value) =>
    Array.isArray(value)
      ? "[" + value.map(canonical).join(",") + "]"
      : value !== null && typeof value === "object"
        ? "{" +
          Object.keys(value)
            .sort()
            .map((k) => JSON.stringify(k) + ":" + canonical(value[k]))
            .join(",") +
          "}"
        : JSON.stringify(value);
const to64 = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
let session = null,
  pair = null,
  keyId = 0,
  local = null,
  routing = null,
  worker = null,
  wasm = null,
  version = 0,
  reservation = null,
  initializing = null;
const history = [];
async function request(path, data, headers = {}) {
  const response = await fetch(path, {
    method: data === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-P2-CSRF": session.csrf } : {}),
      ...headers,
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const value = await response.json();
  if (!response.ok) {
    const error = Error(value.error || response.status);
    error.status = response.status;
    throw error;
  }
  return value;
}
async function enroll() {
  pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const value = await request("/api/key", {
    publicKey: await crypto.subtle.exportKey("jwk", pair.publicKey),
  });
  keyId = value.keyId;
}
async function login(account, password) {
  session = await request("/api/login", { account, password });
  await enroll();
  const marker = $("#session,#signed-in");
  marker.textContent = "Signed in as " + session.account;
  marker.id = "signed-in";
  return session.account;
}
async function prepare(payload) {
  if (!session) throw Error("Sign in to continue");
  const digest = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(canonical(payload)))),
    (x) => x.toString(16).padStart(2, "0"),
  ).join("");
  const c = await request("/api/challenge", { hash: digest });
  const message = encoder.encode(
    `${session.session}|POST|/api/execute|${c.nonce}|${keyId}|${digest}`,
  );
  const signature = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    pair.privateKey,
    message,
  );
  return { nonce: c.nonce, keyId, signature: to64(signature), payload };
}
async function execute(payload) {
  return protectedMode
    ? request("/api/execute", await prepare(payload))
    : request("/api/direct", payload);
}
async function normalize(input) {
  if (!worker) return input;
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID(),
      timer = setTimeout(() => {
        worker.removeEventListener("message", handler);
        reject(Error("Worker response timed out"));
      }, 3000);
    function handler(e) {
      if (e.data.id !== id) return;
      clearTimeout(timer);
      worker.removeEventListener("message", handler);
      resolve(e.data.normalized);
    }
    worker.addEventListener("message", handler);
    worker.postMessage({ id, input });
  });
}
async function calculate(op, input, requestId = crypto.randomUUID()) {
  await initialize();
  if (op === "score") input = await normalize(input);
  if (!protectedMode && op === "score") return { result: local.evaluate(input) };
  if (!protectedMode && op === "route") return { result: routing.planRoute(input) };
  return execute({ op, input, requestId });
}
async function initialize() {
  if (initializing) return initializing;
  initializing = (async () => {
    if (!protectedMode) {
      [local, routing] = await Promise.all([
        import("/public-workload.mjs"),
        import("/public-route.mjs"),
      ]);
    }
    if (kind === "worker" || kind === "multi") worker = new Worker("/plan-worker.js");
    if (kind === "wasm")
      wasm = (await WebAssembly.instantiateStreaming(fetch("/transform.wasm"))).instance.exports;
    if (kind === "multi") {
      const frame = document.createElement("iframe");
      frame.title = "Second-origin operations helper";
      frame.src = "http://127.0.0.1:45912/frame/";
      $("#embedded").replaceChildren(frame);
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            window.removeEventListener("message", handler);
            reject(Error("Frame response timed out"));
          }, 5000),
          id = crypto.randomUUID();
        function handler(e) {
          if (
            e.origin !== "http://127.0.0.1:45912" ||
            e.source !== frame.contentWindow ||
            e.data.id !== id
          )
            return;
          clearTimeout(timer);
          window.removeEventListener("message", handler);
          document.body.dataset.frameReady = "true";
          resolve();
        }
        window.addEventListener("message", handler);
        frame.addEventListener(
          "load",
          () => frame.contentWindow.postMessage({ id }, "http://127.0.0.1:45912"),
          { once: true },
        );
      });
    }
    document.body.dataset.ready = "true";
  })().catch((error) => {
    initializing = null;
    throw error;
  });
  return initializing;
}
function render(value) {
  $("#error").textContent = "";
  $("#output").textContent = JSON.stringify(value);
  history.push(value);
  $("#details").textContent = "Completed operations: " + history.length;
  return value;
}
function failure(error) {
  $("#error").textContent = error.message;
  $("#output").textContent = "Operation could not be completed";
  return { error: error.message };
}
function run(callback) {
  return async (event) => {
    event?.preventDefault();
    try {
      render(await callback());
    } catch (error) {
      failure(error);
    }
  };
}
$("#login").addEventListener(
  "submit",
  run(async () => {
    const form = new FormData($("#login"));
    return { account: await login(form.get("account"), form.get("password")) };
  }),
);
$("#score-form").addEventListener(
  "submit",
  run(() =>
    calculate(
      "score",
      $("#inputs")
        .value.split(",")
        .map((v) => Number(v.trim())),
    ),
  ),
);
$("#route-form").addEventListener(
  "submit",
  run(() =>
    calculate("route", {
      start: Number($("#start").value),
      end: Number($("#end").value),
      congestion: Number($("#congestion").value),
    }),
  ),
);
for (const button of document.querySelectorAll("[data-view]"))
  button.addEventListener("click", () => {
    for (const name of ["score", "route", "stock"])
      $("#" + name + "-view").hidden = name !== button.dataset.view;
    history.push({ view: button.dataset.view });
  });
$("#reserve-form").addEventListener(
  "submit",
  run(async () => {
    const state = await request("/api/state");
    version = state.version;
    const value = await calculate("reserve", {
      product: $("#product").value,
      quantity: Number($("#quantity").value),
      expectedVersion: version,
    });
    reservation = value.result.reservation.id;
    version = value.result.version;
    return value;
  }),
);
for (const action of ["commit", "cancel"])
  $("#" + action).addEventListener(
    "click",
    run(async () => {
      if (!reservation) throw Error("Reserve stock first");
      return calculate(action, { id: reservation });
    }),
  );
$("#recover").addEventListener(
  "click",
  run(async () => {
    worker?.terminate();
    worker = null;
    initializing = null;
    await initialize();
    return { ready: true };
  }),
);
window.research = {
  login,
  calculate,
  prepare,
  execute,
  request,
  rotate: enroll,
  initialize,
  wasm: () => wasm,
  canonical,
  mode: protectedMode ? "guarded" : "baseline",
};
initialize().catch(failure);
