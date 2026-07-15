(function () {
  const API_BASE = window.AGENTUR_API || "";

  let leadId = null;
  let history = [];
  let affiliateUrl = null;

  const registerForm = document.getElementById("register-form");
  const registerCard = document.getElementById("register-card");
  const chatCard = document.getElementById("chat-card");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const registerError = document.getElementById("register-error");
  const scoreBadge = document.getElementById("score-badge");
  const trialLink = document.getElementById("trial-link");

  function appendMessage(role, text) {
    const el = document.createElement("div");
    el.className = "msg " + (role === "user" ? "msg-user" : "msg-bot");
    el.textContent = text;
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function api(path, options) {
    const res = await fetch(API_BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.detail || res.statusText || "Request failed");
    return data;
  }

  registerForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    registerError.hidden = true;

    const fd = new FormData(registerForm);
    const payload = {
      email: fd.get("email"),
      first_name: fd.get("first_name") || null,
      company: fd.get("company") || null,
      industry: "online_business",
      source: "landing",
    };

    try {
      const data = await api("/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      leadId = data.lead_id;
      affiliateUrl = data.affiliate_url;

      registerCard.hidden = true;
      chatCard.hidden = false;

      if (data.score != null) {
        scoreBadge.textContent = "Score: " + data.score;
      }

      appendMessage("bot", data.welcome_message);
      history.push({ role: "assistant", content: data.welcome_message });
    } catch (err) {
      registerError.textContent = err.message;
      registerError.hidden = false;
    }
  });

  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text || !leadId) return;

    chatInput.value = "";
    appendMessage("user", text);
    history.push({ role: "user", content: text });

    const typing = document.createElement("div");
    typing.className = "typing";
    typing.textContent = "Assistant is typing…";
    chatMessages.appendChild(typing);

    try {
      const data = await api("/chat", {
        method: "POST",
        body: JSON.stringify({ lead_id: leadId, message: text, history: history }),
      });

      typing.remove();
      appendMessage("bot", data.reply);
      history.push({ role: "assistant", content: data.reply });

      if (data.score != null) {
        scoreBadge.textContent = "Score: " + data.score;
      }

      if (data.ready_for_trial && (data.affiliate_url || affiliateUrl)) {
        trialLink.href = data.affiliate_url || affiliateUrl || "#";
        trialLink.hidden = false;
      }
    } catch (err) {
      typing.remove();
      appendMessage("bot", "Sorry, something went wrong. Please try again.");
    }
  });
})();
