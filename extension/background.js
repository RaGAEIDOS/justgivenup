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
const VPN_SCAN_INTERVAL = 5 * 60 * 1000; // ms

const ext = globalThis.chrome || globalThis.browser;

/* IDs known to be VPN/proxy extensions (Chrome + Firefox).  The daemon also
 * writes enterprise policies that block the proxy permission generically;
 * this list is the runtime fallback for browsers where "management" is
 * available (Firefox package / a manually granted permission). */
const VPN_IDS = new Set([
  "omghfjlpggmjjaagoclmmobgdodcjboh", "gkojfkhlekighikafcpjkiklfbnlmeio",
  "eppiocemhmnlbhjplcgkofciiegomcon", "jplgfhpmjnbigmhklmmbgecoobifkmpa",
  "fjoaledfpmneenckfbpdfhkmimnjocfa", "kpiecbcckbofpmkkkdibbllpinceiihk",
  "oofgbpoabipfcfjapgnbbjjaenockbdp", "ffbkglfijbcbgblgflchnbphjdllaogb",
  "fgddmllnllkalaagkghckoinaemmogpe", "ailoabdmgclmfmhdagmlohpjlbpffblp",
  "bihmplhobchoageeokmgbdihknkjbknd", "omdakjcmkglenbhjadbccaookpfjihpa",
  "hnmpcagpplmpfojmgmnngilcnanddlhb", "nlbejmccbhkncgokjcmghpfloaajcffj",
  "ekeoaffihmbjndaoglobgjibjgcmjfpo", "ohjocgmpmlfahafbipehkhbaacoemojp",
  "majdfhpaihoncoakbjgbdhglocklcgno", "akcocjjpkmlniicdeemdceeajlmoabhg",
  "jaoafpkngncfpfggjefnekilbkcpjdgp", "jedieiamjmoflcknjdjhpieklepfglin",
  "gjknjjomckknofjidppipffbpoekiipm",
  "vpn@mozilla.com", "vpn@proton.ch", "browser@tunnelbear.com",
  "nordvpnproxy@nordvpn.com", "firefox-addon@expressvpn.com",
  "browsec@browsec.com", "firefox-webext@zenmate.com", "@windscribeff",
  "@setupvpncom", "client@anonymox.net", "foxyproxy@eric.h.jung",
  "suziwen1@gmail.com", "freevpn@actmobile.com",
]);
const VPN_NAME_RE = /(\bvpn\b|\bproxy\b|proxies|hide\s*my\s*ip|ip\s*hider|hotspot\s*shield|browsec|zenmate|\bhola\b|windscribe|tunnelbear|cyberghost|nordvpn|surfshark|expressvpn|ipvanish|proton\s*vpn|veepn|veezn|planet\s*vpn|urban\s*vpn|touch\s*vpn|setup\s*vpn|setupvpn|1click\s*vpn|1vpn|betternet|dotvpn|hoxx|purevpn|private\s*internet\s*access|mullvad|hide\.me|fastestvpn|anonymox|foxyproxy|switchyomega|adguard\s*vpn|mozilla\s*vpn|tuxler|angelvpn|vpncity|vpn\s*unlimited|free\s*vpn)/i;

let vpnBlockedCount = 0;
let lastVpnRun = 0;

/* Chrome APIs are callback-based in some versions, Firefox returns promises.
 * Try the promise form first, then the callback form. */
async function callApi(fn, ...args) {
  try {
    const ret = fn(...args);
    if (ret && typeof ret.then === "function") return await ret;
    if (ret !== undefined) return ret;
  } catch (e) { /* fall through */ }
  return await new Promise((resolve) => {
    let done = false;
    const finish = (value) => { if (!done) { done = true; resolve(value); } };
    try { fn(...args, finish); } catch (e) { finish(null); }
    setTimeout(() => finish(null), 2500);
  });
}

async function extensionState() {
  let access = null;
  let context = false;
  let windows = 0;
  try { context = !!ext.extension?.inIncognitoContext; } catch (e) { /* ignore */ }
  try {
    if (ext.extension?.isAllowedIncognitoAccess) {
      const value = await callApi((...a) => ext.extension.isAllowedIncognitoAccess(...a));
      if (typeof value === "boolean") access = value;
    }
  } catch (e) { /* ignore */ }
  try {
    if (ext.windows?.getAll) {
      const wins = await callApi((...a) => ext.windows.getAll(...a), { populate: false });
      if (Array.isArray(wins)) {
        windows = wins.filter((w) => w && w.incognito).length;
      }
    }
  } catch (e) { /* ignore */ }
  return { access, context, windows };
}

async function enforceVpnBlock(force = false) {
  const mgmt = ext.management;
  if (!mgmt?.getAll) return vpnBlockedCount;
  const now = Date.now();
  if (!force && now - lastVpnRun < VPN_SCAN_INTERVAL) return vpnBlockedCount;
  lastVpnRun = now;
  let all = [];
  try {
    all = (await callApi((...a) => mgmt.getAll(...a))) || [];
  } catch (e) {
    return vpnBlockedCount;
  }
  if (!Array.isArray(all)) return vpnBlockedCount;
  const selfId = ext.runtime?.id;
  let count = 0;
  for (const info of all) {
    if (!info || info.id === selfId || info.type !== "extension") continue;
    const permissions = [].concat(info.permissions || [], info.optionalPermissions || []);
    const name = String(info.name || "");
    const isVpn = VPN_IDS.has(info.id) || permissions.includes("proxy") || VPN_NAME_RE.test(name);
    if (!isVpn) continue;
    count += 1;
    if (info.enabled) {
      try { await callApi((...a) => mgmt.setEnabled(...a), info.id, false); } catch (e) { /* ignore */ }
    }
  }
  vpnBlockedCount = count;
  await setLocal({ jguVpn: { blocked: count, at: now } });
  return count;
}

async function heartbeat() {
  const incognito = await extensionState();
  const vpnBlocked = await enforceVpnBlock(false);
  const payload = {
    version: manifestVersion(),
    browser: detectBrowser(),
    brand: detectBrand(),
    incognito_context: incognito.context,
    incognito_windows: incognito.windows,
    vpn_blocked: vpnBlocked,
  };
  if (typeof incognito.access === "boolean") {
    payload.incognito_access = incognito.access;
  }
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

function manifestVersion() {
  try {
    return ext.runtime.getManifest().version;
  } catch (e) {
    return "3.1.0";
  }
}

function detectBrand() {
  const ua = navigator.userAgent || "";
  if (/LibreWolf\//i.test(ua)) return "librewolf";
  if (/Waterfox\//i.test(ua)) return "waterfox";
  if (/Floorp\//i.test(ua)) return "floorp";
  if (/Firefox\//i.test(ua)) return "firefox";
  if (/Edg\//i.test(ua)) return "edge";
  if (/OPR\//i.test(ua)) return "opera";
  if (/Vivaldi\//i.test(ua)) return "vivaldi";
  if (/Brave\//i.test(ua) || navigator.brave) return "brave";
  const brands = (navigator.userAgentData && navigator.userAgentData.brands) || [];
  if (brands.some((b) => /Microsoft Edge/i.test(b.brand || ""))) return "edge";
  if (brands.some((b) => /Google Chrome/i.test(b.brand || ""))) return "chrome";
  if (/Chromium\//i.test(ua)) return "chromium";
  if (brands.some((b) => /Chromium/i.test(b.brand || ""))) return "chromium";
  if (/Chrome\//i.test(ua)) return "chrome";
  return "unknown";
}

function detectBrowser() {
  const ua = navigator.userAgent || "";
  let name = "Browser";
  if (/LibreWolf\//i.test(ua)) name = "LibreWolf";
  else if (/Waterfox\//i.test(ua)) name = "Waterfox";
  else if (/Floorp\//i.test(ua)) name = "Floorp";
  else if (/Firefox\//.test(ua)) name = "Firefox";
  else if (/Edg\//.test(ua)) name = "Edge";
  else if (/OPR\//.test(ua)) name = "Opera";
  else if (/Vivaldi\//.test(ua)) name = "Vivaldi";
  else if (/Brave\//.test(ua) || navigator.brave) name = "Brave";
  else if (/Chromium\//.test(ua)) name = "Chromium";
  else if (/Chrome\//.test(ua)) name = "Chrome";
  const m = ua.match(/(Firefox|Edg|OPR|Chrome|Vivaldi|Chromium)\/([\d.]+)/);
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
  enforceVpnBlock(true);
});

if (ext.runtime.onStartup) {
  ext.runtime.onStartup.addListener(() => {
    ensureAlarm();
    heartbeat();
    enforceVpnBlock(true);
  });
}

// An incognito window wakes the incognito instance of the worker: report it
// immediately so the daemon can verify that the extension really runs there.
if (ext.windows?.onCreated) {
  ext.windows.onCreated.addListener(() => heartbeat());
}
if (ext.windows?.onRemoved) {
  ext.windows.onRemoved.addListener(() => heartbeat());
}

// If the user re-enables a blocked VPN extension, put it back down at once.
if (ext.management?.onEnabled) {
  ext.management.onEnabled.addListener(() => enforceVpnBlock(true));
}
if (ext.management?.onInstalled) {
  ext.management.onInstalled.addListener(() => enforceVpnBlock(true));
}

ext.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_TICK) {
    heartbeat();
    enforceVpnBlock();
  }
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
enforceVpnBlock(true);
checkForUpdate();
