(async () => {
  const report = {},
    input = [100, 200, 300, 400, 500, 600],
    newPayload = (op = "score", value = input) => ({
      op,
      input: value,
      requestId: crypto.randomUUID(),
    });
  const raw = async (path, data, headers = {}, credentials = "same-origin") => {
    const response = await fetch(path, {
      method: "POST",
      credentials,
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(data),
    });
    return { status: response.status, body: await response.json() };
  };
  let identity = await research.request("/api/login", {
    account: "alice",
    password: "Research-Alice-Only",
  });
  // Re-enroll the client key after the independent login probe.
  await research.login("alice", "Research-Alice-Only");
  report.normal = await research.calculate("score", input);
  report.invalidLogin = await raw("/api/login", {
    account: "alice",
    password: "wrong-research-password",
  });
  report.noSession = await raw("/api/execute", {}, {}, "omit");
  report.noCsrf = await raw("/api/key", {});
  report.publicProgram = { status: (await fetch("/public-workload.mjs")).status };
  report.anonymous = await raw("/api/anonymous", { op: "score", input });
  const prepared = await research.prepare(newPayload());
  report.forgedPayload = await research
    .request("/api/execute", {
      ...prepared,
      payload: { ...prepared.payload, input: [1, 2, 3, 4, 5, 6] },
    })
    .then(
      (v) => ({ unexpected: v }),
      (e) => ({ status: e.status, error: e.message }),
    );
  // Sign and bind each legitimate submission.
  report.duplicateRace = await Promise.all(
    Array.from({ length: 20 }, () =>
      research.request("/api/execute", prepared).then(
        (v) => ({ status: 200, result: v.result }),
        (e) => ({ status: e.status, error: e.message }),
      ),
    ),
  );
  const expired = await research.prepare(newPayload());
  await new Promise((resolve) => setTimeout(resolve, 1650));
  report.expired = await research.request("/api/execute", expired).then(
    (v) => ({ unexpected: v }),
    (e) => ({ status: e.status, error: e.message }),
  );
  const retired = await research.prepare(newPayload());
  await research.rotate();
  report.retired = await research.request("/api/execute", retired).then(
    (v) => ({ unexpected: v }),
    (e) => ({ status: e.status, error: e.message }),
  );
  report.afterRotation = await research.calculate("score", input);
  const outstanding = await Promise.all(
    Array.from({ length: 20 }, () => research.prepare(newPayload())),
  );
  report.independentConcurrent = await Promise.all(
    outstanding.map((p) =>
      research.request("/api/execute", p).then(
        (v) => ({ status: 200, result: v.result }),
        (e) => ({ status: e.status, error: e.message }),
      ),
    ),
  );
  const state = await research.request("/api/state"),
    reservationPayload = newPayload("reserve", {
      product: "P01",
      quantity: 2,
      expectedVersion: state.version,
    });
  report.reserve = await research.execute(reservationPayload);
  const id = report.reserve.result.reservation.id;
  report.idempotent = await research.execute(reservationPayload);
  report.staleVersion = await research
    .execute(newPayload("reserve", { product: "P02", quantity: 1, expectedVersion: state.version }))
    .then(
      (v) => ({ unexpected: v }),
      (e) => ({ status: e.status, error: e.message }),
    );
  report.reusedIdDifferentPayload = await research
    .execute({ ...reservationPayload, input: { ...reservationPayload.input, quantity: 3 } })
    .then(
      (v) => ({ unexpected: v }),
      (e) => ({ status: e.status, error: e.message }),
    );
  const aliceEnvelope = await research.prepare(newPayload());
  await research.login("bob", "Research-Bob-Only");
  report.foreignSignedEnvelope = await research.request("/api/execute", aliceEnvelope).then(
    (v) => ({ unexpected: v }),
    (e) => ({ status: e.status, error: e.message }),
  );
  report.foreignReservation = await research.calculate("commit", { id }).then(
    (v) => ({ unexpected: v }),
    (e) => ({ status: e.status, error: e.message }),
  );
  report.quota = [];
  for (let i = 0; i < 13; i++)
    report.quota.push(
      await research.calculate("score", input).then(
        (v) => ({ status: 200, remaining: v.remaining }),
        (e) => ({ status: e.status, error: e.message }),
      ),
    );
  await research.login("bob", "Research-Bob-Only");
  report.quotaAfterNewSession = await research.calculate("score", input).then(
    (v) => ({ unexpected: v }),
    (e) => ({ status: e.status, error: e.message }),
  );
  await research.login("alice", "Research-Alice-Only");
  // Use fresh hold transitions because the earlier hold may have expired.
  let fresh = await research.request("/api/state");
  const cancelled = await research.calculate("reserve", {
    product: "P02",
    quantity: 1,
    expectedVersion: fresh.version,
  });
  report.cancelled = await research.calculate("cancel", { id: cancelled.result.reservation.id });
  fresh = await research.request("/api/state");
  const committed = await research.calculate("reserve", {
    product: "P03",
    quantity: 1,
    expectedVersion: fresh.version,
  });
  const commitPayload = newPayload("commit", { id: committed.result.reservation.id });
  report.committed = await research.execute(commitPayload);
  report.commitRetry = await research.execute(commitPayload);
  fresh = await research.request("/api/state");
  const expiring = await research.calculate("reserve", {
    product: "P04",
    quantity: 1,
    expectedVersion: fresh.version,
  });
  await new Promise((resolve) => setTimeout(resolve, 1900));
  const finalState = await research.request("/api/state");
  report.expiredReservation = finalState.reservations.find(
    (r) => r.id === expiring.result.reservation.id,
  );
  report.visibleText = document.body.innerText;
  report.labels = [...document.querySelectorAll("input,select")].map((e) => ({
    name: e.name || e.id,
    labels: e.labels.length,
  }));
  report.resultStatusSemantics = !!document.querySelector('[role="status"][aria-live="polite"]');
  report.browserModel = {
    windowModel: typeof window.model,
    privateKey: typeof window.pair,
    programTextInClient: (await (await fetch("/suite-client.mjs")).text()).includes(
      '"threshold":606',
    ),
  };
  // Capture a positive control to check page instrumentation.
  const original = SubtleCrypto.prototype.decrypt,
    captures = [];
  SubtleCrypto.prototype.decrypt = async function (...args) {
    const value = await original.apply(this, args);
    captures.push(new TextDecoder().decode(value));
    return value;
  };
  await research.calculate("score", input);
  report.programDecryptCaptures = captures.length;
  const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 128 }, false, [
      "encrypt",
      "decrypt",
    ]),
    iv = crypto.getRandomValues(new Uint8Array(12)),
    text = new TextEncoder().encode("independent page hook control");
  await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, text),
  );
  report.decryptPositiveControl = [...captures];
  SubtleCrypto.prototype.decrypt = original;
  // Initiate fresh authorized work through the page interface.
  report.onlineReuse = await research.calculate("route", { start: 4, end: 20, congestion: 7 });
  return report;
})();
