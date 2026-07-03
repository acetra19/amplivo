(function () {
  const API = window.AGENTUR_API || "";
  const GROUP_LABELS = {
    llm: "fields-llm",
    email: "fields-email",
    domains: "fields-domains",
    affiliate: "fields-affiliate",
    agent: "fields-agent",
    security: "fields-security",
  };
  const TEST_MAP = {
    groq_api_key: "groq",
    anthropic_api_key: "anthropic",
    brevo_api_key: "brevo",
  };

  let lastSummary = null;

  function toast(msg) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.hidden = false;
    setTimeout(function () { t.hidden = true; }, 5000);
  }

  function statusPill(f, liveStatus) {
    if (liveStatus === "ok") {
      return '<span class="key-pill key-pill-live">● LIVE</span>';
    }
    if (liveStatus === "fail") {
      return '<span class="key-pill key-pill-error">● ERROR</span>';
    }
    if (f.in_use) {
      return '<span class="key-pill key-pill-active">● IN USE</span>';
    }
    if (f.configured) {
      return '<span class="key-pill key-pill-stored">● STORED</span>';
    }
    return '<span class="key-pill key-pill-miss">○ NOT SET</span>';
  }

  function fieldClasses(f) {
    const classes = ["key-field"];
    if (f.in_use) classes.push("key-active");
    else if (f.configured) classes.push("key-stored");
    else classes.push("key-missing");
    if (f.is_secret) classes.push("key-secret");
    return classes.join(" ");
  }

  function fieldHtml(f) {
    const isPassword = f.type === "password";
    const placeholder = isPassword
      ? (f.configured ? "Leave blank to keep stored key" : "Enter API key")
      : "";
    let input = "";
    let preview = "";

    if (f.type === "select") {
      input = '<select name="' + f.key + '" data-secret="false">' +
        f.options.map(function (o) {
          return '<option value="' + o + '"' + (f.value === o ? " selected" : "") + '>' + o + "</option>";
        }).join("") + "</select>";
    } else {
      input = '<input type="' + (isPassword ? "password" : "text") + '" name="' + f.key + '" ' +
        'value="' + (isPassword ? "" : (f.value || "")) + '" placeholder="' + placeholder + '" data-secret="' + isPassword + '">';
    }

    if (isPassword && f.configured && f.value) {
      preview = '<div class="key-preview"><span class="key-preview-label">Current key</span><code>' + f.value + "</code></div>";
    } else if (!isPassword && f.configured && f.value) {
      preview = '<div class="key-preview"><span class="key-preview-label">Current value</span><code>' + f.value + "</code></div>";
    } else if (isPassword && !f.configured) {
      preview = '<div class="key-preview key-preview-empty">No key stored yet</div>';
    }

    return (
      '<div class="' + fieldClasses(f) + '" data-key="' + f.key + '" id="field-' + f.key + '">' +
        '<div class="key-field-head">' +
          '<span class="key-field-title">' + f.label + "</span>" +
          statusPill(f) +
        "</div>" +
        '<span class="field-hint">' + f.key + "</span>" +
        input +
        preview +
        '<span class="key-live-msg" hidden></span>' +
      "</div>"
    );
  }

  function renderSummary(data) {
    const el = document.getElementById("keys-summary");
    if (!el || !data.summary) return;
    lastSummary = data.summary;
    const s = data.summary;
    const provider = (s.llm_provider || "groq").toUpperCase();
    el.innerHTML =
      '<div class="summary-stat"><strong>' + s.secret_configured + "/" + s.secret_total + '</strong><span>keys stored</span></div>' +
      '<div class="summary-stat summary-highlight"><strong>' + provider + '</strong><span>active LLM</span></div>' +
      '<div class="summary-stat"><strong>' + (s.active_keys ? s.active_keys.length : 0) + '</strong><span>settings in use</span></div>' +
      '<div class="summary-note">Green border = actively used · Blue = stored · Type a new value to replace</div>';
  }

  function renderForm(data) {
    renderSummary(data);
    Object.keys(GROUP_LABELS).forEach(function (group) {
      const el = document.getElementById(GROUP_LABELS[group]);
      const fields = data.groups[group] || [];
      el.innerHTML = fields.map(fieldHtml).join("");
    });
    bindSecretInputs();
  }

  function bindSecretInputs() {
    document.querySelectorAll(".key-secret input[data-secret='true']").forEach(function (input) {
      input.addEventListener("input", function () {
        const card = input.closest(".key-field");
        const pill = card.querySelector(".key-pill");
        if (input.value) {
          card.classList.add("key-pending");
          if (pill) {
            pill.className = "key-pill key-pill-pending";
            pill.textContent = "● UNSAVED";
          }
        } else {
          card.classList.remove("key-pending");
          load();
        }
      });
    });
  }

  function applyLiveStatus(testData) {
    Object.keys(TEST_MAP).forEach(function (fieldKey) {
      const testKey = TEST_MAP[fieldKey];
      const card = document.getElementById("field-" + fieldKey);
      if (!card || !testData[testKey]) return;
      const ok = testData[testKey].ok;
      const pill = card.querySelector(".key-pill");
      const msg = card.querySelector(".key-live-msg");
      if (pill && ok) {
        pill.className = "key-pill key-pill-live";
        pill.textContent = "● LIVE";
        card.classList.add("key-live");
      } else if (pill && !ok) {
        pill.className = "key-pill key-pill-error";
        pill.textContent = "● ERROR";
        card.classList.add("key-error");
      }
      if (msg) {
        msg.hidden = false;
        msg.textContent = testData[testKey].message;
        msg.className = "key-live-msg " + (ok ? "ok" : "fail");
      }
    });
  }

  async function runConnectionTest(showPanel) {
    const panel = document.getElementById("status-panel");
    if (showPanel) {
      panel.hidden = false;
      panel.innerHTML = "Testing connections…";
    }
    try {
      const data = await fetch(API + "/settings/test", { method: "POST" }).then(function (r) { return r.json(); });
      applyLiveStatus(data);
      if (showPanel) {
        let html = "";
        ["groq", "anthropic", "brevo"].forEach(function (k) {
          if (!data[k]) return;
          const ok = data[k].ok;
          html += '<div class="status-item ' + (ok ? "ok" : "fail") + '"><strong>' + k + "</strong>: " + data[k].message + "</div>";
        });
        if (data.domains) {
          html += '<div class="status-item"><strong>domains</strong>: api=' + (data.domains.api || "–") + ", n8n=" + (data.domains.n8n || "–") + "</div>";
        }
        panel.innerHTML = html;
      }
      return data;
    } catch (err) {
      if (showPanel) {
        panel.innerHTML = '<div class="status-item fail">Test failed: ' + err.message + "</div>";
      }
      return null;
    }
  }

  async function load() {
    const pinRes = await fetch(API + "/settings/pin-required").then(function (r) { return r.json(); });
    document.getElementById("pin-banner").hidden = !pinRes.required;

    const data = await fetch(API + "/settings").then(function (r) { return r.json(); });
    renderForm(data);
    runConnectionTest(false);
  }

  function collectValues() {
    const values = {};
    document.querySelectorAll("#settings-form [name]").forEach(function (el) {
      const isSecret = el.dataset.secret === "true";
      if (isSecret && !el.value) {
        values[el.name] = "__UNCHANGED__";
      } else {
        values[el.name] = el.value;
      }
    });
    return values;
  }

  document.getElementById("save-btn").addEventListener("click", async function () {
    const pin = document.getElementById("settings-pin").value || null;
    try {
      const res = await fetch(API + "/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: collectValues(), pin: pin }),
      });
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (parseErr) {
        throw new Error(text.slice(0, 120) || "Server error");
      }
      if (!res.ok) throw new Error(data.detail || "Save failed");
      toast("Saved " + data.count + " setting(s). Active keys show as IN USE / LIVE.");
      await load();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("test-btn").addEventListener("click", function () {
    runConnectionTest(true);
  });

  document.getElementById("export-btn").addEventListener("click", async function () {
    const data = await fetch(API + "/settings/export-env").then(function (r) { return r.json(); });
    const pre = document.getElementById("export-preview");
    pre.textContent = data.env;
    pre.hidden = false;
    const blob = new Blob([data.env], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = ".env";
    a.click();
    toast(".env downloaded");
  });

  load();
})();
