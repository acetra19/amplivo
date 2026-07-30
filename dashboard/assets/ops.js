(function () {
  const API = window.AGENTUR_API || "";
  let lastPayload = null;

  const $ = function (id) { return document.getElementById(id); };

  function showToast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    setTimeout(function () { t.hidden = true; }, 3500);
  }

  function pct(n) {
    return Number(n || 0).toFixed(1) + "%";
  }

  function money(n) {
    return "€" + Number(n || 0).toFixed(0);
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderKpis(d) {
    const e = d.email;
    const q = d.lead_quality;
    const f = d.funnel;
    const s = d.sequences;
    $("k-sent").textContent = e.sent_today;
    $("k-quota").textContent = e.remaining + " left · " + pct(e.quota_utilization_pct) + " quota";
    $("k-reply").textContent = pct(e.reply_rate_7d);
    $("k-reply-n").textContent = e.replies_7d + " replies / " + e.sent_7d + " sends";
    $("k-icp").textContent = pct(q.icp_pct);
    $("k-ready").textContent = q.ready_pool + " ready to contact";
    $("k-int").textContent = f.interested;
    $("k-conv").textContent = f.converted + " conversions";
    $("k-rev").textContent = money(d.total_commission);
    $("k-overdue").textContent = s.overdue;
    $("k-seq").textContent = s.active + " active · " + s.paused + " paused";
  }

  function renderRecs(items) {
    $("rec-count").textContent = items.length;
    $("rec-list").innerHTML = items.map(function (r) {
      return '<article class="rec-card ' + esc(r.severity) + '">' +
        '<div class="rec-top"><strong>' + esc(r.title) + '</strong>' +
        '<span class="sev sev-' + esc(r.severity) + '">' + esc(r.severity) + '</span></div>' +
        '<div class="rec-area">' + esc(r.area) + ' · ' + esc(r.metric) + '=' + esc(r.value) + '</div>' +
        '<p class="rec-detail">' + esc(r.detail) + '</p></article>';
    }).join("");
  }

  function renderBars(el, rows, nameKey, countKey) {
    const max = Math.max.apply(null, rows.map(function (r) { return r[countKey]; }).concat([1]));
    el.innerHTML = rows.map(function (r) {
      const w = Math.round((r[countKey] / max) * 100);
      return '<div class="funnel-row"><span>' + esc(r[nameKey]) + '</span>' +
        '<div class="funnel-track"><div class="funnel-fill" style="width:' + w + '%"></div></div>' +
        '<strong>' + r[countKey] + '</strong></div>';
    }).join("") || '<p class="group-desc">No data yet</p>';
  }

  function renderFunnel(f) {
    const stages = [
      { name: "Total", count: f.total_leads },
      { name: "Enriched", count: f.enriched },
      { name: "Contacted", count: f.contacted },
      { name: "Replied", count: f.replied },
      { name: "Interested", count: f.interested },
      { name: "Converted", count: f.converted },
      { name: "Lost", count: f.lost },
    ];
    renderBars($("funnel-bars"), stages, "name", "count");
  }

  function renderTrend(rows) {
    const max = Math.max.apply(null, rows.map(function (r) {
      return Math.max(r.sent, r.replies);
    }).concat([1]));
    $("trend-chart").innerHTML = rows.map(function (r) {
      const sh = Math.max(2, Math.round((r.sent / max) * 100));
      const rh = Math.max(r.replies ? 2 : 0, Math.round((r.replies / max) * 100));
      const label = r.day.slice(5);
      return '<div class="trend-col" title="' + esc(r.day) + ': ' + r.sent + ' sent, ' + r.replies + ' replies">' +
        '<div class="trend-bars">' +
        '<div class="bar sent" style="height:' + sh + '%"></div>' +
        '<div class="bar reply" style="height:' + rh + '%"></div>' +
        '</div><span class="trend-day">' + esc(label) + '</span></div>';
    }).join("");
  }

  function renderQuality(q) {
    $("quality-grid").innerHTML =
      '<div class="q-card"><span>Avg score</span><strong>' + q.avg_score + '</strong></div>' +
      '<div class="q-card"><span>Info@ share</span><strong>' + pct(q.info_email_pct) + '</strong></div>' +
      '<div class="q-card"><span>ICP leads</span><strong>' + q.icp_leads + '</strong></div>' +
      '<div class="q-card"><span>Ready pool</span><strong>' + q.ready_pool + '</strong></div>';

    $("industry-list").innerHTML = q.by_industry.map(function (r) {
      return '<li><span>' + esc(r.name) + '</span><span class="muted">' + r.count + '</span></li>';
    }).join("") || '<li>No data</li>';

    $("source-list").innerHTML = q.by_source.map(function (r) {
      return '<li><span>' + esc(r.name) + '</span><span class="muted">' + r.count + '</span></li>';
    }).join("") || '<li>No data</li>';
  }

  function renderReplies(items) {
    $("reply-feed").innerHTML = items.length ? items.map(function (r) {
      return '<li><strong>' + esc(r.sentiment || "unknown") + '</strong> · ' +
        esc(r.email) +
        '<span class="feed-meta">' + esc(r.summary || r.subject || "") +
        ' · ' + new Date(r.at).toLocaleString() + '</span></li>';
    }).join("") : '<li>No inbound replies yet</li>';
  }

  function renderJson(d) {
    $("json-preview").textContent = JSON.stringify(d, null, 2);
  }

  function renderPlumbing(p) {
    if (!p) return;
    $("plumb-score").textContent = (p.ready ? "READY " : "") + (p.score || "");
    $("plumb-note").textContent = p.systeme_note || "";
    $("plumb-checks").innerHTML = (p.checks || []).map(function (c) {
      return '<li><span>' + (c.ok ? "OK" : "FAIL") + " · " + esc(c.detail) +
        '</span><span class="muted">' + esc(c.id) + "</span></li>";
    }).join("");
    $("plumb-url").textContent = p.sample_tracked_url || "not configured";
  }

  async function load() {
    try {
      const [res, plumbRes] = await Promise.all([
        fetch(API + "/ops/insights"),
        fetch(API + "/ops/plumbing"),
      ]);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      lastPayload = data;
      renderKpis(data);
      renderRecs(data.recommendations || []);
      renderFunnel(data.funnel);
      renderTrend(data.trend_14d || []);
      renderQuality(data.lead_quality);
      renderBars($("sentiment-bars"), data.reply_sentiment_30d || [], "sentiment", "count");
      renderReplies(data.recent_replies || []);
      renderJson(data);
      if (plumbRes.ok) renderPlumbing(await plumbRes.json());
    } catch (err) {
      showToast("Failed to load ops insights");
      $("json-preview").textContent = String(err);
    }
  }

  $("refresh-btn").addEventListener("click", load);
  $("copy-json-btn").addEventListener("click", function () {
    if (!lastPayload) return;
    navigator.clipboard.writeText(JSON.stringify(lastPayload, null, 2)).then(function () {
      showToast("Insights JSON copied");
    }).catch(function () {
      showToast("Copy failed");
    });
  });

  load();
  setInterval(load, 60000);
})();
