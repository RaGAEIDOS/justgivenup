/* Options page: read-only status. All settings live in the dashboard —
 * deliberately, so the extension UI can never weaken the protection. */
(function () {
  const API = "http://127.0.0.1:8081";
  const ext = globalThis.chrome || globalThis.browser;
  let lang = JGU.detect(null);

  const $ = (id) => document.getElementById(id);

  const L = {
    ar: {
      dir: "rtl",
      status: "حالة الخدمة", lock: "القفل الزمني", streak: "أيام نظيفة",
      blocked: "محاولات محظورة", rules: "قواعد الحجب الثابتة",
      info: "الإعدادات كلها في لوحة التحكم المحلية — الإكستنشن نفسه مبيقدرش يغيّر قواعد الحجب وقت ما القفل شغال. حذف الإكستنشن وهو القفل شغال = عقوبة +٩٠ يوم على القفل.",
      active: "شغال", down: "متوقفة", locked: "مقفول", unlocked: "غير مقفول",
      banner: "القفل الزمني شغال حتى ",
      rulesInfo: "قاعدة",
    },
    en: {
      dir: "ltr",
      status: "Service", lock: "Time-lock", streak: "Clean streak",
      blocked: "Blocked attempts", rules: "Static rules",
      info: "Every setting lives in the local dashboard — this extension cannot weaken the rules while the lock runs. Removing the extension while locked adds +90 days to the lock.",
      active: "running", down: "offline", locked: "locked", unlocked: "not locked",
      banner: "Time-lock active until ",
      rulesInfo: "rule(s)",
    },
  };

  function d() { return L[lang] || L.ar; }

  function applyStatic() {
    document.documentElement.lang = lang;
    document.documentElement.dir = d().dir;
    $("l-status").textContent = d().status;
    $("l-lock").textContent = d().lock;
    $("l-streak").textContent = d().streak;
    $("l-blocked").textContent = d().blocked;
    $("l-rules").textContent = d().rules;
    $("info-text").textContent = d().info;
    $("dash").textContent = d().status === "Service" ? "Dashboard" : "لوحة التحكم";
  }

  async function load() {
    try {
      const res = await fetch(`${API}/api/status`, { cache: "no-store" });
      const data = await res.json();
      lang = JGU.detect(data.lang);
      applyStatic();
      $("v-status").textContent = d().active;
      $("v-status").className = "";
      const locked = !!data.lock.locked;
      $("v-lock").textContent = locked ? d().locked : d().unlocked;
      $("v-lock").className = locked ? "bad" : "";
      $("v-streak").textContent = data.stats.clean_days;
      $("v-blocked").textContent = data.stats.total_blocked;
      $("sub").textContent = `v${data.version} — ${data.extension.browser || ""}`;
      if (locked) {
        $("lock-banner").hidden = false;
        $("lock-banner").textContent = d().banner + data.lock.expires_label;
      }
      $("dash").href = `http://127.0.0.1:${data.settings.port || 8081}/`;
    } catch (e) {
      applyStatic();
      $("v-status").textContent = d().down;
      $("v-status").className = "bad";
      $("v-lock").textContent = "?";
      $("v-streak").textContent = "?";
      $("v-blocked").textContent = "?";
    }
    try {
      const staticCount = await ext.declarativeNetRequest.getStaticRuleCount?.();
      if (typeof staticCount === "number") {
        $("v-rules").textContent = `${staticCount} ${d().rulesInfo}`;
      } else {
        $("v-rules").textContent = "rules.json";
      }
    } catch (e) {
      $("v-rules").textContent = "rules.json";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyStatic();
    load();
  });
})();
