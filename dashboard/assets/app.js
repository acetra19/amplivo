(function () {
  const API = window.AGENTUR_API || "";
  let lastAchievements = new Set();

  const $ = function (id) { return document.getElementById(id); };

  function showToast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    setTimeout(function () { t.hidden = true; }, 4000);
  }

  function fmtMoney(n) {
    return "€" + Number(n || 0).toFixed(0);
  }

  function renderQuests(quests) {
    const el = $("quests-list");
    el.innerHTML = quests.map(function (q) {
      const pct = Math.min(100, (q.current / q.target) * 100);
      const done = q.completed ? " done" : "";
      return '<div class="quest-card' + done + '">' +
        '<div class="quest-top"><span>' + q.title + '</span><span>' + q.current + '/' + q.target + '</span></div>' +
        '<div class="quest-bar"><div class="quest-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="quest-reward">+' + q.xp_reward + ' XP reward</div></div>';
    }).join("");
  }

  function renderAchievements(items) {
    $("ach-count").textContent = items.filter(function (a) { return a.unlocked; }).length + "/" + items.length;
    $("achievements-grid").innerHTML = items.map(function (a) {
      const cls = a.unlocked ? " unlocked" : "";
      return '<div class="ach-card' + cls + '" title="' + a.description + '">' +
        '<span class="ach-icon">' + a.icon + '</span>' +
        '<div class="ach-title">' + a.title + '</div>' +
        '<div class="ach-desc">' + a.description + '</div></div>';
    }).join("");

    items.forEach(function (a) {
      if (a.unlocked && !lastAchievements.has(a.slug)) {
        showToast("Achievement unlocked: " + a.icon + " " + a.title);
      }
      if (a.unlocked) lastAchievements.add(a.slug);
    });
  }

  function renderFeed(agentFeed, xpFeed) {
    $("agent-feed").innerHTML = agentFeed.length ? agentFeed.map(function (a) {
      return '<li>' + a.agent_name + ': ' + (a.output_summary || a.status) +
        '<span class="feed-meta">' + new Date(a.started_at).toLocaleString() + '</span></li>';
    }).join("") : '<li>No agent runs yet – import your first lead!</li>';

    $("xp-feed").innerHTML = xpFeed.map(function (e) {
      return '<li>+' + e.xp_amount + ' XP · ' + (e.description || e.event_type) +
        '<span class="feed-meta">' + new Date(e.created_at).toLocaleString() + '</span></li>';
    }).join("");
  }

  function renderProfile(p) {
    $("level-num").textContent = p.level;
    $("rank-title").textContent = p.title;
    $("display-name").textContent = p.display_name;
    $("xp-total").textContent = p.xp_total;
    $("xp-next").textContent = p.xp_to_next_level;
    $("xp-fill").style.width = p.xp_progress_pct + "%";
    $("streak-days").textContent = p.streak_days;

    const ring = document.querySelector(".level-ring");
    if (ring) ring.style.background = "conic-gradient(var(--accent2) " + p.xp_progress_pct + "%, var(--surface2) 0)";
  }

  function renderPipeline(p) {
    $("s-leads").textContent = p.total_leads;
    $("s-icp").textContent = p.icp_leads;
    $("s-emails").textContent = p.emails_sent_today;
    $("s-conv").textContent = p.conversions;
    $("s-rev").textContent = fmtMoney(p.total_commission);
    $("s-voice").textContent = p.voice_queue_length;
  }

  async function load() {
    try {
      const [dash, pipe] = await Promise.all([
        fetch(API + "/dashboard/state").then(function (r) { return r.json(); }),
        fetch(API + "/pipeline/stats").then(function (r) { return r.json(); }),
      ]);
      renderProfile(dash.profile);
      renderQuests(dash.daily_quests);
      renderAchievements(dash.achievements);
      renderFeed(dash.agent_feed, dash.recent_xp);
      renderPipeline(pipe);
    } catch (err) {
      showToast("Failed to load dashboard. Is the API running?");
    }
  }

  $("refresh-btn").addEventListener("click", load);
  load();
  setInterval(load, 30000);
})();
