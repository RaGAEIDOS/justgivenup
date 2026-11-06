/* JustGivenUp! dashboard frontend — bilingual (AR/EN), tabbed SPA.
 * Talks only to the local daemon (same origin).
 */
"use strict";

const $ = (id) => document.getElementById(id);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ------------------------------------------------------------------ */
/* i18n                                                                */
/* ------------------------------------------------------------------ */
const STR = {
  ar: {
    dashboard: "الرئيسية", lock: "القفل", motivation: "التحفيز",
    ranks: "الرتب", events: "السجل", settings: "الإعدادات",
    day: "يوم", hour: "ساعة", min: "دقيقة", sec: "ثانية",
    streak: "أيام نظيفة", blocked: "محاولات محظورة", relapse: "انتكاسات",
    rank: "الرتبة الحالية", longest: "أطول سلسلة",
    lockedUntil: "القفل ينهي في", lockActive: "القفل الزمني شغال",
    noLock: "مفيش قفل زمني حاليًا",
    lockNote: "الحماية شغالة، ومفيش قفل يمنعك من إطفائها — عايز الأمان الكامل؟ اقفل.",
    lockLeft: "متبقي", off: "القفل مقفول",
    quoteTitle: "لمة من اليوم",
    dangerTitle: "لو انزلقت فعلًا",
    dangerNote: "الانتكاسة بيانات، مش حكم نهائي. سجّلها بصدق، القفل يفضل في مكانه — وده بالضبط معناه.",
    porn: "أباحية", mast: "عادة سرية", both: "الاتنين",
    relapseDone: "تم التسجيل. سلسلتك بتتصفر، لكن القفل مستمر — ادخل من جديد.",
    until: "حتى",
    activeLockTitle: "القفل الزمني شغال",
    extendTitle: "تمديد القفل فقط",
    extendNote: "تستطيع تمديد القفل إلى مدة أطول، ولا تستطيع تقصيره أبدًا.",
    confirmLbl: "اكتب اقفل للتأكيد",
    createTitle: "إنشاء قفل زمني",
    createWarn: "بمجرد بدء القفل: لا أحد يستطيع إيقافه أو تقصيره. العبث بملفات القفل يضيف 90 يومًا.",
    benefitsTitle: "ما الذي يقال عن التعافي؟",
    benefitsNote: "هذه خلاصات شائعة مما يبلغه الناس، وليست وعودًا طبية. كل جسد يتحرك بوتيرته.",
    notesTitle: "ملاحظات ثابتة",
    ranksTitle: "رتب التعافي",
    ranksNote: "كل رتبة تتفتح عند بلوغ عدد الأيام المطلوب من أيام التعافي (غير الانتكاسات).",
    eventsTitle: "سجل النشاط",
    profileTitle: "الملف الشخصي",
    name: "الاسم", goal: "الهدف", lang: "اللغة",
    saved: "تم الحفظ ✓",
    sysTitle: "النظام",
    hostsLbl: "حجب DNS (/etc/hosts) أثناء القفل",
    autostartLbl: "التشغيل التلقائي مع فتح النظام",
    sysNoteOn: "التشغيل التلقائي: مفعّل", sysNoteOff: "التشغيل التلقائي: مطفأ",
    sysLockNote: "أثناء القفل لا يمكن إطفاء حجب DNS.",
    applied: "تم التطبيق ✓",
    extTitle: "الإكستنشن",
    extConnected: "متصل", extNever: "لم يتصل بعد", extStale: "آخر اتصال",
    extHint: "لتحميل الإكستنشن: chrome://extensions ← Developer mode ← Load unpacked ← واختر مجلد الإكستنشن. في Firefox: about:addons ← Install Add-on From File ← ملف XPI.",
    extCopy: "نسخ مسار الإكستنشن",
    blockTitle: "نطاقات إضافية",
    add: "إضافة",
    changelogTitle: "ما الجديد",
    eventsTypes: {
      service_start: "بدأت الخدمة", service_stop: "وقفت الخدمة",
      lock_created: "قفل جديد", lock_expired: "انتهى القفل",
      tamper: "عبث مؤكد", unlock_refused: "محاولة فك مرفوضة",
      block: "أباحية محظورة", relapse: "انتكاسة",
    },
  },
  en: {
    dashboard: "Dashboard", lock: "Lock", motivation: "Motivation",
    ranks: "Ranks", events: "Activity", settings: "Settings",
    day: "days", hour: "hours", min: "min", sec: "sec",
    streak: "clean days", blocked: "blocked attempts", relapse: "relapses",
    rank: "current rank", longest: "longest streak",
    lockedUntil: "lock ends on", lockActive: "time-lock active",
    noLock: "no time-lock right now",
    lockNote: "Protection is on, but nothing stops you turning it off — want full safety? Lock it.",
    lockLeft: "left", off: "unlock",
    quoteTitle: "Quote of the day",
    dangerTitle: "If you actually slipped",
    dangerNote: "A relapse is data, not a verdict. Log it honestly, and the lock stays — that's the whole point.",
    porn: "porn", mast: "masturbation", both: "both",
    relapseDone: "Logged. Your streak resets, but the lock holds — start again.",
    until: "until",
    activeLockTitle: "Time-lock active",
    extendTitle: "Extend the lock only",
    extendNote: "You can extend the lock to a later date. You can never shorten it.",
    confirmLbl: "Type LOCK to confirm",
    createTitle: "Create a time-lock",
    createWarn: "Once set: nobody can stop or shorten it. Tampering with the files adds 90 days.",
    benefitsTitle: "What people report about recovery",
    benefitsNote: "Common self-reports, not medical promises. Every body moves at its own pace.",
    notesTitle: "Standing notes",
    ranksTitle: "Recovery ranks",
    ranksNote: "Each rank unlocks at its day count of clean days.",
    eventsTitle: "Activity feed",
    profileTitle: "Profile",
    name: "Name", goal: "Goal", lang: "Language",
    saved: "Saved ✓",
    sysTitle: "System",
    hostsLbl: "DNS blocking (/etc/hosts) while locked",
    autostartLbl: "Auto-start with the system",
    sysNoteOn: "Auto-start: on", sysNoteOff: "Auto-start: off",
    sysLockNote: "DNS blocking cannot be turned off while locked.",
    applied: "Applied ✓",
    extTitle: "Extension",
    extConnected: "connected", extNever: "not connected yet", extStale: "last seen",
    extHint: "To install: chrome://extensions → Developer mode → Load unpacked → choose the extension folder. On Firefox: about:addons → Install Add-on From File → the XPI file.",
    extCopy: "Copy extension path",
    blockTitle: "Custom domains",
    add: "Add",
    changelogTitle: "What's new",
    eventsTypes: {
      service_start: "service started", service_stop: "service stopped",
      lock_created: "lock created", lock_expired: "lock expired",
      tamper: "tamper detected", unlock_refused: "unlock refused",
      block: "porn blocked", relapse: "relapse logged",
    },
  },
};

let S = null; // last /api/status payload
let LANG = "ar";
let activeTab = "dashboard";

function t(key) { return (STR[LANG] && STR[LANG][key]) || STR.ar[key] || key; }

/* ------------------------------------------------------------------ */
/* HTTP helpers                                                        */
/* ------------------------------------------------------------------ */
async function apiGet(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
async function apiPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}

/* ------------------------------------------------------------------ */
/* Rendering                                                           */
/* ------------------------------------------------------------------ */
function applyLanguage() {
  document.documentElement.lang = LANG;
  document.documentElement.dir = LANG === "ar" ? "rtl" : "ltr";
  $("nav-dashboard").textContent = "📊 " + t("dashboard");
  $("nav-lock").textContent = "🔒 " + t("lock");
  $("nav-motivation").textContent = "💪 " + t("motivation");
  $("nav-ranks").textContent = "🏆 " + t("ranks");
  $("nav-events").textContent = "📜 " + t("events");
  $("nav-settings").textContent = "⚙️ " + t("settings");
  $("tab-title").textContent = t(activeTab);
  $$("[data-l]").forEach((el) => { el.textContent = t(el.dataset.l); });
  $("s-streak").textContent = t("streak");
  $("s-blocked").textContent = t("blocked");
  $("s-relapse").textContent = t("relapse");
  $("s-rank").textContent = t("rank");
  $("s-blocked-note").textContent = LANG === "ar" ? "من الإكستنشن مباشرة" : "";
  $("quote-title").textContent = t("quoteTitle");
  $("danger-title").textContent = t("dangerTitle");
  $("danger-note").textContent = t("dangerNote");
  $("r-porn").textContent = t("porn");
  $("r-mast").textContent = t("mast");
  $("r-both").textContent = t("both");
  $("lock-active-title").textContent = t("activeLockTitle");
  $("extend-title").textContent = t("extendTitle");
  $("extend-note").textContent = t("extendNote");
  $("extend-days-lbl").textContent = LANG === "ar" ? "مدة جديدة بالأيام" : "New length in days";
  $("confirm-lbl1").textContent = t("confirmLbl");
  $("create-title").textContent = t("createTitle");
  $("create-days-lbl").textContent = LANG === "ar" ? "المدة بالأيام" : "Duration in days";
  $("confirm-lbl2").textContent = t("confirmLbl");
  $("create-warning").textContent = t("createWarn");
  $("mot-quote-title").textContent = t("quoteTitle");
  $("mot-benefits-title").textContent = t("benefitsTitle");
  $("benefits-disclaimer").textContent = t("benefitsNote");
  $("mot-notes-title").textContent = t("notesTitle");
  $("ranks-title").textContent = t("ranksTitle");
  $("ranks-note").textContent = t("ranksNote");
  $("events-title").textContent = t("eventsTitle");
  $("set-profile-title").textContent = t("profileTitle");
  $("set-name-lbl").textContent = t("name");
  $("set-goal-lbl").textContent = t("goal");
  $("set-lang-lbl").textContent = t("lang");
  $("set-sys-title").textContent = t("sysTitle");
  $("set-hosts-lbl").textContent = t("hostsLbl");
  $("set-autostart-lbl").textContent = t("autostartLbl");
  $("set-ext-title").textContent = t("extTitle");
  $("ext-hint").textContent = t("extHint");
  $("ext-copy").textContent = t("extCopy");
  $("set-block-title").textContent = t("blockTitle");
  $("custom-add").textContent = t("add");
  $("set-changelog-title").textContent = t("changelogTitle");
  // wizard labels
  $("w-title").textContent = LANG === "ar" ? "مرحبًا بك في JustGivenUp!" : "Welcome to JustGivenUp!";
  $("w-intro").textContent = LANG === "ar"
    ? "حماية نهائية من الإباحية بقفل زمني لا يمكن إيقافه، ولوحة متابعة لفترة التعافي. خلينا نبدأ."
    : "Definitive porn protection with an unstoppable time-lock and a recovery dashboard. Let's begin.";
  $("w-lang-lbl").textContent = LANG === "ar" ? "اللغة / Language" : "Language / اللغة";
  $("w-name-lbl").textContent = t("name");
  $("w-goal-lbl").textContent = t("goal");
  $("w-days-lbl").textContent = LANG === "ar" ? "مدة القفل الأولية بالأيام (0 = بدون قفل)" : "Initial lock length in days (0 = no lock)";
  $("w-autostart-lbl").textContent = t("autostartLbl");
  $("w-confirm-lbl").textContent = LANG === "ar" ? "اكتب اقفل للتأكيد (لا يمكن التراجع)" : "Type LOCK to confirm (irreversible)";
  $("w-warning").textContent = LANG === "ar"
    ? "بمجرد بدء القفل: لا أحد — لا أنت ولا الإكستنشن ولا الأمر — يستطيع إيقافه أو تقصيره. العبث بالملفات يضيف 90 يومًا."
    : "Once the lock starts: nobody — not you, not the extension, not the CLI — can stop or shorten it. Tampering adds 90 days.";
  $("w-finish").textContent = LANG === "ar" ? "ابدأ الآن" : "Get started";
}

function fmtRemaining(sec) {
  sec = Math.max(0, sec);
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return { d, h, m, s };
}

function setCountdown(prefix, remaining) {
  const { d, h, m, s } = fmtRemaining(remaining);
  $(prefix + "d").textContent = d;
  $(prefix + "h").textContent = String(h).padStart(2, "0");
  $(prefix + "m").textContent = String(m).padStart(2, "0");
  $(prefix + "s").textContent = String(s).padStart(2, "0");
}

function renderStatus() {
  if (!S) return;
  LANG = S.lang || LANG;
  applyLanguage();

  $("brand-ver").textContent = "v" + S.version;

  // stats
  $("v-streak").textContent = S.stats.clean_days;
  $("v-streak-long").textContent = t("longest") + ": " + S.stats.longest_streak_days;
  $("v-blocked").textContent = S.stats.total_blocked;
  $("v-relapse").textContent = S.stats.total_relapses;
  const rk = S.ranks || {};
  $("v-relapse-detail").textContent =
    `porn=${S.stats.relapse_kinds.porn || 0} · mast=${S.stats.relapse_kinds.masturbation || 0}`;
  if (rk.current_rank) {
    $("v-rank").textContent = rk.current_rank.icon + " " + (LANG === "ar" ? rk.current_rank.name_ar : rk.current_rank.name_en);
  } else {
    $("v-rank").textContent = "—";
  }
  if (rk.next_rank) {
    $("v-rank-next").textContent =
      (LANG === "ar" ? "الرتبة التالية: " : "next: ") +
      (LANG === "ar" ? rk.next_rank.name_ar : rk.next_rank.name_en) +
      " · " + rk.next_rank.progress + "%";
  } else {
    $("v-rank-next").textContent = LANG === "ar" ? "وصلت لأعلى رتبة 🏆" : "top rank reached 🏆";
  }

  // quote + motivation
  const mot = S.motivation || {};
  $("dash-quote").textContent = mot.quote || "—";
  $("mot-quote").textContent = mot.quote || "—";
  const bl = $("benefits-list");
  bl.innerHTML = "";
  (mot.benefits || []).forEach((b) => {
    const li = document.createElement("li");
    li.innerHTML = "<b>" + b.days + "</b> — " + escapeHtml(b.text);
    bl.appendChild(li);
  });
  const nl = $("notes-list");
  nl.innerHTML = "";
  (mot.notes || []).forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    nl.appendChild(li);
  });

  // lock visibility
  const locked = S.lock.locked;
  $("lock-active-card").hidden = !locked;
  $("lock-create-card").hidden = locked;
  $("topbar-lock").textContent = locked ? "🔒 " + t("lockActive") : "";
  $("side-lock").textContent = locked
    ? "🔒 " + t("until") + " " + S.lock.expires_label
    : t("noLock");

  // ranks grid
  const grid = $("ranks-grid");
  grid.innerHTML = "";
  (rk.ranks || []).forEach((r) => {
    const div = document.createElement("div");
    div.className = "rank" + (r.unlocked ? " unlocked" : "");
    if (rk.current_rank && r.days === rk.current_rank.days) div.classList.add("current");
    div.innerHTML =
      '<span class="ric">' + r.icon + '</span><b>' +
      escapeHtml(LANG === "ar" ? r.name_ar : r.name_en) +
      '</b><span class="rd">' + r.days + " " + t("day") + "</span>";
    grid.appendChild(div);
  });

  // events
  const el = $("events-list");
  el.innerHTML = "";
  (S.events || []).forEach((ev) => {
    const types = t("eventsTypes") || {};
    const div = document.createElement("div");
    div.className = "event";
    const bad = ["tamper", "unlock_refused", "relapse"].includes(ev.type);
    const dt = new Date(ev.ts * 1000).toLocaleString(LANG === "ar" ? "ar-EG" : "en");
    div.innerHTML =
      "<time>" + dt + '</time><span class="etype' + (bad ? " bad" : "") + '">' +
      escapeHtml(types[ev.type] || ev.type) + '</span><span class="edetail">' +
      escapeHtml(ev.detail && ev.detail.reason ? ev.detail.reason : "") + "</span>";
    el.appendChild(div);
  });

  // settings values
  const set = S.settings || {};
  $("set-name").value = (set.profile && set.profile.name) || "";
  $("set-goal").value = (set.profile && set.profile.goal) || "";
  $("set-lang").value = LANG;
  $("set-hosts").checked = !!set.hosts_block;
  const autostart = set.auto_start || {};
  $("set-autostart").checked = !!autostart.enabled;
  $("set-sys-note").textContent =
    (autostart.enabled ? t("sysNoteOn") : t("sysNoteOff")) +
    " (" + (autostart.mode || "?") + ")" +
    (locked ? " — " + t("sysLockNote") : "");
  // lock tab fields
  $("lock-until").textContent = t("lockedUntil") + " " + S.lock.expires_label;
  $("hero-until").textContent = t("lockedUntil") + " " + S.lock.expires_label;
  $("hero-note").textContent = locked ? t("lockNote") : t("noLock");

  // extension state
  const ext = S.extension || {};
  $("ext-state").innerHTML = ext.connected
    ? "🟢 " + t("extConnected") + (ext.browser ? " · " + escapeHtml(ext.browser) : "") +
      " · v" + escapeHtml(ext.version || "?")
    : ext.ever_seen
      ? "🟡 " + t("extStale") + " " + (ext.age_seconds ?? "?") + "s"
      : "⚪ " + t("extNever");
  $("ext-copy").dataset.path = (S.extension || {}).dir || "";

  // custom domains
  const cl = $("custom-list");
  cl.innerHTML = "";
  (set.custom_domains || []).forEach((d) => {
    const li = document.createElement("li");
    li.textContent = d;
    const x = document.createElement("button");
    x.className = "btn";
    x.style.marginInlineStart = "10px";
    x.textContent = "✕";
    x.addEventListener("click", () => removeCustomDomain(d));
    li.appendChild(x);
    cl.appendChild(li);
  });

  // changelog
  loadChangelog();
  tickCountdowns();
}

/* ------------------------------------------------------------------ */
/* live countdowns (client-side from the server-provided until)        */
/* ------------------------------------------------------------------ */
let countdownTimer = null;
function tickCountdowns() {
  if (countdownTimer) return;
  const step = () => {
    if (!S) return;
    const remaining = S.lock.until - Math.floor(Date.now() / 1000);
    if (S.lock.locked) {
      setCountdown("cd-", remaining);
      setCountdown("ld-", remaining);
      const pct = S.lock.duration_days > 0
        ? Math.max(0, Math.min(100, ((S.lock.duration_days * 86400 - remaining) / (S.lock.duration_days * 86400)) * 100))
        : 0;
      $("hero-progress").style.width = pct.toFixed(1) + "%";
      $("hero-card").hidden = false;
    } else {
      $("hero-card").hidden = true;
    }
  };
  countdownTimer = setInterval(step, 1000);
  step();
}

/* ------------------------------------------------------------------ */
/* data loading                                                        */
/* ------------------------------------------------------------------ */
async function refresh() {
  try {
    S = await apiGet("/api/status");
    renderStatus();
  } catch (e) {
    console.warn("status poll failed", e);
  }
}

let changelogLoaded = false;
async function loadChangelog() {
  if (changelogLoaded) return;
  try {
    const data = await apiGet("/api/changelog");
    const box = $("changelog");
    box.innerHTML = "";
    (data.entries || []).forEach((e) => {
      const div = document.createElement("div");
      div.className = "cl";
      const title = LANG === "ar" ? e.title_ar : e.title_en;
      const changes = LANG === "ar" ? e.changes_ar : e.changes_en;
      div.innerHTML =
        "<b>v" + escapeHtml(e.version) + "</b> — " + escapeHtml(title) +
        ' <span class="cldate">' + escapeHtml(e.date) + "</span>" +
        "<ul>" + (changes || []).map((c) => "<li>" + escapeHtml(c) + "</li>").join("") + "</ul>";
      box.appendChild(div);
    });
    changelogLoaded = true;
  } catch (e) { /* offline */ }
}

/* ------------------------------------------------------------------ */
/* actions                                                             */
/* ------------------------------------------------------------------ */
async function removeCustomDomain(domain) {
  try {
    await apiPost("/api/custom-domains", { action: "remove", domain });
    refresh();
  } catch (e) { /* noop */ }
}

function showError(id, msg) {
  const el = $(id);
  el.textContent = msg;
  el.hidden = !msg;
}

function bindActions() {
  // navigation
  const sidebar = document.querySelector(".sidebar");
  $$(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;
      $$(".nav-item").forEach((b) => b.classList.toggle("on", b === btn));
      $$(".tab-page").forEach((p) => { p.hidden = p.id !== "page-" + activeTab; });
      $("tab-title").textContent = t(activeTab);
      sidebar.classList.remove("open");
    });
  });
  $("hamburger").addEventListener("click", () => sidebar.classList.toggle("open"));

  // presets
  $$(".preset").forEach((b) => b.addEventListener("click", () => {
    $("create-days").value = b.dataset.days;
  }));

  // lock create / extend
  $("create-btn").addEventListener("click", async () => {
    showError("create-error", "");
    try {
      await apiPost("/api/lock", {
        days: parseInt($("create-days").value, 10) || 0,
        confirm: $("create-confirm").value.trim(),
      });
      $("create-confirm").value = "";
      refresh();
    } catch (e) { showError("create-error", e.message); }
  });

  $("extend-btn").addEventListener("click", async () => {
    showError("extend-error", "");
    try {
      await apiPost("/api/lock", {
        days: parseInt($("extend-days").value, 10) || 0,
        confirm: $("extend-confirm").value.trim(),
      });
      $("extend-confirm").value = "";
      refresh();
    } catch (e) { showError("extend-error", e.message); }
  });

  // relapses
  $$("[data-relapse]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm(LANG === "ar" ? "متأكد؟ سيتم تسجيل الانتكاسة وتصفير السلسلة." : "Sure? This logs a relapse and resets the streak.")) return;
    showError("relapse-error", "");
    try {
      await apiPost("/api/relapse", { kind: b.dataset.relapse });
      showError("relapse-error", LANG === "ar" ? t("relapseDone") : t("relapseDone"));
      refresh();
    } catch (e) { showError("relapse-error", e.message); }
  }));

  // profile + language
  $("set-save").addEventListener("click", async () => {
    showError("set-error", "");
    $("set-ok").hidden = true;
    try {
      await apiPost("/api/settings", {
        name: $("set-name").value,
        goal: $("set-goal").value,
        language: $("set-lang").value,
      });
      $("set-ok").textContent = t("saved");
      $("set-ok").hidden = false;
      refresh();
    } catch (e) { showError("set-error", e.message); }
  });

  // system toggles
  $("set-sys-save").addEventListener("click", async () => {
    showError("set-sys-error", "");
    $("set-sys-ok").hidden = true;
    try {
      await apiPost("/api/settings", {
        hosts_block: $("set-hosts").checked,
        autostart: $("set-autostart").checked,
      });
      $("set-sys-ok").textContent = t("applied");
      $("set-sys-ok").hidden = false;
      refresh();
    } catch (e) { showError("set-sys-error", e.message); }
  });

  // extension path copy
  $("ext-copy").addEventListener("click", async () => {
    const p = $("ext-copy").dataset.path;
    try { await navigator.clipboard.writeText(p); } catch (e) { /* noop */ }
    $("ext-copy").textContent = "✓ " + t("extCopy");
    setTimeout(() => { $("ext-copy").textContent = t("extCopy"); }, 1500);
  });

  // custom domains
  $("custom-add").addEventListener("click", async () => {
    showError("custom-error", "");
    try {
      await apiPost("/api/custom-domains", {
        action: "add",
        domain: $("custom-domain").value.trim(),
      });
      $("custom-domain").value = "";
      refresh();
    } catch (e) { showError("custom-error", e.message); }
  });

  /* ---- wizard ---- */
  let wizardLang = "ar";
  $$("#wizard .seg").forEach((b) => b.addEventListener("click", () => {
    wizardLang = b.dataset.lang;
    $$("#wizard .seg").forEach((x) => x.classList.toggle("on", x === b));
    LANG = wizardLang;
    applyLanguage();
  }));
  $("w-finish").addEventListener("click", async () => {
    showError("w-error", "");
    try {
      await apiPost("/api/setup", {
        language: wizardLang,
        name: $("w-name").value,
        goal: $("w-goal").value,
        lock_days: parseInt($("w-days").value, 10) || 0,
        autostart: $("w-autostart").checked,
        confirm: $("w-confirm").value.trim(),
      });
      $("wizard").hidden = true;
      $("app").hidden = false;
      refresh();
    } catch (e) { showError("w-error", e.message); }
  });
}

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ------------------------------------------------------------------ */
/* boot                                                                */
/* ------------------------------------------------------------------ */
document.addEventListener("DOMContentLoaded", async () => {
  bindActions();
  let setup = false;
  try {
    const r = await apiGet("/api/setup-status");
    setup = !!r.setup_complete;
  } catch (e) { /* daemon not up yet */ }
  if (setup) {
    $("wizard").hidden = true;
    $("app").hidden = false;
  } else {
    $("wizard").hidden = false;
    $("app").hidden = true;
  }
  await refresh();
  setInterval(refresh, 30000);
  setInterval(() => { if (!S) refresh(); }, 4000);
});
