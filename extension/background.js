/* JustGivenUp! Guardian — background service worker (MV3).
 *
 * Responsibilities:
 *   1. heartbeat to the local daemon (proves the extension is alive;
 *      a missing heartbeat while browsers are open = tamper evidence)
 *   2. mirror the lock state (until / remaining) into storage for the popup
 *   3. sync the user's custom domains as dynamic DNR rules
 *   4. auto-update: check GitHub for newer version and self-reload
 *
 * The static blocking rules ship in rules.json and are always active —
 * this worker only adds the integration with the dashboard.
 */

const API = "http://127.0.0.1:8081";
const ALARM_TICK = "jgu-tick";
const DYNAMIC_RULE_BASE = 900000;
const GITHUB_MANIFEST = "https://raw.githubusercontent.com/RaGAEIDOS/justgivenup/main/extension/manifest.json";
const UPDATE_CHECK_INTERVAL = 30; // minutes

const ext = globalThis.chrome || globalThis.browser;

function manifestVersion() {
  try {
    return ext.runtime.getManifest().version;
  } catch (e) {
    return "3.1.0";
  }
}

function detectBrowser() {
  const ua = navigator.userAgent;
  let name = "Browser";
  if (/Firefox\//.test(ua)) name = "Firefox";
  else if (/Edg\//.test(ua)) name = "Edge";
  else if (/OPR\//.test(ua)) name = "Opera";
  else if (/Chrome\//.test(ua)) name = "Chrome";
  const m = ua.match(/(Firefox|Edg|OPR|Chrome)\/([\d.]+)/);
  return m ? `${name} ${m[2].split(".")[0]}` : name;
}

async function api(path, options) {
  const res = await fetch(API + path, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function setLocal(obj) {
  try {
    await ext.storage.local.set(obj);
  } catch (e) {
    /* storage unavailable (rare) */
  }
}

async function heartbeat() {
  const payload = { version: manifestVersion(), browser: detectBrowser() };
  try {
    const data = await api("/api/heartbeat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    await setLocal({
      jgu: {
        locked: !!data.locked,
        until: data.until || 0,
        serverDown: false,
        penaltyDays: data.penalty_days || 90,
        checkedAt: Date.now(),
      },
    });
    await syncDynamicRules();
  } catch (e) {
    await setLocal({
      jgu: {
        locked: false,
        until: 0,
        serverDown: true,
        checkedAt: Date.now(),
      },
    });
  }
}

/* Custom user domains (small list) as dynamic rules — static rules come
 * from rules.json and stay active even if the daemon is offline. */
async function syncDynamicRules() {
  if (!ext.declarativeNetRequest) return;
  try {
    const data = await api("/api/blocklist?tier=custom");
    const domains = Array.isArray(data.core) ? data.core.slice(0, 4500) : [];
    const existing = await ext.declarativeNetRequest.getDynamicRules();
    const removeRuleIds = existing
      .map((r) => r.ruleId)
      .filter((id) => id >= DYNAMIC_RULE_BASE);
    const addRules = [];
    if (domains.length > 0) {
      addRules.push({
        id: DYNAMIC_RULE_BASE + 1,
        priority: 1,
        action: { type: "block" },
        condition: {
          requestDomains: domains,
          resourceTypes: [
            "main_frame", "sub_frame", "stylesheet", "script", "image",
            "font", "object", "xmlhttprequest", "media", "websocket",
            "ping", "other",
          ],
        },
      });
    }
    await ext.declarativeNetRequest.updateDynamicRules({
      removeRuleIds,
      addRules,
    });
  } catch (e) {
    /* daemon offline or API changed — static rules still protect */
  }
}

async function ensureAlarm() {
  try {
    const alarms = await ext.alarms.getAll();
    if (!alarms.some((a) => a.name === ALARM_TICK)) {
      ext.alarms.create(ALARM_TICK, { periodInMinutes: 1 });
    }
    // separate alarm for update checks
    if (!alarms.some((a) => a.name === "jgu-update")) {
      ext.alarms.create("jgu-update", { periodInMinutes: UPDATE_CHECK_INTERVAL });
    }
  } catch (e) {
    ext.alarms.create(ALARM_TICK, { periodInMinutes: 1 });
    ext.alarms.create("jgu-update", { periodInMinutes: UPDATE_CHECK_INTERVAL });
  }
}

/* ------------------------------------------------------------------ */
/* Auto-update: check GitHub for newer manifest, notify + self-reload */
/* ------------------------------------------------------------------ */
async function checkForUpdate() {
  try {
    const res = await fetch(GITHUB_MANIFEST, { cache: "no-store" });
    if (!res.ok) return;
    const remote = await res.json();
    const remoteVer = String(remote.version || "");
    const localVer = manifestVersion();
    if (!remoteVer || remoteVer === localVer) return;

    // compare versions: remote > local => update available
    const a = localVer.split(".").map(Number);
    const b = remoteVer.split(".").map(Number);
    let newer = false;
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const x = a[i] || 0, y = b[i] || 0;
      if (y > x) { newer = true; break; }
      if (x > y) break;
    }
    if (!newer) return;

    // notify the user
    await setLocal({ jguUpdate: { available: true, version: remoteVer, checkedAt: Date.now() } });
    try {
      ext.notifications?.create?.("jgu-update", {
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "JustGivenUp! Update",
        message: `Version ${remoteVer} is available. Click to update.`,
        priority: 2,
      });
    } catch (e) { /* notifications permission not granted */ }
  } catch (e) { /* offline — skip */ }
}

// listen for notification clicks to trigger reload
ext.notifications?.onClicked?.addListener((id) => {
  if (id === "jgu-update") {
    ext.runtime.reload();
  }
});

ext.runtime.onInstalled.addListener(() => {
  ensureAlarm();
  heartbeat();
});

if (ext.runtime.onStartup) {
  ext.runtime.onStartup.addListener(() => {
    ensureAlarm();
    heartbeat();
  });
}

ext.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_TICK) heartbeat();
  if (alarm.name === "jgu-update") checkForUpdate();
});

/* Also react when the popup asks for a fresh view */
ext.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "jgu-refresh") {
    heartbeat().then(() => sendResponse({ ok: true }));
    return true; // async response
  }
  if (msg && msg.type === "jgu-update-now") {
    checkForUpdate().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});

/* First run inside the worker lifetime */
ensureAlarm();
heartbeat();
checkForUpdate();
