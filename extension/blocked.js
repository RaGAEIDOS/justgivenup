/* Interstitial page shown when declarativeNetRequest redirects a
 * navigation to a blocked domain.  Reports the attempt to the dashboard
 * (streak stats) and shows the lock countdown + a motivational line. */
(function () {
  const API = "http://127.0.0.1:8081";
  let state = { lang: JGU.detect(null), locked: false, until: 0 };

  const $ = (id) => document.getElementById(id);

  function t(key) {
    const dict = JGU.pick(state.lang);
    return dict[key] || key;
  }

  function applyStatic() {
    const dict = JGU.pick(state.lang);
    document.documentElement.lang = state.lang;
    document.documentElement.dir = dict.dir;
    $("title").textContent = dict.stopTitle;
    $("body").textContent = dict.stopBody;
    $("advice").textContent = dict.stopAdvice;
    $("back-btn").textContent = dict.back;
    $("dash-btn").textContent = dict.openDashboard;
    $("lbl-d").textContent = dict.day;
    $("lbl-h").textContent = dict.hour;
    $("lbl-m").textContent = dict.minute;
    $("lbl-s").textContent = dict.second;
  }

  function tick() {
    if (!state.locked) return;
    const remain = Math.max(0, state.until - Math.floor(Date.now() / 1000));
    $("cd-d").textContent = Math.floor(remain / 86400);
    $("cd-h").textContent = String(Math.floor((remain % 86400) / 3600)).padStart(2, "0");
    $("cd-m").textContent = String(Math.floor((remain % 3600) / 60)).padStart(2, "0");
    $("cd-s").textContent = String(remain % 60).padStart(2, "0");
  }

  async function load() {
    try {
      const res = await fetch(`${API}/api/status`, { cache: "no-store" });
      const data = await res.json();
      state.lang = JGU.detect(data.lang);
      state.locked = !!data.lock.locked;
      state.until = data.lock.until || 0;
      $("quote").textContent = (data.motivation && data.motivation.quote) || "";
      $("lock-block").hidden = !state.locked;
      $("nolock-note").hidden = state.locked;
      $("nolock-note").textContent = t("noLock");
      if (state.locked) {
        $("until-label").textContent =
          `${t("until")} ${data.lock.expires_label || ""}`;
      }
      applyStatic();
      tick();
    } catch (e) {
      applyStatic();
      $("quote").textContent = "";
      $("lock-block").hidden = true;
      $("nolock-note").hidden = false;
      $("nolock-note").textContent = t("noLock");
    }
  }

  async function report() {
    try {
      await fetch(`${API}/api/report`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          count: 1,
          from: document.referrer || location.hostname || "interstitial",
        }),
      });
      const toast = $("toast");
      toast.textContent = t("reportSent");
      toast.classList.add("show");
      setTimeout(() => toast.classList.remove("show"), 2500);
    } catch (e) { /* daemon offline: block still happened */ }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyStatic();
    $("back-btn").addEventListener("click", () => {
      if (history.length > 1) history.back();
      else location.href = "about:blank";
    });
    load();
    report();
    setInterval(tick, 1000);
  });
})();
