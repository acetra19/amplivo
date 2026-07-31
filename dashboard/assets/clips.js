(function () {
  const $ = (id) => document.getElementById(id);
  const toast = $("toast");
  const logEl = $("action-log");

  function showToast(msg, ok = true) {
    toast.hidden = false;
    toast.textContent = msg;
    toast.style.borderColor = ok ? "var(--success)" : "var(--danger)";
    setTimeout(() => { toast.hidden = true; }, 3200);
  }

  function log(obj) {
    logEl.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.reason || res.statusText);
    return data;
  }

  function pill(status) {
    return `<span class="status-pill ${status || ""}">${status || "—"}</span>`;
  }

  function money(n, currency) {
    if (n == null) return "—";
    const cur = currency || "USD";
    const symbol = cur === "EUR" ? "€" : "$";
    return `${symbol}${Number(n).toFixed(2)} ${cur}`;
  }

  function linkOrDash(url, label) {
    if (!url) return "—";
    return `<a class="linkish" href="${url}" target="_blank" rel="noopener">${label || "open"}</a>`;
  }

  function renderRuntime(rt) {
    const el = $("runtime-banner");
    if (!el || !rt) return;
    const mode = rt.dry_run ? "DRY-RUN" : "LIVE";
    const opus = rt.opusclip_configured ? "Opus key set" : "no Opus key → dry clips";
    el.textContent = `Mode: ${mode} · max jobs/run: ${rt.max_jobs_per_run} · ${opus}`;
  }

  function renderStats(s) {
    $("k-work").textContent = s.workable_campaigns ?? 0;
    $("k-flight").textContent = s.in_flight ?? 0;
    $("k-ready").textContent = s.ready ?? 0;
    $("k-sub").textContent = s.submitted ?? 0;
    $("k-paid").textContent = s.paid ?? 0;
    $("k-payout").textContent = `earned ${money(s.payout_total, "USD")}`;
    $("k-bad").textContent = (s.failed || 0) + (s.rejected || 0);
  }

  function renderCampaigns(rows) {
    const tbody = $("campaigns-table").querySelector("tbody");
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">No campaigns yet. Seed demos or add one.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((c) => `
      <tr>
        <td>
          <strong>${esc(c.title)}</strong>
          <div class="muted" style="font-size:0.72rem">${esc(c.source_url || "")}</div>
        </td>
        <td>${esc(c.marketplace)}</td>
        <td>${c.payout_rate != null ? money(c.payout_rate) : "—"}</td>
        <td>${pill(c.status)}</td>
        <td class="row-actions">
          <button class="btn-tiny" data-close="${c.id}" type="button">Close</button>
        </td>
      </tr>
    `).join("");
    tbody.querySelectorAll("[data-close]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api(`/clips/campaigns/${btn.dataset.close}/status`, {
            method: "POST",
            body: JSON.stringify({ status: "closed" }),
          });
          showToast("Campaign closed");
          await load();
        } catch (e) {
          showToast(e.message, false);
        }
      });
    });
  }

  function renderJobs(rows) {
    const tbody = $("jobs-table").querySelector("tbody");
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">No jobs yet. Run drain or produce.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((j) => `
      <tr>
        <td>
          <strong>${esc(j.campaign_title || "—")}</strong>
          <div class="muted" style="font-size:0.72rem">${esc(j.marketplace || "")}</div>
        </td>
        <td>${pill(j.status)}</td>
        <td>${j.qa_score != null ? j.qa_score : "—"}</td>
        <td>
          ${linkOrDash(j.clip_url, "clip")}
          · ${linkOrDash(j.post_url, "post")}
          ${j.error_message ? `<div class="muted" style="font-size:0.7rem">${esc(j.error_message)}</div>` : ""}
        </td>
        <td class="row-actions">
          ${j.status === "ready" ? `<button class="btn-tiny" data-submit="${j.id}" type="button">Submit</button>` : ""}
          ${j.status === "submitted" ? `<button class="btn-tiny" data-paid="${j.id}" type="button">Mark paid</button>` : ""}
        </td>
      </tr>
    `).join("");

    tbody.querySelectorAll("[data-submit]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const post = prompt("Post URL (or leave blank for dry stub)");
        if (post === null) return;
        try {
          const postUrl = (post || "").trim() || `https://proof.amplivo.net/clips/${btn.dataset.submit}`;
          await api(`/clips/jobs/${btn.dataset.submit}/submit`, {
            method: "POST",
            body: JSON.stringify({ post_url: postUrl }),
          });
          showToast("Job submitted");
          await load();
        } catch (e) {
          showToast(e.message, false);
        }
      });
    });

    tbody.querySelectorAll("[data-paid]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const amount = prompt("Payout amount (optional)");
        try {
          await api(`/clips/jobs/${btn.dataset.paid}/paid`, {
            method: "POST",
            body: JSON.stringify({
              payout_amount: amount ? Number(amount) : null,
            }),
          });
          showToast("Marked paid");
          await load();
        } catch (e) {
          showToast(e.message, false);
        }
      });
    });
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function load() {
    const data = await api("/clips/overview");
    renderRuntime(data.runtime || {});
    renderStats(data.stats || {});
    renderCampaigns(data.campaigns || []);
    renderJobs(data.jobs || []);
  }

  async function runAction(label, fn) {
    log(`${label}…`);
    try {
      const result = await fn();
      log(result);
      showToast(label + " OK");
      await load();
    } catch (e) {
      log(String(e.message || e));
      showToast(e.message || "failed", false);
    }
  }

  $("refresh-btn").addEventListener("click", () => load().catch((e) => showToast(e.message, false)));
  $("drain-btn").addEventListener("click", () =>
    runAction("Drain", () => api("/clips/drain", {
      method: "POST",
      body: JSON.stringify({}),
    }))
  );
  $("seed-btn").addEventListener("click", () =>
    runAction("Seed demos", () => api("/clips/campaigns/seed", { method: "POST" }))
  );
  $("poll-btn").addEventListener("click", () =>
    runAction("Poll producing", () => api("/clips/jobs/poll", { method: "POST" }))
  );
  $("run-btn").addEventListener("click", () =>
    runAction("Produce", () => api("/clips/jobs/run", {
      method: "POST",
      body: JSON.stringify({}),
    }))
  );
  $("submit-btn").addEventListener("click", () =>
    runAction("Auto-submit", () => api("/clips/jobs/auto-submit", { method: "POST" }))
  );

  $("campaign-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await api("/clips/campaigns", {
        method: "POST",
        body: JSON.stringify({
          title: $("c-title").value.trim(),
          source_url: $("c-url").value.trim(),
          marketplace: $("c-market").value,
          brief: $("c-brief").value.trim() || null,
          payout_rate: $("c-rate").value ? Number($("c-rate").value) : null,
          payout_model: "cpm",
          currency: "USD",
        }),
      });
      showToast("Campaign created");
      ev.target.reset();
      await load();
    } catch (e) {
      showToast(e.message, false);
    }
  });

  load().catch((e) => {
    log(String(e.message || e));
    showToast(e.message || "load failed", false);
  });
})();
