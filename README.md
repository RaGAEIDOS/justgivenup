<p align="center">
  <img src="img/logo-readme.png" width="170" alt="JustGivenUp! Guardian">
</p>

<h1 align="center">JustGivenUp! Guardian</h1>

<p align="center">
  <b>منع قطعي للإباحية في المتصفح، بقفل زمني لا يمكن إيقافه، ولوحة متابعة لرحلة تعافيك.</b><br>
  Definitive in-browser porn blocking with an irreversible time-lock and a
  recovery dashboard.
</p>

<p align="center">
  <a href="https://github.com/RaGAEIDOS/justgivenup/releases/latest"><img src="https://img.shields.io/badge/Download-Latest-blue?style=for-the-badge" alt="Download Latest"></a>
  <a href="https://ragaeidos.website/justgivenup/"><img src="https://img.shields.io/badge/Debian%20apt%20repo-2499ed?style=for-the-badge" alt="apt repo"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/RaGAEIDOS/justgivenup"><img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue?style=for-the-badge" alt="Platform"></a>
</p>

---

## 🇪🇬 العربية

<div align="center"><b>JustGivenUp!</b> — حاجتين في واحد:</div>

1. **إكستنشن للمتصفح (Chrome + Firefox)** — يحجب مباشرةً فوق 12,000 موقع إباحي
   بـ `declarativeNetRequest`، وشاشة تحفيزية عند المحاولة، وتحديث لحظي من الداش بورد.
2. **تطبيق داش بورد وإعدادات** — يتبع أيام تعافيك من الإباحية والعادة السرية
   (سلاسل نظيفة، انتكاسات، رتب، كلمات تحفيزية)، ويمنع أي محتوى إباحي يعرض في
   المتصفح **بشكل قطعي ونهائي**.

### 🔒 القفل الزمني

- تختار المدة (من يوم إلى 3650 يومًا) **من مرة واحدة**.
- بمجرد بدئه لا يستطيع أحد — لا أنت ولا الإكستنشن ولا الأمر — إيقافه أو تقصيره.
- العبث بأي ملف (حذف، تعديل، تغيير النسخة، أو حتى تغيير الساعة) يكتشفه ويضيف **+90 يومًا**.
- طبقات الحماية: إكستنشن + سياسات متصفحات إجبارية (`URLBlocklist`) +
  حجب DNS عبر `/etc/hosts` (150,000+ نطاق) + خدمة systemd + حارس كل 30 ثانية.

### 📥 التثبيت

**Linux (Debian/Ubuntu/Mint) عبر apt:**

```bash
curl -fsSL https://ragaeidos.website/justgivenup/install.sh | sudo sh
```

أو يدويًا:

```bash
echo "deb [trusted=yes] https://ragaeidos.website/justgivenup stable main" \
  | sudo tee /etc/apt/sources.list.d/justgivenup.list
sudo apt update && sudo apt install justgivenup
```

بعد التثبيت الخدمة تعمل **أوتوماتيك مع إقلاع النظام**. افتح
[http://127.0.0.1:8081](http://127.0.0.1:8081) في المتصفح وأكمل المعالج.

**الإكستنشن:** مدمج مسبقًا في الحزمة:
- Chrome/Edge/Brave: `chrome://extensions` ← Developer mode ← **Load unpacked**
  ← `/usr/lib/justgivenup/justgivenup/extension`
- Firefox: `about:addons` ← **Install Add-on From File** ←
  `justgivenup.xpi` بجانب الإكستنشن

**Windows** (Python 3 مطلوب): [`packaging/windows/install.ps1`](packaging/windows/install.ps1)
شغّله كمسؤول مرة واحدة لحاجب DNS.

### لو حابب تنزّل الملفات وتشغّل يدويًا (بدون apt)

```bash
git clone https://github.com/RaGAEIDOS/justgivenup
cd justgivenup/app
python3 -m justgivenup run        # الداش بورد على :8081
python3 -m justgivenup status     # حالة القفل والتعافي
```

### 🗂️ تركيبة المشروع

```
justgivenup/
├── extension/          # إكستنشن Chrome/Firefox (MV3) + rules.json
├── app/                # تطبيق الداش بورد (Python 3، كل المنصات)
│   ├── justgivenup/    #   القفل-المختوم، الخادم، التنفيذ (hosts)، الأحداث
│   └── web/            #   الواجهة الأمامية (عربي/إنجليزي)
├── data/               # قوائم الحظر (150k كامل + 12k أساسي) — مولّدة
├── packaging/deb/      # هيكل حزمة Debian (وحدات systemd + سياسات المتصفحات)
├── packaging/windows/  # مثبّت ويندوز PowerShell
├── scripts/            # build-deb.sh / make-apt-repo.sh / pack_extension.sh
├── site/               # صفحة الهبوط + install.sh (تُنشر على gh-pages)
└── legacy/             # الكود القدام C++ (شاشة ويندوز ONNX) كمرجع
```

### ⚠️ ما لا يستطيع فعله

- جذر الجهاز نفسه لا سبيل إلى منعه: حساب روت/مسؤول يستطيع دائمًا حذف الخدمة أو
  الخروج من النظام. الهدف: منع **الاندفاع** — توقف فيه نفسك وأنت في لحظة ضعف.
- استخراج الصور من النتائج البحثية يحتاج محلِّل صورة (الواجهة تدخل إجبارية SafeSearch
  من Google/Bing/DDG).
- Reddit/Tumblr/Twitter إلخ مواقع عالمية — تلك لا تُحظر بنواة المشروع إلا أوضاعًا
  مثل `nsfw.reddit.com` الموجودة في القائمة.

---

## 🇬🇧 English

### What this is

1. **A browser extension (Chrome + Firefox, MV3)** that blocks 12,000+ adult
   domains in-browser with `declarativeNetRequest`, showing a motivational
   interstitial instead of a blank refusal.
2. **A local dashboard + settings app** that tracks your recovery streak from
   porn/masturbation (clean days, relapses, ranks, motivational quotes) and
   blocks adult content **definitively**.

### 🔒 The time-lock

- You pick the duration (1–3650 days) **once**.
- After that, nobody — not you, not the extension, not the CLI — can stop or
  shorten it before it expires.
- Any tampering (delete, edit, forge the seal, move the clock, remove the
  extension while locked…) is detected and extends the lock by **+90 days**.
- Enforcement stack: extension DNR rules → enterprise browser policies
  (`URLBlocklist`) → system-wide DNS blocking via `/etc/hosts` (150k+
  domains) → systemd service + a 30s watchdog that restarts it if killed.

### 📥 Install (Linux)

```bash
curl -fsSL https://ragaeidos.website/justgivenup/install.sh | sudo sh
```

Then open http://127.0.0.1:8081 and finish the setup wizard. The service
auto-starts at boot. Manual local run:

```bash
git clone https://github.com/RaGAEIDOS/justgivenup
cd justgivenup/app
python3 -m justgivenup run
```

### 🧪 Testing

- `scripts/test_e2e.py` — full E2E: extension heartbeat, interstitial
  redirect, block reporting, sealed lock, `403` unlock-refused, cross-origin
  CSRF refusal, valid expiry cleaning the hosts block, and the **+90-day
  tamper penalty**. Expect 15/15.
- `scripts/test_extension_chrome.py` — loads the extension in Chrome for
  Testing and verifies the DNR redirect to `blocked.html`.
- `scripts/test_policy_chrome.py` — investigates enterprise URLBlocklist
  pattern semantics (see notes there: `--load-policy` is not honored by
  headless Chrome-for-Testing; policies are generated from the documented
  `*://*.domain/*` / `*://domain/*` forms and verified on a real install
  via `chrome://policy`).

### 📅 Roadmap

- [x] v3.0.0 — extension + cross-platform Python daemon + Debian apt repo
- [ ] Signed apt release (`apt-key`/`gpg`) instead of `[trusted=yes]`
- [ ] WebSearch / image-result extra DNR rules
- [ ] Android app (same lock semantics)
- [ ] Application Manager / GUI settings tray

### 📜 License

MIT — see [LICENSE](LICENSE).
