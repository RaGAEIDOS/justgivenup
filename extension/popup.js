/* Popup renderer: talks to the local daemon, ticks the countdown. */
(function () {
  const API = "http://127.0.0.1:8081";
  const ext = globalThis.chrome || globalThis.browser;
  let state = { locked: false, until: 0, lang: "ar", serverDown: false };

  const $ = (id) => document.getElementById(id);

  function t(key) {
    return JGU.pick(state.lang)[key] || key;
  }

  function applyStaticText() {
    const dict = JGU.pick(state.lang);
    document.documentElement.lang = state.lang;
    document.documentElement.dir = dict.dir;
    $("lbl-d").textContent = dict.day;
    $("lbl-h").textContent = dict.hour;
    $("lbl-m").textContent = dict.minute;
    $("lbl-s").textContent = dict.second;
    $("down-msg").textContent = dict.serverDown;
    $("down-note").textContent = dict.serverDownNote;
    $("lock-note").textContent = dict.lockNote;
    $("u-streak-lbl").textContent = dict.streak;
    $("u-blocked-lbl").textContent = dict.blocked;
    $("u-relapse-lbl").textContent = dict.relapses;
    $("unlocked-note").textContent = dict.unlockedNote;
    $("lock-link").textContent = dict.lockNow;
    $("dash-link").textContent = dict.dashboard;
    $("dash-foot").textContent = dict.dashboard;
  }

  function render() {
    const pill = $("pill");
    $("server-down").hidden = !state.serverDown;
    $("locked-view").hidden = state.serverDown || !state.locked;
    $("unlocked-view").hidden = state.serverDown || state.locked;

    if (state.serverDown) {
      pill.textContent = "— offline";
      pill.className = "pill";
      return;
    }
    if (state.locked) {
      pill.textContent = t("locked");
      pill.className = "pill locked";
      $("until-label").textContent =
        `${t("until")} ${state.expiresLabel || ""}`;
    } else {
      pill.textContent = t("unlocked");
      pill.className = "pill ok";
    }
  }

  function tickCountdown() {
    if (!state.locked) return;
    const remain = Math.max(0, state.until - Math.floor(Date.now() / 1000));
    const d = Math.floor(remain / 86400);
    const h = Math.floor((remain % 86400) / 3600);
    const m = Math.floor((remain % 3600) / 60);
    const s = remain % 60;
    $("cd-d").textContent = d;
    $("cd-h").textContent = String(h).padStart(2, "0");
    $("cd-m").textContent = String(m).padStart(2, "0");
    $("cd-s").textContent = String(s).padStart(2, "0");
    if (remain === 0) refresh();
  }

  async function refresh() {
    try {
      const res = await fetch(`${API}/api/status`, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.locked = !!data.lock.locked;
      state.until = data.lock.until || 0;
      state.expiresLabel = data.lock.expires_label || "";
      state.lang = JGU.detect(data.lang);
      state.serverDown = false;
      $("ver").textContent = "v" + data.version;
      $("quote").textContent = (data.motivation && data.motivation.quote) || "";
      $("u-streak").textContent = (data.stats && data.stats.clean_days) || 0;
      $("u-blocked").textContent = (data.stats && data.stats.total_blocked) || 0;
      $("u-relapse").textContent = (data.stats && data.stats.total_relapses) || 0;
      const base = `${API}/`;
      $("dash-link").href = base;
      $("dash-foot").href = base;
      $("lock-link").href = base + "#lock";
      applyStaticText();
      render();
      tickCountdown();
    } catch (e) {
      state.serverDown = true;
      // fall back to last known state from storage
      try {
        const stored = (await ext.storage.local.get("jgu")).jgu;
        if (stored && stored.until) {
          state.locked = !!stored.locked;
          state.until = stored.until;
        }
      } catch (e2) { /* ignore */ }
      applyStaticText();
      render();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyStaticText();
    render();
    refresh();
    setInterval(tickCountdown, 1000);
    try {
      ext.runtime.sendMessage({ type: "jgu-refresh" }, () => void 0);
    } catch (e) { /* ignore */ }
  });
})();
