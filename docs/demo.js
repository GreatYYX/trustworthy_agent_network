(() => {
  function showError(message) {
    const el = document.getElementById("demo-error");
    if (!el) return;
    el.hidden = false;
    el.textContent = message;
  }

  const data = window.GUARDRAIL_DEMO_DATA;
  if (!data || !Array.isArray(data.demos) || !data.demos.length) {
    showError("Demo data failed to load. Hard-refresh with Cmd+Shift+R.");
    return;
  }

  const scenarioList = document.getElementById("scenario-list");
  const caseTabs = document.getElementById("case-tabs");
  const caseKicker = document.getElementById("case-kicker");
  const caseTitle = document.getElementById("case-title");
  const caseSummary = document.getElementById("case-summary");
  const outcomeBadge = document.getElementById("outcome-badge");
  const timeline = document.getElementById("timeline");
  const replayBtn = document.getElementById("replay-btn");
  const copyLinkBtn = document.getElementById("copy-link-btn");
  const modelBlurb = document.getElementById("model-blurb");
  const chatStatus = document.getElementById("chat-status");
  const errorEl = document.getElementById("demo-error");

  const state = {
    model: "sol",
    demoId: data.demos[0].id,
    caseIndex: 0,
    token: 0,
  };

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function currentDemo() {
    return data.demos.find((demo) => demo.id === state.demoId) || data.demos[0];
  }

  function currentCases() {
    const demo = currentDemo();
    const modelCases = (demo.cases && demo.cases[state.model]) || [];
    const bakedCases = demo.bakedIn || [];
    const effectiveIndex = demo.boltedAttackIndex === 0 ? 1 : 0;
    const boltedEffective = modelCases[effectiveIndex];
    const boltedAttack = modelCases[demo.boltedAttackIndex];
    if (!boltedEffective || !boltedAttack || bakedCases.length < 1) return [];
    return [
      {
        ...boltedEffective,
        tabTitle: "Guardrail effective",
        architectureLabel: "Bolted-on effective · " + data.models[state.model].label,
      },
      {
        ...boltedAttack,
        tabTitle: "Guardrail ineffective",
        architectureLabel: "Bolted-on ineffective · " + data.models[state.model].label,
      },
      {
        ...bakedCases[0],
        tabTitle: "Baked-in defense",
        architectureLabel: "TAN baked-in defense",
      },
    ];
  }

  function currentCase() {
    const cases = currentCases();
    return cases[Math.min(state.caseIndex, Math.max(cases.length - 1, 0))];
  }

  function shortLabel(speaker) {
    const value = String(speaker || "");
    if (value.includes("Guardrail")) return "Rail";
    if (value.includes("System")) return "Sys";
    if (value.includes("Finance")) return "Fin";
    if (value.includes("Scraper")) return "Web";
    if (value.includes("Planning")) return "Plan";
    if (value.includes("Navigation")) return "Nav";
    if (value.includes("Medical")) return "Med";
    if (value.includes("Public")) return "Pub";
    if (value.includes("Cross")) return "Join";
    if (value.includes("Coder")) return "Code";
    if (value.includes("Tester")) return "Test";
    if (value.includes("TAN")) return "TAN";
    if (value.includes("Provenance")) return "Prov";
    if (value.includes("Operator")) return "Op";
    if (value.includes("Registry")) return "Reg";
    return value.slice(0, 3);
  }

  function avatarClass(speaker, kind) {
    const name = String(speaker || "").toLowerCase();
    if (name.includes("system")) return "system";
    if (name.includes("guardrail")) return "guard";
    if (kind === "model") return "model";
    return "agent";
  }

  function chipLabel(kind, speaker) {
    if (String(speaker || "").includes("Guardrail")) return "Safety check";
    if (kind === "model") return "Model response";
    if (kind === "action") return "Action";
    if (kind === "output") return "Agent output";
    return "Result";
  }

  function outcomeLabel(value) {
    if (value === "exploited") return "Bypass";
    if (value === "partial") return "Partial";
    if (value === "allowed") return "Valid";
    return "Contained";
  }

  function speakerTitle(speaker) {
    return String(speaker || "").split("·")[0].trim();
  }

  function sleep(ms, token) {
    return new Promise((resolve, reject) => {
      window.setTimeout(() => {
        if (token !== state.token) reject(new Error("cancelled"));
        else resolve();
      }, ms);
    });
  }

  function shareUrl() {
    const url = new URL(window.location.href);
    url.search = "";
    url.hash = [state.demoId, state.model, String(state.caseIndex)].join("/");
    return url.toString();
  }

  function syncLocation() {
    const next = "#" + [state.demoId, state.model, String(state.caseIndex)].join("/");
    if (window.location.hash !== next) {
      history.replaceState(null, "", next);
    }
  }

  function applyHash() {
    const raw = (window.location.hash || "").replace(/^#/, "").trim();
    if (!raw) return;

    const parts = raw.split("/").filter(Boolean);
    const demoId = parts[0];
    if (demoId && data.demos.some((demo) => demo.id === demoId)) {
      state.demoId = demoId;
    }
    if (parts[1] && data.models[parts[1]]) {
      state.model = parts[1];
    }
    if (parts[2] != null && parts[2] !== "") {
      const idx = Number(parts[2]);
      if (!Number.isNaN(idx) && idx >= 0) state.caseIndex = idx;
    }
  }

  function renderScenarios() {
    scenarioList.innerHTML = data.demos
      .map((demo, index) => {
        const active = demo.id === state.demoId ? " is-active" : "";
        const num = String(index + 1).padStart(2, "0");
        return (
          '<button type="button" class="scenario-btn' +
          active +
          '" data-demo="' +
          escapeHtml(demo.id) +
          '"><span class="scenario-index">' +
          num +
          '</span><span class="scenario-copy"><strong>' +
          escapeHtml(demo.title) +
          "</strong><small>" +
          escapeHtml(demo.subtitle) +
          "</small></span></button>"
        );
      })
      .join("");
  }

  function renderCaseTabs() {
    const cases = currentCases();
    caseTabs.innerHTML = cases
      .map((item, index) => {
        const active = index === state.caseIndex ? " is-active" : "";
        return (
          '<button type="button" class="case-tab' +
          active +
          '" data-case-index="' +
          index +
          '">' +
          escapeHtml(item.tabTitle || item.title) +
          "</button>"
        );
      })
      .join("");
  }

  function renderMeta() {
    const demo = currentDemo();
    const item = currentCase();
    const model = data.models[state.model];
    if (!item) return;

    caseKicker.textContent = demo.title + " · " + (item.architectureLabel || model.label);
    caseTitle.textContent = item.title;
    caseSummary.textContent = item.summary;
    outcomeBadge.className = "outcome " + item.outcome;
    outcomeBadge.textContent = outcomeLabel(item.outcome);
    if (modelBlurb) modelBlurb.textContent = model.blurb || "";
  }

  async function typeText(el, text, token, interval) {
    el.textContent = "";
    for (let i = 0; i < text.length; i += 1) {
      if (token !== state.token) throw new Error("cancelled");
      el.textContent += text[i];
      if (timeline && i % 12 === 0) {
        timeline.scrollTop = timeline.scrollHeight;
      }
      await sleep(interval, token);
    }
  }

  async function renderTimeline(animated) {
    const token = ++state.token;
    const item = currentCase();
    if (!item) return;

    timeline.innerHTML = "";
    if (chatStatus) chatStatus.textContent = animated ? "Replaying…" : "Recorded run";

    const turns = item.turns || [];

    for (let i = 0; i < turns.length; i += 1) {
      if (token !== state.token) return;
      const turn = turns[i];
      const role = avatarClass(turn.speaker, turn.kind);
      const isGuard = String(turn.speaker || "").includes("Guardrail");
      const msg = document.createElement("article");
      msg.className = "msg msg-" + role + (isGuard ? " msg-guard" : "");

      const bodyClass =
        turn.kind === "model" || isGuard
          ? "msg-text mono"
          : turn.kind === "result"
            ? "msg-text result"
            : "msg-text";

      msg.innerHTML =
        '<div class="msg-avatar ' +
        role +
        '" aria-hidden="true">' +
        escapeHtml(shortLabel(turn.speaker)) +
        "</div>" +
        '<div class="msg-main">' +
        '<div class="msg-meta">' +
        '<span class="msg-name">' +
        escapeHtml(speakerTitle(turn.speaker)) +
        "</span>" +
        '<span class="msg-kind">' +
        escapeHtml(chipLabel(turn.kind, turn.speaker)) +
        "</span>" +
        "</div>" +
        '<div class="' +
        bodyClass +
        '"></div>' +
        (turn.meta || turn.note
          ? '<p class="msg-note">' + escapeHtml(turn.meta || turn.note) + "</p>"
          : "") +
        "</div>";

      timeline.appendChild(msg);
      const textEl = msg.querySelector(".msg-text");
      const lower = String(turn.text || "").toLowerCase();
      if (isGuard && lower.includes("unsafe")) {
        textEl.classList.add("is-unsafe");
      } else if (isGuard && lower.includes("safe")) {
        textEl.classList.add("is-safe");
      }

      if (animated) {
        msg.classList.add("is-visible", "is-active");
        try {
          const speed = turn.kind === "model" || (turn.text || "").length > 120 ? 8 : 14;
          await typeText(textEl, turn.text || "", token, speed);
          await sleep(220, token);
        } catch (_err) {
          return;
        }
        msg.classList.remove("is-active");
      } else {
        textEl.textContent = turn.text || "";
        msg.classList.add("is-visible");
      }
    }

    if (chatStatus && token === state.token) chatStatus.textContent = "Recorded run";
  }

  function renderAll(animated) {
    const cases = currentCases();
    if (state.caseIndex >= cases.length) state.caseIndex = 0;
    errorEl.hidden = true;
    document.querySelectorAll("[data-model]").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.model === state.model);
    });
    renderScenarios();
    renderCaseTabs();
    renderMeta();
    syncLocation();
    renderTimeline(animated);
  }

  document.querySelectorAll("[data-model]").forEach((button) => {
    button.addEventListener("click", () => {
      state.model = button.dataset.model;
      renderAll(true);
    });
  });

  scenarioList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-demo]");
    if (!button) return;
    state.demoId = button.dataset.demo;
    state.caseIndex = 0;
    renderAll(true);
  });

  caseTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-case-index]");
    if (!button) return;
    state.caseIndex = Number(button.dataset.caseIndex);
    renderAll(true);
  });

  replayBtn.addEventListener("click", () => {
    renderTimeline(true);
  });

  if (copyLinkBtn) {
    copyLinkBtn.addEventListener("click", async () => {
      const url = shareUrl();
      try {
        await navigator.clipboard.writeText(url);
        copyLinkBtn.textContent = "Copied";
        window.setTimeout(() => {
          copyLinkBtn.textContent = "Copy link";
        }, 1400);
      } catch (_err) {
        window.prompt("Copy this link:", url);
      }
    });
  }

  window.addEventListener("hashchange", () => {
    applyHash();
    renderAll(true);
  });

  const params = new URLSearchParams(window.location.search);
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const staticMode = params.has("static");
  const embedMode = params.has("embed");

  if (embedMode) {
    document.body.classList.add("is-embed");
  }

  // Legacy query support, then hash.
  if (params.get("model") && data.models[params.get("model")]) {
    state.model = params.get("model");
  }
  if (params.get("demo") && data.demos.some((d) => d.id === params.get("demo"))) {
    state.demoId = params.get("demo");
  }
  if (params.get("case") != null) {
    const idx = Number(params.get("case"));
    if (!Number.isNaN(idx) && idx >= 0) state.caseIndex = idx;
  }
  applyHash();

  renderAll(!(prefersReduced || staticMode));
})();
