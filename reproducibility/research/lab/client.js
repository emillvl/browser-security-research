/* All tests run through the visible page controls. Results include raw observations. */
const resultNode = document.querySelector("#result"),
  statusNode = document.querySelector("#status");
const enc = new TextEncoder(),
  dec = new TextDecoder();
const from64 = (s) =>
  Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const to64 = (b) =>
  btoa(String.fromCharCode(...new Uint8Array(b)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const json = async (url, body) => {
  const r = await fetch(
    url,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  return { status: r.status, body: await r.json() };
};
const environment = () => ({
  userAgent: navigator.userAgent,
  language: navigator.language,
  hardwareConcurrency: navigator.hardwareConcurrency,
  secureContext: isSecureContext,
  time: new Date().toISOString(),
  timeOrigin: performance.timeOrigin,
  viewport: { width: innerWidth, height: innerHeight },
  browserCpu: "not measured",
  browserMemory: performance.memory
    ? {
        used: performance.memory.usedJSHeapSize,
        total: performance.memory.totalJSHeapSize,
        limit: performance.memory.jsHeapSizeLimit,
        nonstandard: true,
      }
    : "unavailable",
});
const reference = (x) => (7 * x + 13) % 1009;
const load = (src) =>
  new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.append(s);
  });
async function run() {
  document.querySelector("#run").disabled = true;
  statusNode.textContent = "Running actual browser experiments";
  const output = { kind: "experiments", environment: environment(), tests: [] };
  const add = (id, question, observed) => {
    output.tests.push({ id, question, observed });
    resultNode.textContent = JSON.stringify(output, null, 2);
  };
  try {
    const plain = await (await fetch("/plain.js")).text();
    await load("/plain.js");
    add("E01", "Can delivered source and behavior be recovered?", {
      sourceBytes: enc.encode(plain).length,
      source: plain,
      sourceHash: to64(await crypto.subtle.digest("SHA-256", enc.encode(plain))),
      matches: Array.from({ length: 100 }, (_, x) => quote(x) === reference(x)).filter(Boolean)
        .length,
      total: 100,
    });
    const vmText = await (await fetch("/vm.js")).text();
    await load("/vm.js");
    const bytecode = JSON.parse(vmText.match(/const b=(\[[^\]]+\])/)[1]);
    add("E02", "Does a stack interpreter conceal its constants or behavior?", {
      sourceBytes: enc.encode(vmText).length,
      recoveredBytecode: bytecode,
      exactFormulaStringPresent: vmText.includes("7*x+13"),
      outputsMatch: Array.from({ length: 100 }, (_, x) => quoteVM(x) === reference(x)).filter(
        Boolean,
      ).length,
      total: 100,
      analysisMethod: "Read bytecode array and interpreter dispatch cases",
    });
    const ecdh = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, [
      "deriveKey",
    ]);
    const capsule = (
      await json("/api/capsule", {
        publicKey: await crypto.subtle.exportKey("jwk", ecdh.publicKey),
      })
    ).body;
    const serverPub = await crypto.subtle.importKey(
      "jwk",
      capsule.publicKey,
      { name: "ECDH", namedCurve: "P-256" },
      false,
      [],
    );
    const hkdf = await crypto.subtle.deriveKey(
      { name: "ECDH", public: serverPub },
      ecdh.privateKey,
      { name: "HKDF" },
      false,
      ["deriveKey"],
    );
    const key = await crypto.subtle.deriveKey(
      {
        name: "HKDF",
        hash: "SHA-256",
        salt: from64(capsule.salt),
        info: enc.encode("website-protection-study-v1"),
      },
      hkdf,
      { name: "AES-GCM", length: 256 },
      false,
      ["decrypt"],
    );
    let exported;
    try {
      await crypto.subtle.exportKey("raw", key);
      exported = "unexpected success";
    } catch (e) {
      exported = e.name;
    }
    const subtlePrototype = Object.getPrototypeOf(crypto.subtle),
      original = subtlePrototype.decrypt;
    let intercepted = "";
    let clear;
    try {
      subtlePrototype.decrypt = async function (...args) {
        const value = await original.apply(this, args);
        intercepted = dec.decode(value);
        return value;
      };
      clear = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: from64(capsule.iv) },
        key,
        from64(capsule.ciphertext),
      );
    } finally {
      subtlePrototype.decrypt = original;
    }
    Function(dec.decode(clear))();
    const damaged = from64(capsule.ciphertext);
    damaged[0] ^= 1;
    let tampered;
    try {
      await crypto.subtle.decrypt({ name: "AES-GCM", iv: from64(capsule.iv) }, key, damaged);
      tampered = "unexpected success";
    } catch (e) {
      tampered = e.name;
    }
    add(
      "E03",
      "Does ECDH delivery plus a nonextractable AES key hide the executed source from browser instrumentation?",
      {
        scheme: "ECDH P-256 HKDF SHA-256 AES-256-GCM",
        ciphertextBytes: from64(capsule.ciphertext).length,
        plaintextBytes: clear.byteLength,
        aesKeyExtractable: key.extractable,
        privateKeyExtractable: ecdh.privateKey.extractable,
        exportAttempt: exported,
        hookCapturedPlaintext: intercepted,
        executedResult: protectedQuote(5),
        tamperResult: tampered,
        rawKeyDelivered: false,
        sharedSecretExposedToJavaScript: false,
        attacker: "A3 controlled prototype hook installed before decryption",
      },
    );
    const originalLog = console.log;
    console.log = () => {};
    console.log("Suppressed research marker");
    console.log = originalLog;
    let contextPrevented = false;
    const stopContext = (e) => {
      e.preventDefault();
      contextPrevented = e.defaultPrevented;
    };
    document.addEventListener("contextmenu", stopContext);
    document.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true }));
    document.removeEventListener("contextmenu", stopContext);
    const stillReadable = await (await fetch("/plain.js")).text();
    add("E04", "Do console and context menu suppression stop source retrieval?", {
      logWasReplaced: true,
      contextMenuDefaultPrevented: contextPrevented,
      bytesRecovered: enc.encode(stillReadable).length,
      sourceEqual: stillReadable === plain,
      method: "Ordinary same-origin fetch by the browser owner; no context menu required",
    });
    let cross;
    try {
      cross = {
        unexpectedRead: await (await fetch("http://127.0.0.1:4382/untrusted.json")).text(),
      };
    } catch (e) {
      cross = { error: e.name };
    }
    await load("http://127.0.0.1:4382/cross.js");
    const sriBytes = await (await fetch("/sri-bad.js")).text();
    add("E05", "Which boundaries do CORS and integrity enforce?", {
      crossOriginFetch: cross,
      crossOriginClassicScriptExecuted: globalThis.crossOriginExecutable === true,
      integrityRejectedBytesStillFetchable: sriBytes.length,
      meaning:
        "Remote-origin response reading differs from resource execution and from browser-owner access",
    });
    const wasmBytes = await (await fetch("/quote.wasm")).arrayBuffer();
    const wasm = await WebAssembly.instantiate(wasmBytes);
    const imports = WebAssembly.Module.imports(wasm.module),
      exports = WebAssembly.Module.exports(wasm.module);
    add("E06", "Does WebAssembly prevent recovery or use of the delivered module?", {
      bytesRecovered: wasmBytes.byteLength,
      sha256: to64(await crypto.subtle.digest("SHA-256", wasmBytes)),
      imports,
      exports,
      matches: Array.from(
        { length: 100 },
        (_, x) => wasm.instance.exports.quote(x) === reference(x),
      ).filter(Boolean).length,
      total: 100,
      first64Bytes: to64(wasmBytes),
    });
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, [
      "sign",
      "verify",
    ]);
    const enrolled = await json("/api/session", {
      publicKey: await crypto.subtle.exportKey("jwk", pair.publicKey),
    });
    const challenge = (await json("/api/challenge")).body;
    const sign = async (ch, x) => ({
      nonce: ch.nonce,
      x,
      signature: to64(
        await crypto.subtle.sign(
          { name: "ECDSA", hash: "SHA-256" },
          pair.privateKey,
          enc.encode(`${ch.session}|POST|/api/signed|${ch.nonce}|${x}`),
        ),
      ),
    });
    const signed = await sign(challenge, 5),
      valid = await json("/api/signed", signed),
      replay = await json("/api/signed", signed);
    const changed = (await json("/api/challenge")).body,
      signed2 = await sign(changed, 8);
    signed2.x = 9;
    const altered = await json("/api/signed", signed2);
    const owner = (await json("/api/challenge")).body,
      ownerResult = await json("/api/signed", await sign(owner, 9));
    const stale = (await json("/api/challenge")).body;
    await new Promise((r) => setTimeout(r, 2100));
    const expired = await json("/api/signed", await sign(stale, 5));
    add(
      "E07",
      "Can signed execution leases reject copied requests while permitting the browser owner?",
      {
        keyExtractable: pair.privateKey.extractable,
        sessionIssuedFor: "Authorized demo session, no production identity system",
        valid: valid.status,
        replay: replay.status,
        alteredInput: altered.status,
        ownerCanInvokeSigning: ownerResult.status,
        expired: expired.status,
        leaseMs: 2000,
        protocol:
          "Session method path nonce input bound by P-256 signature. No claim of browser attestation.",
      },
    );
    await json("/api/session", {});
    const q0 = (await json("/api/oracle?x=0")).body.value,
      q1 = (await json("/api/oracle?x=1")).body.value;
    const slope = (q1 - q0 + 1009) % 1009,
      offset = q0;
    const predicted = Array.from({ length: 98 }, (_, i) => {
      const x = i + 2;
      return (slope * x + offset) % 1009 === reference(x);
    }).filter(Boolean).length;
    let statuses = [];
    for (let i = 2; i < 11; i++) statuses.push((await json("/api/oracle?x=" + i)).status);
    await json("/api/session", {});
    const reset = await json("/api/oracle?x=50");
    await json("/api/session", {});
    const keyedSamples = [];
    for (let x = 0; x < 4; x++)
      keyedSamples.push({ x, ...(await json("/api/oracle?kind=keyed&x=" + x)).body });
    add("E08", "Can server behavior be reconstructed without server source?", {
      linearModelKnownFamily: true,
      queriesUsedToFit: 2,
      recoveredSlope: slope,
      recoveredOffset: offset,
      heldoutDomainMatches: predicted,
      heldoutTotal: 98,
      requestStatusesAfterFit: statuses,
      newDemoSessionResetsBudget: reset.status,
      keyedObservations: keyedSamples,
      keyedGeneralization:
        "Not established; four samples do not prove resistance. HMAC key never delivered.",
    });
    const frame = document.createElement("iframe");
    frame.title = "Isolated frame test";
    frame.src = "http://127.0.0.1:4382/broker-frame/";
    document.body.append(frame);
    await new Promise((r) => (frame.onload = r));
    let frameRead;
    try {
      frameRead = { text: frame.contentWindow.document.body.innerText };
    } catch (e) {
      frameRead = { error: e.name };
    }
    const rpc = await new Promise((resolve, reject) => {
      const id = "research-" + Date.now(),
        timer = setTimeout(() => reject(Error("RPC timeout")), 3000);
      const listener = (e) => {
        if (e.origin === "http://127.0.0.1:4382" && e.data.id === id) {
          clearTimeout(timer);
          removeEventListener("message", listener);
          resolve(e.data);
        }
      };
      addEventListener("message", listener);
      frame.contentWindow.postMessage({ op: "quote", id, x: 5 }, "http://127.0.0.1:4382");
    });
    add("E09", "Does origin compartmentalization hide implementation from the parent page?", {
      parentDOMRead: frameRead,
      permittedRPC: rpc,
      frameSourceURL: frame.src,
      protectionAgainst: "A5 parent origin",
      limitation:
        "Frame source is still delivered to the browser. No browser or OS ownership protection.",
    });
    frame.remove();
    const marker = "/* recipient=research-demo-001 */\n",
      marked = marker + plain,
      stripped = marked.replace(/\/\*[^]*?\*\//g, "");
    const clone = Function(stripped + ";return quote;")();
    add("E10", "Does a comment watermark prevent a functional clone?", {
      markerPresentBefore: marked.includes("research-demo-001"),
      markerPresentAfter: stripped.includes("research-demo-001"),
      matches: Array.from({ length: 100 }, (_, x) => clone(x) === reference(x)).filter(Boolean)
        .length,
      total: 100,
      interpretation: "This removable comment is an attribution aid, not a copying boundary.",
    });
    const robots = await (await fetch("/robots/")).text();
    add("E11", "Does a robots exclusion make resources inaccessible?", {
      normalBrowserStatus: 200,
      htmlBytes: enc.encode(robots).length,
      copyableTextPresent: robots.includes("This text and script remain available"),
      robotsRule: "Disallow: /robots/",
      separateCrawlerRunRequired: true,
    });
    const integrityFrame = document.createElement("iframe");
    integrityFrame.title = "Integrity test";
    integrityFrame.src = "/csp/";
    document.body.append(integrityFrame);
    await new Promise((r) => (integrityFrame.onload = r));
    await new Promise((r) => setTimeout(r, 350));
    add("E12", "Does browser CSP and SRI enforcement protect confidentiality?", {
      enforcement: JSON.parse(
        integrityFrame.contentDocument.querySelector("#csp-result").textContent,
      ),
      recoveredTamperedScript: sriBytes,
      scope: "These are execution integrity controls; the read used ordinary same-origin fetch.",
    });
    integrityFrame.remove();
    const pixelFrame = document.createElement("iframe");
    pixelFrame.title = "Pixel copying test";
    pixelFrame.src = "/rendered/";
    document.body.append(pixelFrame);
    await new Promise((r) => (pixelFrame.onload = r));
    const pixelDoc = pixelFrame.contentDocument,
      before = pixelDoc.querySelector("#fallback").textContent,
      pixels = pixelDoc.querySelector("canvas").toDataURL("image/png");
    pixelDoc.querySelector("#accessible").click();
    add("E13", "What does a canvas-only representation change?", {
      semanticTextBefore: before,
      pixelCaptureDataURL: pixels,
      pixelCaptureCharacters: pixels.length,
      accessibleTextAfter: pixelDoc.querySelector("#fallback").textContent,
      meaning: "Pixels are copyable. Accessible text restores a semantic representation.",
    });
    pixelFrame.remove();
    const noStore = await fetch("/plain.js");
    const savedBody = await noStore.text();
    add("E14", "Does no-store stop deliberate response copying?", {
      cacheControl: noStore.headers.get("cache-control"),
      responseStatus: noStore.status,
      savedBytes: enc.encode(savedBody).length,
      scope:
        "No claim about persistence or eviction behavior; only direct response access was tested.",
    });
    await json("/api/session", { publicKey: await crypto.subtle.exportKey("jwk", pair.publicKey) });
    const concurrent = (await json("/api/challenge")).body,
      parallelSigned = await sign(concurrent, 11);
    const parallel = await Promise.all(
      Array.from({ length: 20 }, () => json("/api/signed", parallelSigned)),
    );
    const challengeA = (await json("/api/challenge")).body,
      challengeB = (await json("/api/challenge")).body;
    const resultA = await json("/api/signed", await sign(challengeA, 12)),
      resultB = await json("/api/signed", await sign(challengeB, 13));
    add("E16", "Are leases safe under replay races and overlapping widgets?", {
      parallelStatuses: parallel.map((r) => r.status),
      overlappingChallengeA: resultA.status,
      overlappingChallengeB: resultB.status,
      meaning:
        "Both independently issued live challenges should work once; a shared latest-challenge slot may invalidate the first.",
    });
    const inputs = [0, 1, 7, 15, 31, 47, 63, 95],
      observations = {};
    for (const kind of ["raw", "banded"]) {
      await json("/api/session", {});
      observations[kind] = [];
      for (const x of inputs)
        observations[kind].push({
          x,
          value: (await json("/api/oracle?kind=" + kind + "&x=" + x)).body.value,
        });
    }
    const candidates = {};
    for (const kind of ["raw", "banded"]) {
      candidates[kind] = [];
      for (let a = 0; a < 32; a++)
        for (let b = 0; b < 32; b++) {
          if (
            observations[kind].every(({ x, value }) => {
              const y = (a * x + b) % 1009;
              return (
                value ===
                (kind === "raw" ? y : ["low", "medium", "high"][Math.min(2, Math.floor(y / 337))])
              );
            })
          )
            candidates[kind].push([a, b]);
        }
    }
    let adaptiveCandidates = candidates.banded.slice(),
      adaptive = [];
    await json("/api/session", {});
    const band = (a, b, x) =>
      ["low", "medium", "high"][Math.min(2, Math.floor(((a * x + b) % 1009) / 337))];
    for (let i = 0; i < 8; i++) {
      let chosen = -1,
        best = adaptiveCandidates.length;
      for (let x = 0; x < 100; x++) {
        const counts = {};
        for (const [a, b] of adaptiveCandidates) {
          const v = band(a, b, x);
          counts[v] = (counts[v] || 0) + 1;
        }
        const worst = Math.max(...Object.values(counts));
        if (worst < best) {
          best = worst;
          chosen = x;
        }
      }
      if (chosen < 0) break;
      const value = (await json("/api/oracle?kind=banded&x=" + chosen)).body.value;
      adaptiveCandidates = adaptiveCandidates.filter(([a, b]) => band(a, b, chosen) === value);
      adaptive.push({ x: chosen, value, remainingCandidates: adaptiveCandidates.length });
    }
    const behaviorMatches = adaptiveCandidates.length
      ? Array.from(
          { length: 100 },
          (_, x) => band(...adaptiveCandidates[0], x) === band(7, 13, x),
        ).filter(Boolean).length
      : 0;
    add("E17", "How does returning only required categories change finite model reconstruction?", {
      inputs,
      queriesPerVariant: 8,
      priorFamily: "(a*x+b) modulo 1009 for integers a,b from 0 through 31; 1024 candidates",
      observations,
      rawCandidateCount: candidates.raw.length,
      bandedCandidateCount: candidates.banded.length,
      bandedCandidates: candidates.banded,
      adaptiveQueries: adaptive,
      adaptiveRemainingCandidates: adaptiveCandidates.length,
      cloneCategoryMatches: behaviorMatches,
      cloneCategoryTotal: 100,
      scope:
        "Fixed prior. Adaptive stage uses a fresh demo session with up to eight further queries. Exact parameter ambiguity does not imply resistance to category cloning.",
    });
    add("E18", "Can a server proxy reproduce the CORS-restricted service?", {
      response: await json("/api/proxy?x=17"),
      expected: 132,
      method:
        "An isolated local proxy sends the allowed Origin header as an ordinary native HTTP client. No production system is modified.",
    });
    const cfg = (await json("/api/paillier/config")).body,
      n = BigInt(cfg.n),
      n2 = n * n,
      ca = BigInt(cfg.ca),
      cb = BigInt(cfg.cb);
    const pow = (base, exponent, mod) => {
      let r = 1n;
      for (; exponent > 0n; exponent >>= 1n, base = (base * base) % mod)
        if (exponent & 1n) r = (r * base) % mod;
      return r;
    };
    const evaluate = (x) => ({ x, ciphertext: ((pow(ca, BigInt(x), n2) * cb) % n2).toString() });
    const normal = await json("/api/paillier/open", evaluate(5)),
      recoveredA = await json("/api/paillier/open", { ciphertext: cfg.ca }),
      recoveredB = await json("/api/paillier/open", { ciphertext: cfg.cb });
    const boundNormal = await json("/api/paillier/bound", evaluate(5)),
      boundAttack = await json("/api/paillier/bound", { x: 5, ciphertext: cfg.ca });
    const y0 = (await json("/api/paillier/bound", evaluate(0))).body.value,
      y1 = (await json("/api/paillier/bound", evaluate(1))).body.value;
    const samples = [];
    for (let i = -3; i < 15; i++) {
      const t = performance.now();
      await json("/api/paillier/bound", evaluate(5));
      if (i >= 0) samples.push(performance.now() - t);
    }
    add("E20", "Can homomorphic evaluation hide affine code and still safely disclose results?", {
      scheme: cfg.scheme,
      keyBits: cfg.keyBits,
      normal,
      chosenCiphertextCoefficientA: recoveredA,
      chosenCiphertextCoefficientB: recoveredB,
      boundNormal,
      boundAttack,
      boundTwoQueries: { y0, y1, inferredA: y1 - y0, inferredB: y0 },
      roundTripSamplesMs: samples,
      configJSONBytes: enc.encode(JSON.stringify(cfg)).length,
      limitations:
        "An intentionally unrestricted decryption interface is compared with expression binding. This is not a general script protection system or a production Paillier library.",
    });
    output.completed = new Date().toISOString();
    const saved = await json("/api/save", output);
    output.saved = saved.body.saved;
    resultNode.textContent = JSON.stringify(output, null, 2);
    statusNode.textContent = "Complete. Evidence saved as " + output.saved;
  } catch (e) {
    output.error = { name: e.name, message: e.message, stack: e.stack };
    await json("/api/save", output);
    resultNode.textContent = JSON.stringify(output, null, 2);
    statusNode.textContent = "Interrupted by " + e.message;
  }
  document.querySelector("#run").disabled = false;
}
async function benchmark() {
  document.querySelector("#bench").disabled = true;
  statusNode.textContent = "Measuring real browser elapsed time";
  const output = {
    kind: "benchmark",
    environment: environment(),
    warmup: 10,
    batches: 30,
    clock: "performance.now milliseconds",
    samples: { plain: [], vm: [], wasm: [], remote: [], aes64KiB: [], aes256KiB: [] },
    workload: {
      computeCallsPerBatch: 1000000,
      remoteRequestsPerBatch: 1,
      cryptoDecryptionsPerBatch: 50,
    },
    notes: [
      "Interleaved alternating compute order",
      "Loopback timing, not Internet latency",
      "No browser CPU measurement",
      "Concurrent tooling and renderer work may affect scheduling",
    ],
  };
  try {
    const metricWindow = (await json("/api/metrics/start", {})).body;
    if (!globalThis.quote) await load("/plain.js");
    if (!globalThis.quoteVM) await load("/vm.js");
    const wasm = (await WebAssembly.instantiate(await (await fetch("/quote.wasm")).arrayBuffer()))
      .instance.exports.quote;
    const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, [
      "encrypt",
      "decrypt",
    ]);
    const blobs = {};
    for (const n of [65536, 262144]) {
      const iv = crypto.getRandomValues(new Uint8Array(12));
      blobs[n] = {
        iv,
        ciphertext: await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new Uint8Array(n)),
      };
    }
    let sink = 0;
    const functions = { plain: quote, vm: quoteVM, wasm };
    for (let i = -10; i < 30; i++) {
      const order = i % 2 === 0 ? ["plain", "vm", "wasm"] : ["wasm", "vm", "plain"];
      for (const name of order) {
        const t = performance.now();
        for (let j = 0; j < 1000000; j++) sink += functions[name](j % 100);
        const elapsed = performance.now() - t;
        if (i >= 0) output.samples[name].push(elapsed);
      }
      for (const [n, label] of [
        [65536, "aes64KiB"],
        [262144, "aes256KiB"],
      ]) {
        const t = performance.now();
        for (let k = 0; k < 50; k++)
          await crypto.subtle.decrypt(
            { name: "AES-GCM", iv: blobs[n].iv },
            key,
            blobs[n].ciphertext,
          );
        if (i >= 0) output.samples[label].push(performance.now() - t);
      }
      const t = performance.now();
      await (await fetch("/api/bench?x=5")).json();
      if (i >= 0) output.samples.remote.push(performance.now() - t);
    }
    output.sink = sink;
    output.serverMetrics = (await json("/api/metrics/stop", { id: metricWindow.id })).body;
    output.environmentAfter = environment();
    output.measuredResourceBytes = {
      plain: enc.encode(await (await fetch("/plain.js")).text()).length,
      vm: enc.encode(await (await fetch("/vm.js")).text()).length,
      wasm: (await (await fetch("/quote.wasm")).arrayBuffer()).byteLength,
    };
    output.completed = new Date().toISOString();
    const saved = await json("/api/save", output);
    output.saved = saved.body.saved;
    resultNode.textContent = JSON.stringify(output, null, 2);
    statusNode.textContent = "Measurements complete. Evidence saved as " + output.saved;
  } catch (e) {
    output.error = e.message;
    await json("/api/save", output);
    resultNode.textContent = JSON.stringify(output, null, 2);
    statusNode.textContent = "Measurement failure " + e.message;
  }
  document.querySelector("#bench").disabled = false;
}
document.querySelector("#run").onclick = run;
document.querySelector("#bench").onclick = benchmark;
const auto = new URLSearchParams(location.search).get("autorun");
if (auto === "experiments") run();
if (auto === "bench") benchmark();
