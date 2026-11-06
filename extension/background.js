/* JustGivenUp! Guardian — background service worker (MV3).
 *
 * Responsibilities:
 *   1. heartbeat to the local daemon (proves the extension is alive;
 *      a missing heartbeat while browsers are open = tamper evidence)
 *   2. mirror the lock state (until / remaining) into storage for the popup
 *   3. sync the user's custom domains as dynamic DNR rules
 *
 * The static blocking rules ship in rules.json and are always active —
 * this worker only adds the integration with the dashboard.
 */

const API = "http://127.0.0.1:8081";
const ALARM_TICK = "jgu-tick";
const DYNAMIC_RULE_BASE = 900000;

const ext = globalThis.chrome || globalThis.browser;

function manifestVersion() {
  try {
    return ext.runtime.getManifest().version;
  } catch (e) {
    return "3.0.0";
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
  } catch (e) {
    ext.alarms.create(ALARM_TICK, { periodInMinutes: 1 });
  }
}

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
});

/* Also react when the popup asks for a fresh view */
ext.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "jgu-refresh") {
    heartbeat().then(() => sendResponse({ ok: true }));
    return true; // async response
  }
  return false;
});

/* First run inside the worker lifetime */
ensureAlarm();
heartbeat();
