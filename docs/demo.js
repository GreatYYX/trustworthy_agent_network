(() => {
  const data = window.GUARDRAIL_DEMO_DATA;
  const grid = document.getElementById("case-grid");
  const errorEl = document.getElementById("demo-error");
  const copyLinkBtn = document.getElementById("copy-link-btn");
  const toggleStreamBtn = document.getElementById("toggle-stream-btn");
  const replayAllBtn = document.getElementById("replay-all-btn");
  const streams = [];
  let runId = 0;
  let paused = false;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function showError(message) {
    if (!errorEl) return;
    errorEl.hidden = false;
    errorEl.textContent = message;
  }

  if (!data || !Array.isArray(data.demos) || !data.demos.length || !grid) {
    showError("Demo data failed to load. Hard-refresh with Cmd+Shift+R.");
    return;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function boltedAttackLabel(value) {
    if (value === "exploited") return "Attack succeeds";
    if (value === "partial") return "Partial bypass";
    return "Attack blocked";
  }

  function streamShell(streamId) {
    return `
      <div class="stream-shell">
        <div class="stream-toolbar">
          <span class="stream-label"><i aria-hidden="true"></i> Dialogue stream</span>
          <span class="stream-status" data-stream-status="${escapeHtml(streamId)}">Queued</span>
        </div>
        <div class="stream-body" data-stream-body="${escapeHtml(streamId)}" aria-live="polite"></div>
      </div>`;
  }

  function boltedCard(demo, modelId) {
    const model = data.models[modelId];
    const cases = demo.cases?.[modelId] || [];
    const attackIndex = demo.boltedAttackIndex || 0;
    const attack = cases[attackIndex];
    if (!attack || !model) return "";

    const streamId = `${demo.id}-${modelId}`;
    streams.push({ id: streamId, sectionId: demo.id, item: attack });

    return `
      <article class="comparison-card bolted-card" data-stream-card="${escapeHtml(streamId)}" data-outcome="${escapeHtml(attack.outcome)}">
        <div class="card-topline">
          <p class="architecture">Bolted-on · ${escapeHtml(model.label)}</p>
          <span class="outcome ${escapeHtml(attack.outcome)}">${boltedAttackLabel(attack.outcome)}</span>
        </div>
        <h3>${escapeHtml(attack.title)}</h3>
        <p class="card-summary">${escapeHtml(attack.summary)}</p>
        ${streamShell(streamId)}
      </article>`;
  }

  function bakedCard(demo) {
    const attack = demo.bakedIn?.[0];
    const valid = demo.bakedIn?.[1];
    if (!attack || !valid) return "";

    const streamId = `${demo.id}-tan`;
    streams.push({ id: streamId, sectionId: demo.id, item: attack });

    return `
      <article class="comparison-card baked-card" data-stream-card="${escapeHtml(streamId)}" data-outcome="${escapeHtml(attack.outcome)}">
        <div class="card-topline">
          <p class="architecture">TAN baked-in · model-independent</p>
          <span class="outcome ${escapeHtml(attack.outcome)}">Defense succeeds</span>
        </div>
        <h3>${escapeHtml(attack.title)}</h3>
        <p class="card-summary">${escapeHtml(attack.summary)}</p>
        ${streamShell(streamId)}
        <div class="valid-path is-pending" data-completion-for="${escapeHtml(streamId)}">
          <div>
            <span class="valid-path-label">Valid action remains reachable</span>
            <strong>${escapeHtml(valid.title)}</strong>
          </div>
        </div>
      </article>`;
  }

  grid.innerHTML = data.demos
    .map((demo, index) => `
      <section class="scenario-section" id="${escapeHtml(demo.id)}">
        <header class="scenario-head">
          <span class="scenario-index">${String(index + 1).padStart(2, "0")}</span>
          <div>
            <h2>${escapeHtml(demo.title)}</h2>
            <p>${escapeHtml(demo.subtitle)}</p>
          </div>
        </header>
        <div class="comparison-grid">
          ${boltedCard(demo, "sol")}
          ${boltedCard(demo, "opus")}
          ${bakedCard(demo)}
        </div>
      </section>`)
    .join("");

  function speakerName(value) {
    return String(value || "Agent").split("·")[0].trim();
  }

  function speakerCode(value) {
    const name = String(value || "");
    if (name.includes("Guardrail")) return "Rail";
    if (name.includes("TAN")) return "TAN";
    if (name.includes("System")) return "Sys";
    if (name.includes("Finance")) return "Fin";
    if (name.includes("Navigation")) return "Nav";
    if (name.includes("Medical")) return "Med";
    if (name.includes("Cross")) return "Join";
    if (name.includes("Coder")) return "Code";
    if (name.includes("Tester")) return "Test";
    if (name.includes("Provenance")) return "Prov";
    return name.replace(/\s+Agent.*/, "").slice(0, 4) || "A";
  }

  function messageRole(turn) {
    const speaker = String(turn.speaker || "").toLowerCase();
    if (speaker.includes("guardrail")) return "guard";
    if (speaker.includes("tan")) return "tan";
    if (speaker.includes("system")) return "system";
    if (turn.kind === "model") return "model";
    return "agent";
  }

  function makeMessage(turn) {
    const role = messageRole(turn);
    const message = document.createElement("article");
    message.className = `stream-message role-${role}`;
    message.innerHTML = `
      <span class="stream-avatar" aria-hidden="true">${escapeHtml(speakerCode(turn.speaker))}</span>
      <div class="stream-copy">
        <div class="stream-meta">
          <strong>${escapeHtml(speakerName(turn.speaker))}</strong>
          <span>${escapeHtml(turn.kind || "message")}</span>
        </div>
        <p class="stream-text"></p>
      </div>`;
    return message;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function waitWhilePaused(currentRun) {
    while (paused && currentRun === runId) await sleep(70);
  }

  async function streamText(element, value, currentRun) {
    const text = String(value || "");
    const chunkSize = text.length > 180 ? 7 : text.length > 90 ? 5 : 3;
    for (let index = 0; index < text.length; index += chunkSize) {
      if (currentRun !== runId) return false;
      await waitWhilePaused(currentRun);
      element.textContent = text.slice(0, index + chunkSize);
      element.closest(".stream-body").scrollTop = element.closest(".stream-body").scrollHeight;
      await sleep(12);
    }
    return currentRun === runId;
  }

  async function playStream(stream, currentRun, instant = false) {
    const body = document.querySelector(`[data-stream-body="${stream.id}"]`);
    const status = document.querySelector(`[data-stream-status="${stream.id}"]`);
    const completion = document.querySelector(`[data-completion-for="${stream.id}"]`);
    const card = document.querySelector(`[data-stream-card="${stream.id}"]`);
    if (!body || !status || !card) return;

    body.innerHTML = "";
    completion?.classList.add("is-pending");
    card.classList.remove("is-complete");
    card.classList.add("is-streaming");
    status.textContent = instant ? "Recorded" : "Streaming";

    for (const turn of stream.item.turns || []) {
      if (currentRun !== runId) return;
      await waitWhilePaused(currentRun);
      const message = makeMessage(turn);
      body.appendChild(message);
      const textElement = message.querySelector(".stream-text");
      if (instant) textElement.textContent = turn.text || "";
      else if (!(await streamText(textElement, turn.text, currentRun))) return;
      message.classList.add("is-complete");
      body.scrollTop = body.scrollHeight;
      if (!instant) await sleep(110);
    }

    if (currentRun !== runId) return;
    status.textContent = "Complete";
    card.classList.remove("is-streaming");
    card.classList.add("is-complete");
    completion?.classList.remove("is-pending");
  }

  async function playAll(instant = false) {
    const currentRun = ++runId;
    paused = false;
    if (toggleStreamBtn) toggleStreamBtn.textContent = "Pause";

    for (const stream of streams) {
      const body = document.querySelector(`[data-stream-body="${stream.id}"]`);
      const status = document.querySelector(`[data-stream-status="${stream.id}"]`);
      const completion = document.querySelector(`[data-completion-for="${stream.id}"]`);
      const card = document.querySelector(`[data-stream-card="${stream.id}"]`);
      if (body) body.innerHTML = "";
      if (status) status.textContent = "Queued";
      completion?.classList.add("is-pending");
      if (card) card.classList.remove("is-streaming", "is-complete");
    }

    for (const demo of data.demos) {
      if (currentRun !== runId) return;
      const sectionStreams = streams.filter((stream) => stream.sectionId === demo.id);
      await Promise.all(sectionStreams.map((stream) => playStream(stream, currentRun, instant)));
      if (!instant) await sleep(220);
    }
  }

  if (toggleStreamBtn) {
    toggleStreamBtn.addEventListener("click", () => {
      paused = !paused;
      toggleStreamBtn.textContent = paused ? "Continue" : "Pause";
    });
  }

  if (replayAllBtn) {
    replayAllBtn.addEventListener("click", () => playAll(Boolean(reducedMotion)));
  }

  if (copyLinkBtn) {
    copyLinkBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(window.location.href.split("#")[0]);
        copyLinkBtn.textContent = "Copied";
        window.setTimeout(() => { copyLinkBtn.textContent = "Copy link"; }, 1400);
      } catch (_error) {
        window.prompt("Copy this link:", window.location.href.split("#")[0]);
      }
    });
  }

  const requestedId = (window.location.hash || "").slice(1).split("/")[0];
  if (requestedId && data.demos.some((demo) => demo.id === requestedId)) {
    document.getElementById(requestedId)?.scrollIntoView();
  }

  if (new URLSearchParams(window.location.search).has("embed")) {
    document.body.classList.add("is-embed");
  }

  window.setTimeout(() => playAll(Boolean(reducedMotion)), 240);
})();
