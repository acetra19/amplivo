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

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      const msg = typeof detail === "string" ? detail : (detail && JSON.stringify(detail)) || res.statusText;
      throw new Error(msg);
    }
    return data;
  }

  function renderQuota(q, readyCount, inboxCount) {
    $("k-sent").textContent = q.sent_today ?? 0;
    $("k-rem").textContent = q.remaining ?? 0;
    $("k-limit").textContent = `limit ${q.daily_limit ?? 30}`;
    $("k-ready").textContent = readyCount ?? 0;
    $("k-inbox").textContent = inboxCount ?? 0;
  }

  function renderReady(leads) {
    const tbody = $("ready-table").querySelector("tbody");
    if (!leads.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="muted">No ready leads. Import CSV or add a lead.</td></tr>`;
      return;
    }
    tbody.innerHTML = leads.map((l) => `
      <tr>
        <td>
          <strong>${esc(l.email)}</strong>
          <div class="muted" style="font-size:0.72rem">${esc(l.first_name || "")}</div>
        </td>
        <td>${esc(l.company || "—")}</td>
        <td>${l.score != null ? l.score : "—"}</td>
        <td>${l.generic_inbox ? '<span class="flag-pill warn">generic</span>' : '<span class="flag-pill">personal</span>'}</td>
      </tr>
    `).join("");
  }

  function linkCtaBody(item) {
    const name = item.first_name || "there";
    const url = item.affiliate_url || "{{affiliate_url}}";
    return (
      `Hi ${name},\n\n` +
      `Thanks for your reply — here is the free Systeme.io access (no credit card):\n${url}\n\n` +
      `Click the link to start. If anything is unclear, just reply here.\n\nBest regards`
    );
  }

  function questionBody(item) {
    const name = item.first_name || "there";
    const url = item.affiliate_url || "";
    return (
      `Hi ${name},\n\n` +
      `Thanks for the message — happy to answer.\n\n` +
      (url ? `If useful, free access is here:\n${url}\n\n` : "") +
      `Best regards`
    );
  }

  function renderInbox(items) {
    const root = $("inbox-list");
    if (!items.length) {
      root.innerHTML = `<p class="muted">Inbox clear — no needs_action replies.</p>`;
      return;
    }
    root.innerHTML = items.map((item, idx) => `
      <article class="inbox-card" data-idx="${idx}">
        <h3>${esc(item.email)} · ${esc(item.company || "")}</h3>
        <div class="inbox-meta">${esc(item.action_reason || "")} · ${esc(item.sentiment || "")} · ${esc(item.age_hours)}h ago</div>
        <div class="inbox-preview">${esc(item.body_preview || item.summary || "")}</div>
        <div class="inbox-actions">
          <button class="btn-tiny" type="button" data-preset="link" data-idx="${idx}">Preset: Send link CTA</button>
          <button class="btn-tiny" type="button" data-preset="question" data-idx="${idx}">Preset: Answer question</button>
        </div>
        <div class="reply-box">
          <input data-subj="${idx}" placeholder="Subject" value="Re: Systeme.io free access">
          <textarea data-body="${idx}" rows="5" placeholder="Reply body"></textarea>
          <button class="btn" type="button" data-send="${idx}">Send reply</button>
        </div>
      </article>
    `).join("");

    root.querySelectorAll("[data-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = Number(btn.dataset.idx);
        const item = items[i];
        const body = btn.dataset.preset === "link" ? linkCtaBody(item) : questionBody(item);
        const subj = root.querySelector(`[data-subj="${i}"]`);
        const ta = root.querySelector(`[data-body="${i}"]`);
        if (subj) subj.value = btn.dataset.preset === "link"
          ? "Your free Systeme.io link"
          : "Re: your question";
        if (ta) ta.value = body;
      });
    });

    root.querySelectorAll("[data-send]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const i = Number(btn.dataset.send);
        const item = items[i];
        const subject = root.querySelector(`[data-subj="${i}"]`)?.value?.trim();
        const body = root.querySelector(`[data-body="${i}"]`)?.value?.trim();
        if (!subject || !body) {
          showToast("Subject and body required", false);
          return;
        }
        try {
          const result = await api("/outbound/reply", {
            method: "POST",
            body: JSON.stringify({ lead_id: item.lead_id, subject, body }),
          });
          log(result);
          showToast("Reply sent");
          await load();
        } catch (e) {
          showToast(e.message, false);
          log(String(e.message || e));
        }
      });
    });
  }

  function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map((h) => h.trim().toLowerCase());
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const row = {};
      headers.forEach((h, idx) => { row[h] = (cols[idx] || "").trim(); });
      if (row.email) rows.push(row);
    }
    return rows;
  }

  async function load() {
    const [ready, inbox] = await Promise.all([
      api("/ops/leads/ready?limit=30"),
      api("/ops/inbox?days=30&limit=40"),
    ]);
    renderQuota(ready.quota || {}, (ready.leads || []).length, inbox.needs_action_count || 0);
    renderReady(ready.leads || []);
    renderInbox(inbox.needs_action || []);
  }

  $("refresh-btn").addEventListener("click", () => {
    load().catch((e) => showToast(e.message, false));
  });

  $("drain-btn").addEventListener("click", async () => {
    log("Drain…");
    try {
      const result = await api("/outbound/drain-quota", {
        method: "POST",
        body: JSON.stringify({ max_new: 12 }),
      });
      log(result);
      showToast(`Drain sent ${result.sent_new || 0}`);
      await load();
    } catch (e) {
      showToast(e.message, false);
      log(String(e.message || e));
    }
  });

  $("lead-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const payload = {
        email: $("l-email").value.trim(),
        first_name: $("l-first").value.trim() || null,
        company: $("l-company").value.trim() || null,
        website: $("l-website").value.trim() || null,
        industry: "online_business",
        country: "DE",
        source: "dashboard",
      };
      const result = await api("/leads", { method: "POST", body: JSON.stringify(payload) });
      log(result);
      showToast("Lead created");
      ev.target.reset();
      await load();
    } catch (e) {
      showToast(e.message, false);
    }
  });

  $("csv-import-btn").addEventListener("click", async () => {
    const rows = parseCsv($("csv-paste").value);
    if (!rows.length) {
      showToast("No CSV rows found", false);
      return;
    }
    log(`Importing ${rows.length}…`);
    let ok = 0;
    let fail = 0;
    for (const row of rows) {
      try {
        await api("/leads", {
          method: "POST",
          body: JSON.stringify({
            email: row.email,
            first_name: row.first_name || null,
            company: row.company || null,
            website: row.website || null,
            industry: row.industry || "online_business",
            country: row.country || "DE",
            source: row.source || "csv_dashboard",
          }),
        });
        ok += 1;
      } catch {
        fail += 1;
      }
    }
    log({ imported: ok, failed: fail });
    showToast(`Imported ${ok}, failed ${fail}`, fail === 0);
    await load();
  });

  $("conv-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const amount = $("c-amount").value;
      const result = await api("/ops/record-conversion", {
        method: "POST",
        body: JSON.stringify({
          email: $("c-email").value.trim(),
          event_type: $("c-event").value,
          commission_amount: amount ? Number(amount) : null,
        }),
      });
      log(result);
      showToast("Conversion recorded");
      ev.target.reset();
    } catch (e) {
      showToast(e.message, false);
      log(String(e.message || e));
    }
  });

  load().catch((e) => {
    log(String(e.message || e));
    showToast(e.message || "load failed", false);
  });
})();
