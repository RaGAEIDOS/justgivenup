/* Shared translations for the extension pages (popup / blocked / options).
 * The dashboard language is authoritative when reachable; navigator
 * language decides before the first successful contact. */
(function (global) {
  const DICT = {
    ar: {
      dir: "rtl",
      locked: "قفل زمني شغال",
      unlocked: "الحماية شغالة",
      serverDown: "الخدمة المحلية مش شغالة.",
      serverDownNote: "الحجب الثابت لسه شغال حتى لو الخدمة وقفت.",
      day: "يوم", hour: "ساعة", minute: "دقيقة", second: "ثانية",
      until: "حتى",
      lockNote: "القفل شغال — مفيش زرار إيقاف قبل الانتهاء.",
      streak: "أيام نظيفة", blocked: "محظور", relapses: "انتكاسات",
      unlockedNote: "الحماية شغالة. مفيش قفل زمني متفعّل دلوقتي.",
      lockNow: "اقفل الآن", dashboard: "لوحة التحكم",
      stopTitle: "قف.",
      stopBody: "الموقع ده محظور. لو عندك قفل زمني شغال، فكّر في النهاردة اللي اخترتها فيه وأنت صح.",
      stopAdvice: "خد نفس عمقي، ارجع خطوة لورا، وشوف سجل تقدّمك في لوحة التحكم.",
      back: "رجوع", openDashboard: "افتح لوحة التحكم",
      reportSent: "تم تسجيل المحاولة ✓ — تقدّمك بيكسب منها.",
      noLock: "مفيش قفل زمني حاليًا — الحماية شغالة بس محتاجة قفل.",
      pctBlocked: "محاولة محظورة",
    },
    en: {
      dir: "ltr",
      locked: "Time-lock active",
      unlocked: "Protection on",
      serverDown: "The local guardian service is not running.",
      serverDownNote: "Static blocking still works while the service is down.",
      day: "d", hour: "h", minute: "m", second: "s",
      until: "until",
      lockNote: "The lock is active — there is no stop button before it ends.",
      streak: "clean days", blocked: "blocked", relapses: "relapses",
      unlockedNote: "Protection is on. No time-lock is active right now.",
      lockNow: "Lock now", dashboard: "Dashboard",
      stopTitle: "Stop.",
      stopBody: "This site is blocked. If your time-lock is running, remember the day you chose it — you were right.",
      stopAdvice: "Take a breath, step back, and check your progress in the dashboard.",
      back: "Go back", openDashboard: "Open dashboard",
      reportSent: "Attempt logged ✓ — your streak grows from this.",
      noLock: "No time-lock right now — protection is on but unlocked.",
      pctBlocked: "blocked attempt",
    },
  };

  function pick(lang) {
    return DICT[lang] || DICT.ar;
  }

  function detect(langHint) {
    if (langHint && DICT[langHint]) return langHint;
    const nav = (navigator.language || "ar").toLowerCase();
    return nav.startsWith("ar") ? "ar" : "en";
  }

  global.JGU = { DICT, pick, detect };
})(window);
