<p align="center">
  <img src="img/logo-readme.png" width="200" alt="JustGivenUp! Shield">
</p>

<h1 align="center">JustGivenUp! - Screen Guardian</h1>

<p align="center">
  <b>A tamper-proof Windows screen guardian with AI-powered NSFW detection, smart filtering, and a cryptographic time-lock that stops you from quitting.</b>
</p>

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/latest"><img src="https://img.shields.io/github/v/release/RaGAEIDOS/justgivenup?style=for-the-badge&logo=windows&label=Download%20Latest&color=blue" alt="Download Latest"></a>
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/tag/v2.2"><img src="https://img.shields.io/badge/Release-v2.2-blueviolet?style=for-the-badge&logo=github" alt="Release v2.2"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/RaGAEIDOS/justgivenup"><img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-blue?style=for-the-badge&logo=windows" alt="Platform"></a>
</p>

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup/issues/new?template=bug_report.md">Report Bug</a>
  ·
  <a href="https://github.com/RaGAEIDOS/justgivenup/issues/new?template=feature_request.md">Request Feature</a>
  ·
  <a href="https://github.com/RaGAEIDOS/justgivenup/discussions">Ask a Question</a>
</p>

---

## Why JustGivenUp?

Every day, millions of people lose hours of their lives to content they regret consuming. Willpower alone is not enough -- when impulse strikes, even the best intentions crumble. JustGivenUp was built for those moments. It is not a content blocker you can dismiss in two clicks. It is a **commitment device**: once you lock it, you cannot stop it until the timer runs out. No registry hack, no task manager trick, no emergency override will save you. The only way out is through.

This is not surveillance. This is **self-respect in code form**. Set your goal, lock yourself in, and come out the other side knowing you kept your word.

---

## Quick Download

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/download/v2.2/JustGivenUp-Setup-2.2-win64.exe">
    <img src="https://img.shields.io/badge/Download-JustGivenUp!%20v2.2%20(41%20MB)-brightgreen?style=for-the-badge&logo=windows&logoColor=white" alt="Download Installer">
  </a>
</p>

<p align="center">
  <code>JustGivenUp-Setup-2.2-win64.exe</code> -- Installer (Windows service + auto-restart, recommended)
</p>

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/download/v2.2/JustGivenUp-v2.2-win64.zip">
    <code>JustGivenUp-v2.2-win64.zip</code> -- Portable ZIP (no install)
  </a>
</p>

### Or install via PowerShell (Admin)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

---

## Features

| Capability | Detail |
|---|---|
| **AI NSFW Detection** | Screen capture via GDI `BitBlt` every 3s, NudeNet `320n.onnx` inference via ONNX Runtime 1.26 |
| **Tab Close (not kill)** | Warns before closing via Ctrl+W instead of killing browser process. Supports 30+ browsers |
| **Warning Dialog** | System-modal YES/NO dialog on blacklist/NSFW hit — "Go Back" closes tab, "Continue" logs relapse. After 3 refusals, ALL browsers are killed |
| **Smart Filtering** | Massive whitelist (200+ edu/dev platforms) skips detection; blacklist (proxy/VPN/porn/streaming/.ru) warns instantly |
| **All-Window Scan** | `EnumWindows` checks every visible window title, not just foreground |
| **Web Dashboard** | Local HTTP server on port 8081 with live stats, profile, ranks, settings |
| **Setup Wizard** | First-run guided setup: language, name, goal, duration, auto-start, profile picture |
| **Rank System** | 13 milestones (7-2550 days clean) with emoji badges, progress tracking, Arabic/English names |
| **Profile Page** | Name, reason, profile picture — track your identity and motivation |
| **Settings Page** | Language toggle (English/العربية), auto-start configuration |
| **Stats Tracking** | Blocked count, relapses, streaks, warning history saved to `%APPDATA%\JustGivenUp\stats.json` |
| **Cryptographic Time-Lock** | SHA-256 sealed via BCrypt in registry; tampering adds 90 days |
| **Exit Prevention** | Stop/Exit grayed when locked, Alt+F4 blocked, `--emergency-stop` refused |
| **Windows Service** | Runs as SYSTEM via `JustGivenUpSvc.exe`; auto-restarts guardian if killed |
| **Auto-Restart** | `RegisterApplicationRestart` restarts on crash/kill from Task Manager |
| **Background Operation** | Console detaches after startup; runs silently in background, no window |
| **Custom Tray Icon** | Shield icon visible in system tray with countdown display |

---

## CLI Commands

```
JustGivenUp.exe                        Run with system tray
JustGivenUp.exe --install               Add to Windows startup
JustGivenUp.exe --remove                Remove from Windows startup
JustGivenUp.exe --lock--DAYS            Lock for N days (3 confirmations required)
JustGivenUp.exe --emergency-stop        Kill all JustGivenUp processes
JustGivenUp.exe --help                  Show help
```

---

## Quick Start

1. **Download** the [latest installer](https://github.com/RaGAEIDOS/justgivenup/releases/latest)
2. Run the installer — it sets up the Windows service and places `JustGivenUp.exe` on your desktop
3. Launch `JustGivenUp.exe` — the **Setup Wizard** opens in your browser at `http://127.0.0.1:8081`
4. Follow the 6-step wizard: choose language → enter your name → select your goal → pick lock duration → enable auto-start → add a profile picture
5. Click **Finish & Start** — the program locks itself for your chosen duration
6. Reboot if desired — the program starts automatically and the service keeps it running

---

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Dashboard** | Live stats (clean days, blocked, relapses, streak, lock status, activity history) |
| **Profile** | Your name, reason for using, profile picture |
| **Ranks** | 13 rank milestones (Bronze → Silver → Gold → Platinum → Diamond → Master → Grandmaster → Legend → Mythic → Immortal → Transcendent → Ascended → Enlightened) with progress bar |
| **Settings** | Language toggle (English/العربية), auto-start with Windows |

---
## How It Works

```
                   +------------------+
                   |  EnumWindows     |
                   |  (all windows)   |
                   +--------+---------+
                            |
                    +-------v--------+
                    |    Filter      |
                    |  (title match) |
                    +-------+--------+
                            |
              +-------------+-------------+
              |                           |
       SKIP / LENIENT              BLACKLIST HIT
              |                           |
      +-------v--------+         +--------v--------+
      |    Capture     |         |    Browser      |
      |  (BitBlt 3s)  |         |    Killer       |
      +-------+-------+         |  (TerminateProc)|
              |                 +-----------------+
      +-------v--------+
      |   Detector     |
      |  (ONNX RT)     |
      +-------+--------+
              |
       +------v------+
       |  NSFW?      |
       +------+------+
              |
    +---------+---------+
    |                   |
   YES                 NO
    |                   |
    v                   v
+-----------+     +-----------+
|  Browser  |     |   Sleep   |
|  Killer   |     |   3 sec   |
+-----------+     +-----------+
```

---

## Configuration

Config is stored at `%APPDATA%\JustGivenUp\config.json`:

| Key | Default | Description |
|---|---|---|
| `interval_seconds` | `3` | Seconds between screen captures |
| `nsfw_threshold` | `0.45` | Detection confidence threshold (0-1) |
| `cooldown_seconds` | `10` | Cooldown after a browser kill |
| `browsers` | `chrome,firefox,msedge,brave,opera` | Target browser executables |
| `whitelist_skip` | `youtube,udemy,coursera,...` | Sites that skip detection entirely |
| `whitelist_lenient` | *(empty)* | Sites with a higher threshold |
| `blacklist_kill` | `proxy,porn,streaming,.ru,...` | Sites that trigger instant browser kill |

---

## Security Model

- **Time-Lock**: Lock duration is sealed with SHA-256 via BCrypt. The registry stores a Unix timestamp and HMAC-SHA256 seal. Tampering with either value is detected and adds 90 days.
- **No DNS blocking**: Browser processes are terminated directly. No network filtering.
- **Windows Service**: `JustGivenUpSvc.exe` runs as SYSTEM, monitors `JustGivenUp.exe`, and restarts it within 1 second if killed.
- **Auto-Restart**: `RegisterApplicationRestart` lets Windows Error Reporting restart the process on crash or task-kill.
- **Watchdog**: `JustGivenUp_watchdog.exe` polls every 8 seconds and restarts the main process if killed.
- **Locked Exit Prevention**: Stop/Exit grayed out, Alt+F4 blocked, `--emergency-stop` refused.
- **Tamper Logging**: All tamper attempts are logged to `%APPDATA%\JustGivenUp\guardian.log`.

---

## Building from Source

### Requirements

- MSYS2 MinGW-w64 GCC 16.1.0+
- CMake 4.3.3+
- ONNX Runtime 1.26 (MSYS2 `ucrt64`)

### Build

```bash
mkdir build && cd build
cmake .. -G "Ninja"
ninja
```

The `build/` directory will contain both executables and all required DLLs.

---

## Roadmap

- [ ] Per-application whitelist/blacklist (allow games, block browsers during work hours)
- [ ] Schedule-based locking (lock every night 10pm-6am)
- [ ] Remote monitoring via encrypted telemetry
- [ ] QR code unlock with remote approval
- [ ] Linux support via X11/Wayland screen capture
- [ ] GUI configuration editor

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

<p align="center">
  <b>JustGivenUp!</b> -- Because the version of you that sets the lock knows better than the version of you that wants to break it.
</p>

---

## 🇸🇦 النسخة العربية

**JustGivenUp!** — برنامج حماية شاشة لنظام ويندوز، يعمل بالذكاء الاصطناعي لكشف المحتوى غير المناسب، مع فلتر ذكي وقفل زمني مشفر يمنعك من إيقافه.

### لماذا JustGivenUp!؟

كل يوم، يخسر ملايين الأشخاص ساعات من أعمارهم أمام محتوى يندمون عليه. قوة الإرادة وحدها لا تكفي — فعندما تأتي اللحظة، تنهار أحسن النوايا. هذا البرنامج صُمم لتلك اللحظات. إنه ليس مجرد مانع محتوى يمكنك إغلاقه بنقرتين. إنه **جهاز التزام**: بمجرد أن تقفله، لا يمكنك إيقافه حتى ينتهي المؤقت. لا اختراق ريجستري، ولا مدير مهام، ولا طوارئ ستنقذك. الطريق الوحيد للخروج هو الانتظار حتى النهاية.

هذه ليست مراقبة. هذا **احترام للذات في صورة كود**. حدد هدفك، اقفل نفسك، واخرج من الجانب الآخر وأنت تعرف أنك وفيت بوعدك.

### المميزات

| الميزة | الشرح |
|---|---|
| **كشف NSFW بالذكاء الاصطناعي** | تصوير الشاشة كل 3 ثوانٍ عبر GDI `BitBlt`، تحليل بنموذج NudeNet `320n.onnx` عبر ONNX Runtime |
| **إغلاق التبويبات بدلاً من قتل المتصفح** | يحاكي الضغط على Ctrl+W لإغلاق التبويب المخالف مع نافذة تحذير. بعد 3 رفضات متتالية، تُقتل جميع المتصفحات |
| **فلتر ذكي** | قائمة بيضاء ضخمة (200+ موقع تعليمي) تتجاوز الفحص؛ قائمة سوداء (بروكسي، VPN، إباحي، رقص، .ru) تغلق التبويب فوراً |
| **لوحة تحكم ويب** | dashboard محلي على `http://127.0.0.1:8081` يعرض إحصائيات حية، الملف الشخصي، الرتب، الإعدادات |
| **معالج الإعداد الأولي** | 6 خطوات: اختيار اللغة، الاسم، الهدف، المدة، التشغيل مع ويندوز، الصورة الشخصية |
| **نظام الرتب** | 13 رتبة (7-2550 يوم نظيف) مع شارات إيموجي، تتبع التقدم، أسماء عربية/إنجليزية |
| **صفحة الملف الشخصي** | الاسم، سبب الاستخدام، صورة شخصية |
| **الإعدادات** | تبديل اللغة (عربي/إنجليزي)، تفعيل التشغيل مع ويندوز |
| **القفل الزمني المشفر** | SHA-256 عبر BCrypt في الريجستري؛ العبث يضيف 90 يوماً إضافية |
| **منع الخروج** | زر الإيقاف/الخروج معطل عند القفل، Alt+F4 محظور، `--emergency-stop` مرفوض |
| **تشغيل في الخلفية** | بعد بدء التشغيل، يتم فصل الكونسول وتشغيل البرنامج في الخلفية بدون نافذة |
| **دعم جميع المتصفحات** | Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Tor, Yandex, Arc, وغيرها (30+ متصفح) |

### أوامر سطر الأوامر

```
JustGivenUp.exe                             تشغيل عادي مع علبة النظام
JustGivenUp.exe --install                    إضافة إلى بدء تشغيل ويندوز
JustGivenUp.exe --remove                     إزالة من بدء تشغيل ويندوز
JustGivenUp.exe --lock--عددالأيام            قفل لعدد N من الأيام (يطلب تأكيد 3 مرات)
JustGivenUp.exe --emergency-stop             قتل جميع عمليات JustGivenUp
JustGivenUp.exe --help                       عرض المساعدة
```

### بدء سريع

1. **حمّل** [المثبّت الرسمي](https://github.com/RaGAEIDOS/justgivenup/releases/latest)
2. شغّل المثبّت — يثبّت الخدمة وينسخ الملفات على سطح المكتب
3. شغّل `JustGivenUp.exe` — **معالج الإعداد** يفتح في المتصفح على `http://127.0.0.1:8081`
4. اتبع الخطوات الـ 6: اختر اللغة → أدخل اسمك → حدد هدفك → اختر المدة → فعّل التشغيل مع ويندوز → أضف صورة
5. اضغط **إنهاء والبدء** — البرنامج يقفل نفسه للمدة التي اخترتها

### لوحة التحكم (Dashboard)

عند تشغيل البرنامج، افتح المتصفح على `http://127.0.0.1:8081` لترى:
- **الصفحة الرئيسية**: إحصائيات حية (أيام نظيفة، محظورات، انتكاسات، السلسلة)
- **الملف الشخصي**: اسمك، سبب الاستخدام، صورتك
- **الرتب**: 13 رتبة (برونز → فضة → ذهب → بلاتين → ماس → خبير → أستاذ كبير → أسطورة → أسطوري → خالد → متعالٍ → صاعد → مستنير)
- **الإعدادات**: تبديل اللغة (عربي/إنجليزي)، تشغيل مع ويندوز

### كيف يعمل

1. **مسح جميع النوافذ**: يفحص `EnumWindows` عناوين جميع النوافذ المفتوحة
2. **الفلتر**: إذا كان الموقع في القائمة البيضاء → يتجاوز الفحص؛ في القائمة السوداء → تحذير فوري
3. **الكشف بالذكاء الاصطناعي**: إذا كان الموقع غير معروف، يصور الشاشة ويحللها بنموذج NudeNet
4. **الإجراء**: عند اكتشاف محتوى غير مناسب أو موقع محظور → نافذة تحذير ("عد إلى الخلف" أو "متابعة")
   - إذا ضغطت "عد إلى الخلف" ← يغلق التبويب (Ctrl+W)
   - إذا ضغطت "متابعة" ← يسجل انتكاسة ويستمر
   - بعد 3 رفضات متتالية (اختيار "متابعة") ← تُقتل جميع المتصفحات

### نموذج الأمان

- **القفل الزمني**: مدة القفل مشفرة بـ SHA-256 عبر BCrypt. الريجستري يخزن طابع زمني مع HMAC-SHA256. العبث بأي قيمة يُكتشف ويضيف 90 يوماً
- **بدون حجب DNS**: لا يتم إنهاء المتصفحات مباشرة، بل تغلق التبويبات المخالفة فقط
- **الحارس**: `JustGivenUp_watchdog.exe` يفحص كل 8 ثوانٍ ويعيد تشغيل البرنامج إذا تم إيقافه
- **تسجيل الاختراق**: كل محاولات العبث تُسجل في `%APPDATA%\JustGivenUp\guardian.log`

### بناء من المصدر

**المتطلبات**: MSYS2 MinGW-w64 GCC 16.1.0+, CMake 4.3.3+, ONNX Runtime 1.26

```bash
mkdir build && cd build
cmake .. -G "Ninja"
ninja
```

### الترخيص

موزع تحت رخصة MIT. انظر ملف `LICENSE` للمزيد.

### التحميل

<p align="center" dir="rtl">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/download/v2.2/JustGivenUp-Setup-2.2-win64.exe">
    <img src="https://img.shields.io/badge/تحميل-مثبت%20v2.2%20(41%20MB)-brightgreen?style=for-the-badge&logo=windows" alt="تحميل المثبت">
  </a>
</p>

<p align="center" dir="rtl">
  <code>JustGivenUp-Setup-2.2-win64.exe</code> — المثبت الرسمي (يُثبّت الخدمة وإعادة التشغيل التلقائي)
</p>

<p align="center" dir="rtl">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/latest">
    أو حمّل آخر إصدار
  </a>
</p>

<p align="center" dir="rtl">
  <b>JustGivenUp!</b> — لأن نسخة نفسك التي تضع القفل أعقل من النسخة التي تريد كسره.
</p>

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup">
    <img src="https://img.shields.io/badge/GitHub-RaGAEIDOS%2Fjustgivenup-181717?style=for-the-badge&logo=github" alt="GitHub">
  </a>
</p>

---

## 🇵🇸 Palestine

<p align="center">
  <b>Free Palestine.</b><br>
  This project stands in solidarity with the Palestinian people and their struggle for freedom, justice, and self-determination.
</p>

<p align="center" dir="rtl">
  <b>فلسطين حرة.</b><br>
  هذا المشروع يقف تضامناً مع الشعب الفلسطيني في نضاله من أجل الحرية والعدالة وتقرير المصير.
</p>
