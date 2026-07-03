(function () {
  const API = window.AGENTUR_API || "";
  const GROUP_LABELS = { llm: "fields-llm", email: "fields-email", domains: "fields-domains", affiliate: "fields-affiliate", agent: "fields-agent", security: "fields-security" };

  function toast(msg) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.hidden = false;
    setTimeout(function () { t.hidden = true; }, 4500);
  }

  function fieldHtml(f) {
    const configured = f.configured ? '<span class="tag-ok">configured</span>' : '<span class="tag-miss">missing</span>';
    const placeholder = f.type === "password" ? "Enter new value (leave blank to keep)" : "";
    let input = "";

    if (f.type === "select") {
      input = '<select name="' + f.key + '" data-secret="' + (f.type === "password") + '">' +
        f.options.map(function (o) {
          return '<option value="' + o + '"' + (f.value === o ? " selected" : "") + '>' + o + '</option>';
        }).join("") + "</select>";
    } else {
      input = '<input type="' + (f.type === "password" ? "password" : "text") + '" name="' + f.key + '" ' +
        'value="' + (f.type === "password" ? "" : (f.value || "")) + '" placeholder="' + placeholder + '" data-secret="' + (f.type === "password") + '">';
    }

    return '<label class="field-label">' + f.label + " " + configured +
      '<span class="field-hint">' + f.key + "</span>" + input + "</label>";
  }

  function renderForm(data) {
    Object.keys(GROUP_LABELS).forEach(function (group) {
      const el = document.getElementById(GROUP_LABELS[group]);
      const fields = data.groups[group] || [];
      el.innerHTML = fields.map(fieldHtml).join("");
    });
  }

  async function load() {
    const pinRes = await fetch(API + "/settings/pin-required").then(function (r) { return r.json(); });
    document.getElementById("pin-banner").hidden = !pinRes.required;

    const data = await fetch(API + "/settings").then(function (r) { return r.json(); });
    renderForm(data);
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
      toast("Saved " + data.count + " settings – active immediately");
      load();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("test-btn").addEventListener("click", async function () {
    const panel = document.getElementById("status-panel");
    panel.hidden = false;
    panel.innerHTML = "Testing connections…";
    try {
      const data = await fetch(API + "/settings/test", { method: "POST" }).then(function (r) { return r.json(); });
      let html = "";
      ["groq", "anthropic", "brevo"].forEach(function (k) {
        if (!data[k]) return;
        const ok = data[k].ok;
        html += '<div class="status-item ' + (ok ? "ok" : "fail") + '"><strong>' + k + '</strong>: ' + data[k].message + "</div>";
      });
      if (data.domains) {
        html += '<div class="status-item"><strong>domains</strong>: api=' + (data.domains.api || "–") + ", n8n=" + (data.domains.n8n || "–") + "</div>";
      }
      panel.innerHTML = html;
    } catch (err) {
      panel.innerHTML = '<div class="status-item fail">Test failed: ' + err.message + "</div>";
    }
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
