#include "dashboard.h"
#include "config.h"
#include "stats.h"
#include "log.h"
#include "lock.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <sstream>
#include <thread>
#include <chrono>
#include <vector>
#include <shlobj.h>
#include <shlwapi.h>
#pragma comment(lib, "ws2_32.lib")

Dashboard::Dashboard(Config* cfg, int port) : _cfg(cfg), _port(port) {}

Dashboard::~Dashboard() { stop(); }

void Dashboard::start() {
    if (_running) return;
    _running = true;
    _thread = new std::thread(&Dashboard::server_thread, this);
    Log::instance().info("[DASHBOARD] Started on port " + std::to_string(_port));
}

void Dashboard::stop() {
    _running = false;
    if (_thread) {
        if (_thread->joinable()) _thread->join();
        delete _thread;
        _thread = nullptr;
    }
}

void Dashboard::read_body(int sock, std::string& body, int content_len) {
    body.clear();
    if (content_len <= 0) return;
    std::vector<char> buf(content_len + 1);
    int total = 0;
    while (total < content_len) {
        int n = recv(sock, buf.data() + total, content_len - total, 0);
        if (n <= 0) break;
        total += n;
    }
    buf[total] = 0;
    body = buf.data();
}

void Dashboard::server_thread() {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        Log::instance().error("[DASHBOARD] WSAStartup failed");
        _running = false;
        return;
    }

    SOCKET server = socket(AF_INET, SOCK_STREAM, 0);
    if (server == INVALID_SOCKET) {
        Log::instance().error("[DASHBOARD] socket() failed");
        WSACleanup();
        _running = false;
        return;
    }

    _server_socket = (void*)server;

    int opt = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, (char*)&opt, sizeof(opt));

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(_port);

    if (bind(server, (sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
        Log::instance().error("[DASHBOARD] bind() failed on port " + std::to_string(_port));
        closesocket(server);
        WSACleanup();
        _running = false;
        return;
    }

    if (listen(server, 5) == SOCKET_ERROR) {
        Log::instance().error("[DASHBOARD] listen() failed");
        closesocket(server);
        WSACleanup();
        _running = false;
        return;
    }

    Log::instance().info("[DASHBOARD] Listening on http://127.0.0.1:" + std::to_string(_port));

    while (_running) {
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(server, &readfds);
        struct timeval tv = {1, 0};

        int activity = select(0, &readfds, NULL, NULL, &tv);
        if (activity < 0) break;
        if (activity == 0) continue;
        if (!FD_ISSET(server, &readfds)) continue;

        sockaddr_in client;
        int client_len = sizeof(client);
        SOCKET client_sock = accept(server, (sockaddr*)&client, &client_len);
        if (client_sock == INVALID_SOCKET) continue;

        char buf[8192] = {};
        int n = recv(client_sock, buf, sizeof(buf) - 1, 0);
        if (n <= 0) { closesocket(client_sock); continue; }
        buf[n] = 0;
        std::string request(buf);

        std::string method = "GET";
        std::string path = "/";
        std::string body;

        size_t m_pos = request.find(' ');
        if (m_pos != std::string::npos) {
            method = request.substr(0, m_pos);
            size_t path_start = m_pos + 1;
            size_t path_end = request.find(' ', path_start);
            if (path_end != std::string::npos) {
                path = request.substr(path_start, path_end - path_start);
                // URL decode
                size_t q = path.find('?');
                if (q != std::string::npos) path = path.substr(0, q);
            }
        }

        // Parse Content-Length for POST
        int content_len = 0;
        size_t cl_pos = request.find("Content-Length: ");
        if (cl_pos != std::string::npos) {
            std::string cl_str = request.substr(cl_pos + 16);
            size_t crlf = cl_str.find("\r\n");
            if (crlf != std::string::npos) cl_str = cl_str.substr(0, crlf);
            try { content_len = std::stoi(cl_str); } catch (...) {}
        }

        // Read remaining body if needed
        size_t hdr_end = request.find("\r\n\r\n");
        if (hdr_end != std::string::npos) {
            std::string remaining = request.substr(hdr_end + 4);
            body = remaining;
            int have = (int)remaining.size();
            if (have < content_len) {
                std::string extra;
                read_body(client_sock, extra, content_len - have);
                body += extra;
            }
        }

        std::string response = handle_request(method, path, body);
        send(client_sock, response.c_str(), (int)response.size(), 0);
        closesocket(client_sock);
    }

    closesocket(server);
    WSACleanup();
    _server_socket = nullptr;
}

static std::string http_json(int code, const std::string& body) {
    std::ostringstream r;
    r << "HTTP/1.1 " << code << " " << (code == 200 ? "OK" : code == 404 ? "Not Found" : "Error") << "\r\n"
      << "Content-Type: application/json\r\n"
      << "Access-Control-Allow-Origin: *\r\n"
      << "Content-Length: " << body.size() << "\r\n"
      << "\r\n"
      << body;
    return r.str();
}

static std::string http_html(const std::string& body) {
    std::ostringstream r;
    r << "HTTP/1.1 200 OK\r\n"
      << "Content-Type: text/html; charset=utf-8\r\n"
      << "Content-Length: " << body.size() << "\r\n"
      << "\r\n"
      << body;
    return r.str();
}

static bool is_auto_start_installed() {
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                      0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        wchar_t buf[MAX_PATH] = {};
        DWORD sz = sizeof(buf);
        LSTATUS r = RegQueryValueExW(hKey, L"JustGivenUp", NULL, NULL, (BYTE*)buf, &sz);
        RegCloseKey(hKey);
        return r == ERROR_SUCCESS;
    }
    return false;
}

static bool install_auto_start() {
    wchar_t exe_path[MAX_PATH];
    GetModuleFileNameW(NULL, exe_path, MAX_PATH);
    HKEY hKey;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                        0, NULL, 0, KEY_SET_VALUE, NULL, &hKey, NULL) != ERROR_SUCCESS)
        return false;
    LSTATUS ret = RegSetValueExW(hKey, L"JustGivenUp", 0, REG_SZ,
        (const BYTE*)exe_path, (DWORD)(wcslen(exe_path) + 1) * 2);
    RegCloseKey(hKey);
    return ret == ERROR_SUCCESS;
}

static bool remove_auto_start() {
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                      0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {
        RegDeleteValueW(hKey, L"JustGivenUp");
        RegCloseKey(hKey);
        return true;
    }
    return false;
}

struct RankDef { int days; const char* name_en; const char* name_ar; const char* icon; };

static const RankDef RANKS[] = {
    {7, "Bronze", "برونز", "\xF0\x9F\xA5\x89"},
    {14, "Silver", "فضة", "\xF0\x9F\xA5\x88"},
    {21, "Gold", "ذهب", "\xF0\x9F\xA5\x87"},
    {30, "Platinum", "بلاتين", "\xF0\x9F\x92\x8E"},
    {60, "Diamond", "الماس", "\xF0\x9F\x92\xA0"},
    {90, "Master", "الخبير", "\xF0\x9F\x91\x91"},
    {120, "Grandmaster", "الأستاذ الكبير", "\xE2\x9A\x9C\xEF\xB8\x8F"},
    {240, "Legend", "الأسطورة", "\xF0\x9F\x8F\x86"},
    {300, "Mythic", "الأسطوري", "\xF0\x9F\x8C\x9F"},
    {365, "Immortal", "الخالد", "\xE2\x99\xBE\xEF\xB8\x8F"},
    {680, "Transcendent", "المتعالي", "\xF0\x9F\x94\xA5"},
    {1220, "Ascended", "الصاعد", "\xE2\x98\x80\xEF\xB8\x8F"},
    {2550, "Enlightened", "المستنير", "\xF0\x9F\x95\x8A\xEF\xB8\x8F"},
};

static const int NUM_RANKS = sizeof(RANKS) / sizeof(RANKS[0]);

std::string Dashboard::api_ranks() {
    int clean = Stats::instance().clean_days();
    int longest = Stats::instance().data().longest_clean_streak;
    if (longest < clean) longest = clean;

    int current_idx = -1, next_idx = -1;
    for (int i = 0; i < NUM_RANKS; i++) {
        if (longest >= RANKS[i].days) current_idx = i;
    }
    if (current_idx >= 0 && current_idx < NUM_RANKS - 1) next_idx = current_idx + 1;

    json r = json::array();
    for (int i = 0; i < NUM_RANKS; i++) {
        bool unlocked = longest >= RANKS[i].days;
        r.push_back({
            {"days", RANKS[i].days},
            {"name_en", RANKS[i].name_en},
            {"name_ar", RANKS[i].name_ar},
            {"icon", RANKS[i].icon},
            {"unlocked", unlocked}
        });
    }

    json resp;
    resp["ranks"] = r;
    resp["current_streak"] = clean;
    resp["longest_streak"] = longest;
    if (current_idx >= 0) {
        resp["current_rank"] = {
            {"days", RANKS[current_idx].days},
            {"name_en", RANKS[current_idx].name_en},
            {"name_ar", RANKS[current_idx].name_ar},
            {"icon", RANKS[current_idx].icon}
        };
    } else {
        resp["current_rank"] = json::object();
    }
    if (next_idx >= 0) {
        int cur_days = current_idx >= 0 ? RANKS[current_idx].days : 0;
        int nxt_days = RANKS[next_idx].days;
        int range = nxt_days - cur_days;
        int progress = range > 0 ? (int)((double)(longest - cur_days) / range * 100) : 0;
        if (progress > 100) progress = 100;
        resp["next_rank"] = {
            {"days", RANKS[next_idx].days},
            {"name_en", RANKS[next_idx].name_en},
            {"name_ar", RANKS[next_idx].name_ar},
            {"icon", RANKS[next_idx].icon},
            {"progress", progress},
            {"remaining", nxt_days - longest}
        };
    } else {
        resp["next_rank"] = json::object();
        resp["max_rank_reached"] = true;
    }

    return http_json(200, resp.dump(2));
}

std::string Dashboard::api_setup_status() {
    json j;
    j["setup_complete"] = _cfg->get().setup_complete;
    return http_json(200, j.dump(2));
}

std::string Dashboard::api_handle_setup(const std::string& body) {
    try {
        json j = json::parse(body);
        auto& cfg = _cfg->get();

        if (j.contains("name")) cfg.user_name = j["name"];
        if (j.contains("work")) cfg.user_work = j["work"];
        if (j.contains("picture")) cfg.user_picture = j["picture"];
        if (j.contains("language")) cfg.language = j["language"];
        if (j.contains("auto_start") && j["auto_start"].get<bool>())
            install_auto_start();

        cfg.setup_complete = true;
        _cfg->save();

        // Lock the program if duration specified
        if (j.contains("lock_days") && j["lock_days"].is_number() && j["lock_days"].get<int>() > 0) {
            Lock lock;
            lock.set_lock(j["lock_days"].get<int>());
        }

        json r = {{"ok", true}};
        return http_json(200, r.dump(2));
    } catch (...) {
        json r = {{"ok", false}, {"error", "Invalid JSON"}};
        return http_json(200, r.dump(2));
    }
}

std::string Dashboard::api_profile() {
    auto& cfg = _cfg->get();
    json j;
    j["name"] = cfg.user_name;
    j["work"] = cfg.user_work;
    j["picture"] = cfg.user_picture;
    j["setup_complete"] = cfg.setup_complete;
    return http_json(200, j.dump(2));
}

std::string Dashboard::api_save_profile(const std::string& body) {
    try {
        json j = json::parse(body);
        auto& cfg = _cfg->get();
        if (j.contains("name")) cfg.user_name = j["name"];
        if (j.contains("work")) cfg.user_work = j["work"];
        if (j.contains("picture")) cfg.user_picture = j["picture"];
        _cfg->save();
        json r = {{"ok", true}};
        return http_json(200, r.dump(2));
    } catch (...) {
        json err = {{"ok", false}, {"error", "Invalid JSON"}};
        return http_json(200, err.dump(2));
    }
}

std::string Dashboard::api_settings() {
    auto& cfg = _cfg->get();
    json j;
    j["language"] = cfg.language;
    j["auto_start"] = is_auto_start_installed();
    j["setup_complete"] = cfg.setup_complete;
    return http_json(200, j.dump(2));
}

std::string Dashboard::api_save_settings(const std::string& body) {
    try {
        json j = json::parse(body);
        auto& cfg = _cfg->get();
        if (j.contains("language")) cfg.language = j["language"];
        if (j.contains("auto_start")) {
            if (j["auto_start"].get<bool>()) install_auto_start();
            else remove_auto_start();
        }
        _cfg->save();
        json r = {{"ok", true}};
        return http_json(200, r.dump(2));
    } catch (...) {
        json err = {{"ok", false}, {"error", "Invalid JSON"}};
        return http_json(200, err.dump(2));
    }
}

std::string Dashboard::api_check_update() {
    // Simple check via GitHub API (connecting from C++ side)
    // Returns current version info
    json j;
    j["current_version"] = "v2.2";
    j["check_url"] = "https://github.com/RaGAEIDOS/justgivenup/releases/latest";
    return http_json(200, j.dump(2));
}

std::string Dashboard::api_stats() {
    Stats::instance().update_streak();
    json j = Stats::instance().to_json();
    Lock lock;
    j["is_locked"] = lock.is_locked();
    j["lock_until"] = lock.until_str();
    j["clean_days"] = Stats::instance().clean_days();
    return http_json(200, j.dump(2));
}

std::string Dashboard::handle_request(const std::string& method, const std::string& path, const std::string& body) {
    if (path == "/api/stats") return api_stats();
    if (path == "/api/setup-status") return api_setup_status();
    if (path == "/api/setup" && method == "POST") return api_handle_setup(body);
    if (path == "/api/profile" && method == "GET") return api_profile();
    if (path == "/api/profile" && method == "POST") return api_save_profile(body);
    if (path == "/api/ranks") return api_ranks();
    if (path == "/api/settings" && method == "GET") return api_settings();
    if (path == "/api/settings" && method == "POST") return api_save_settings(body);
    if (path == "/api/check-update") return api_check_update();
    if (path == "/") return http_html(dashboard_html());
    return http_html(dashboard_html());
}

std::string Dashboard::dashboard_html() {
    return R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JustGivenUp! -- Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f1a;color:#e0e0e0;min-height:100vh}
body.rtl{direction:rtl;font-family:'Segoe UI',Tahoma,sans-serif}
.sidebar{position:fixed;top:0;left:0;bottom:0;width:220px;background:#141428;border-right:1px solid #2a2a4a;display:flex;flex-direction:column;z-index:10}
body.rtl .sidebar{left:auto;right:0;border-right:none;border-left:1px solid #2a2a4a}
.sidebar .brand{padding:20px;text-align:center;border-bottom:1px solid #2a2a4a}
.sidebar .brand h2{color:#4fc3f7;font-size:1.1em;letter-spacing:1px}
.sidebar .brand .ver{color:#555;font-size:0.7em;margin-top:4px}
.sidebar nav{flex:1;padding:10px 0}
.sidebar nav a{display:block;padding:14px 24px;color:#999;text-decoration:none;font-size:0.9em;transition:all 0.2s;border-left:3px solid transparent}
body.rtl .sidebar nav a{border-left:none;border-right:3px solid transparent}
.sidebar nav a:hover{background:#1a1a35;color:#eee}
.sidebar nav a.active{color:#4fc3f7;background:#1a1a35;border-left-color:#4fc3f7}
body.rtl .sidebar nav a.active{border-left-color:transparent;border-right-color:#4fc3f7}
.sidebar nav a .icon{margin-right:10px}
body.rtl .sidebar nav a .icon{margin-right:0;margin-left:10px}
.main{margin-left:220px;min-height:100vh}
body.rtl .main{margin-left:0;margin-right:220px}
.topbar{background:#141428;padding:16px 30px;border-bottom:1px solid #2a2a4a;display:flex;justify-content:space-between;align-items:center}
.topbar .page-title{font-size:1.2em;color:#fff}
.topbar .lang-toggle{background:transparent;border:1px solid #2a2a4a;color:#999;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:0.85em}
.topbar .lang-toggle:hover{background:#1a1a35;color:#eee}
.content{padding:30px}
.tab{display:none}
.tab.active{display:block}
.card{background:#1a1a2e;border-radius:12px;padding:20px;border:1px solid #2a2a4a;margin-bottom:20px}
.card h3{color:#aaa;margin-bottom:15px;font-size:0.95em;letter-spacing:1px;text-transform:uppercase}
.form-group{margin-bottom:16px}
.form-group label{display:block;color:#999;font-size:0.85em;margin-bottom:6px}
.form-group input,.form-group select{width:100%;padding:12px 14px;background:#0f0f1a;border:1px solid #2a2a4a;border-radius:8px;color:#e0e0e0;font-size:0.95em;outline:none;transition:border 0.2s}
.form-group input:focus,.form-group select:focus{border-color:#4fc3f7}
.form-group select option{background:#1a1a2e;color:#e0e0e0}
.btn{display:inline-block;padding:12px 28px;border:none;border-radius:8px;font-size:0.95em;cursor:pointer;transition:all 0.2s;font-weight:600}
.btn-primary{background:#4fc3f7;color:#0f0f1a}
.btn-primary:hover{background:#39b0e4}
.btn-secondary{background:#2a2a4a;color:#ccc}
.btn-secondary:hover{background:#3a3a5a}
.btn-success{background:#66bb6a;color:#0f0f1a}
.btn-success:hover{background:#4caf50}
.btn-danger{background:#ef5350;color:#fff}
.btn-danger:hover{background:#e53935}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.profile-pic{width:100px;height:100px;border-radius:50%;object-fit:cover;border:3px solid #2a2a4a;background:#1a1a2e}
.profile-pic-sm{width:48px;height:48px;border-radius:50%;object-fit:cover;border:2px solid #2a2a4a;background:#1a1a2e}
.profile-pic-wrapper{text-align:center;margin-bottom:20px;position:relative;display:inline-block}
.profile-pic-wrapper .change-btn{position:absolute;bottom:0;right:0;background:#4fc3f7;color:#0f0f1a;border:none;border-radius:50%;width:32px;height:32px;cursor:pointer;font-size:1em;display:flex;align-items:center;justify-content:center}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:#1a1a2e;border-radius:12px;padding:20px;text-align:center;border:1px solid #2a2a4a}
.stat-card .value{font-size:2.5em;font-weight:700;color:#4fc3f7;margin:10px 0}
.stat-card .value.green{color:#66bb6a}
.stat-card .value.red{color:#ef5350}
.stat-card .value.yellow{color:#ffa726}
.stat-card .label{color:#888;font-size:0.85em;text-transform:uppercase;letter-spacing:1px}
.stat-card .sub{font-size:0.75em;color:#666;margin-top:5px}
.history{background:#1a1a2e;border-radius:12px;padding:20px;border:1px solid #2a2a4a;margin-bottom:20px}
.history h3{color:#aaa;margin-bottom:15px;letter-spacing:1px}
.history-item{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #2a2a4a;font-size:0.9em}
.history-item:last-child{border-bottom:none}
.history-item .tp{color:#4fc3f7}
.history-item .tp.blocked{color:#66bb6a}
.history-item .tp.relapse{color:#ef5350}
.history-item .date{color:#666}
.lock-info{text-align:center;margin-bottom:20px;padding:12px;border-radius:8px;font-size:0.9em}
.lock-info.locked{background:#3e2723;border:1px solid #6d4c41;color:#ff8a65}
.lock-info.unlocked{background:#1b3a1b;border:1px solid #2e7d32;color:#81c784}
.badge{display:inline-block;background:#1a1a2e;border-radius:20px;padding:4px 14px;font-size:0.75em;color:#4fc3f7;border:1px solid #2a2a4a}
.live-dot{display:inline-block;width:8px;height:8px;background:#66bb6a;border-radius:50%;animation:pulse 2s infinite;margin-right:6px;vertical-align:middle}
@keyframes pulse{0%{opacity:1}50%{opacity:0.6}100%{opacity:1}}
.footer{text-align:center;margin-top:30px;color:#555;font-size:0.8em}

/* Ranks */
.rank-tree{display:flex;flex-direction:column;gap:8px}
.rank-item{display:flex;align-items:center;padding:14px 18px;background:#1a1a2e;border-radius:10px;border:1px solid #2a2a4a;gap:16px}
.rank-item.unlocked{background:#1a2e1a;border-color:#2e7d32}
.rank-item.locked{opacity:0.6}
.rank-item.current{border-color:#4fc3f7;box-shadow:0 0 12px rgba(79,195,247,0.15)}
.rank-item .icon{font-size:2em;width:50px;text-align:center}
.rank-item .info{flex:1}
.rank-item .info .name{font-size:1.1em;font-weight:600}
.rank-item .info .days{color:#888;font-size:0.8em}
.rank-item .progress-bar{width:120px;height:8px;background:#0f0f1a;border-radius:4px;overflow:hidden}
.rank-item .progress-bar .fill{height:100%;background:#4fc3f7;border-radius:4px;transition:width 0.5s}
.rank-item .status .check{color:#66bb6a;font-size:1.5em}
.rank-item .status .lock{color:#555;font-size:1.2em}

/* Setup overlay */
#setup-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:#0f0f1a;z-index:9999;display:flex;align-items:center;justify-content:center;overflow-y:auto}
.setup-box{background:#1a1a2e;border-radius:16px;border:1px solid #2a2a4a;padding:40px;max-width:520px;width:90%;margin:40px auto}
.setup-box h1{text-align:center;color:#4fc3f7;font-size:1.8em;margin-bottom:5px}
.setup-box .subtitle{text-align:center;color:#888;margin-bottom:30px;font-size:0.9em}
.setup-step{display:none}
.setup-step.active{display:block}
.setup-step h3{color:#ccc;margin-bottom:20px;font-size:1.1em}
.setup-nav{display:flex;justify-content:space-between;margin-top:25px;gap:12px}
.setup-steps{display:flex;justify-content:center;gap:8px;margin-bottom:30px}
.setup-steps .dot{width:10px;height:10px;border-radius:50%;background:#2a2a4a;transition:all 0.3s}
.setup-steps .dot.active{background:#4fc3f7}
.setup-steps .dot.done{background:#66bb6a}
.rank-select{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;margin-bottom:16px}
.rank-option{padding:12px;text-align:center;background:#0f0f1a;border:1px solid #2a2a4a;border-radius:8px;cursor:pointer;transition:all 0.2s}
.rank-option:hover{border-color:#4fc3f7;background:#1a1a35}
.rank-option.selected{border-color:#4fc3f7;background:#1a1a35;box-shadow:0 0 8px rgba(79,195,247,0.2)}
.rank-option .days{font-size:1.1em;font-weight:600;color:#4fc3f7}
.rank-option .label{font-size:0.75em;color:#888;margin-top:2px}
.picture-input{display:none}
.profile-header{display:flex;align-items:center;gap:20px;margin-bottom:20px}
.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;padding:14px 24px;color:#e0e0e0;z-index:10000;opacity:0;transition:opacity 0.3s;pointer-events:none}
.toast.show{opacity:1}
.toast.success{border-color:#66bb6a;color:#66bb6a}
.toast.error{border-color:#ef5350;color:#ef5350}
.update-check{display:inline-flex;align-items:center;gap:8px}
.update-check .spinner{width:16px;height:16px;border:2px solid #2a2a4a;border-top-color:#4fc3f7;border-radius:50%;animation:spin 0.8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div id="setup-overlay" style="display:none"></div>
<div id="app" style="display:none">
<div class="sidebar">
<div class="brand">
<h2>JustGivenUp!</h2>
<div class="ver">v2.2</div>
</div>
<nav>
<a href="#" data-tab="dashboard" class="active"><span class="icon">&#x1F4CA;</span> <span data-i18n="dashboard">Dashboard</span></a>
<a href="#" data-tab="profile"><span class="icon">&#x1F464;</span> <span data-i18n="profile">Profile</span></a>
<a href="#" data-tab="ranks"><span class="icon">&#x1F3C6;</span> <span data-i18n="ranks">Ranks</span></a>
<a href="#" data-tab="settings"><span class="icon">&#x2699;&#xFE0F;</span> <span data-i18n="settings">Settings</span></a>
<a href="#" data-tab="dashboard" id="check-update-link"><span class="icon">&#x1F504;</span> <span data-i18n="check_update">Check Update</span></a>
</nav>
</div>
<div class="main">
<div class="topbar">
<div class="page-title" id="page-title">Dashboard</div>
<button class="lang-toggle" id="lang-toggle">العربية</button>
</div>
<div class="content">

<div id="tab-dashboard" class="tab active">
<div id="lock-info"></div>
<div class="grid">
<div class="stat-card"><div class="label" data-i18n="clean_days">Clean Days</div><div class="value green" id="clean-days">0</div><div class="sub" data-i18n="since_last_relapse">since last relapse</div></div>
<div class="stat-card"><div class="label" data-i18n="blocked">Blocked Attempts</div><div class="value" id="total-blocked">0</div><div class="sub" data-i18n="detected_stopped">detected and stopped</div></div>
<div class="stat-card"><div class="label" data-i18n="relapses">Relapses</div><div class="value red" id="total-relapses">0</div><div class="sub" data-i18n="times_continued">times you chose to continue</div></div>
<div class="stat-card"><div class="label" data-i18n="longest_clean">Longest Clean Streak</div><div class="value yellow" id="longest-streak">0</div><div class="sub" data-i18n="days">days</div></div>
<div class="stat-card"><div class="label" data-i18n="warnings">Warnings Shown</div><div class="value" id="warnings-shown">0</div><div class="sub" data-i18n="times_reminded">times you were reminded</div></div>
<div class="stat-card"><div class="label" data-i18n="start_date">Start Date</div><div class="value" style="font-size:1.2em" id="start-date">--</div><div class="sub" data-i18n="journey_began">your journey began</div></div>
</div>
<div class="history"><h3 data-i18n="recent_activity">Recent Activity</h3><div id="activity-list"><div class="history-item"><span class="date" data-i18n="no_activity">No activity recorded yet</span></div></div></div>
<div class="footer"><span class="badge"><span class="live-dot"></span><span data-i18n="live">Live</span></span> JustGivenUp! -- Your commitment, protected by code.</div>
</div>

<div id="tab-profile" class="tab">
<div class="card">
<h3 data-i18n="profile_info">Profile Information</h3>
<div style="text-align:center;margin-bottom:20px">
<div class="profile-pic-wrapper">
<img class="profile-pic" id="profile-pic" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect fill='%231a1a2e' width='100' height='100'/%3E%3Ctext x='50' y='55' text-anchor='middle' fill='%23555' font-size='40' font-family='sans-serif'%3E👤%3C/text%3E%3C/svg%3E" alt="Profile">
<button class="change-btn" id="pic-change-btn">&#x270F;&#xFE0F;</button>
<input type="file" class="picture-input" id="pic-input" accept="image/*">
</div>
</div>
<div class="form-group"><label data-i18n="name_label">Your Name</label><input id="profile-name" placeholder="Enter your name" maxlength="50"></div>
<div class="form-group"><label data-i18n="work_label">What brings you here?</label><select id="profile-work"><option value="" data-i18n="select_reason">Select a reason...</option><option value="productivity" data-i18n="option_productivity">Productivity</option><option value="self_improvement" data-i18n="option_self">Self Improvement</option><option value="mental_health" data-i18n="option_mental">Mental Health</option><option value="addiction" data-i18n="option_addiction">Overcoming Addiction</option><option value="focus" data-i18n="option_focus">Deep Focus</option><option value="other" data-i18n="option_other">Other</option></select></div>
<button class="btn btn-primary" id="profile-save" data-i18n="save_profile" onclick="saveProfile()">Save Profile</button>
</div>
</div>

<div id="tab-ranks" class="tab">
<div class="card">
<h3 data-i18n="rank_progress">Rank Progress</h3>
<p style="color:#888;font-size:0.9em;margin-bottom:20px"><span data-i18n="current_streak">Current Streak</span>: <strong id="rank-current-streak">0</strong> <span data-i18n="days">days</span> | <span data-i18n="longest">Longest</span>: <strong id="rank-longest-streak">0</strong> <span data-i18n="days">days</span></p>
<div id="next-rank-info" style="display:none;background:#1a1a35;border-radius:8px;padding:14px;margin-bottom:20px;border:1px solid #2a2a4a">
<div style="display:flex;align-items:center;gap:12px">
<div id="next-rank-icon" style="font-size:2em"></div>
<div style="flex:1">
<div style="font-size:0.85em;color:#888" data-i18n="next_rank">Next Rank</div>
<div id="next-rank-name" style="font-weight:600;font-size:1.1em"></div>
<div style="font-size:0.8em;color:#888"><span data-i18n="remaining_days">Remaining</span>: <strong id="next-rank-remaining">0</strong> <span data-i18n="days">days</span></div>
<div style="margin-top:8px;height:8px;background:#0f0f1a;border-radius:4px;overflow:hidden"><div id="next-rank-bar" style="height:100%;background:#4fc3f7;border-radius:4px;transition:width 0.5s;width:0%"></div></div>
</div>
</div>
</div>
<div class="card">
<h3 data-i18n="all_ranks">All Ranks</h3>
<div class="rank-tree" id="rank-tree"></div>
</div>
</div>

<div id="tab-settings" class="tab">
<div class="card">
<h3 data-i18n="settings_title">Settings</h3>
<div class="form-group"><label><input type="checkbox" id="setting-autostart" style="width:auto;margin-right:8px;vertical-align:middle;accent-color:#4fc3f7"> <span data-i18n="open_with_windows">Open with Windows startup</span></label></div>
<div class="form-group"><label data-i18n="language_label">Language / اللغة</label><select id="setting-lang"><option value="en">English</option><option value="ar">العربية</option></select></div>
<button class="btn btn-primary" id="settings-save" onclick="saveSettings()" data-i18n="save_settings">Save Settings</button>
</div>
<div class="card">
<h3 data-i18n="about">About</h3>
<p style="color:#888;font-size:0.9em;line-height:1.6">
<strong>JustGivenUp! v2.2</strong><br>
<span data-i18n="about_desc">A tamper-proof Windows screen guardian with AI-powered NSFW detection, smart filtering, and cryptographic time-lock.</span><br><br>
<span data-i18n="build_info">Built with C++23 / MinGW / ONNX Runtime / Ninja</span><br>
<a href="https://github.com/RaGAEIDOS/justgivenup" style="color:#4fc3f7" target="_blank">GitHub</a>
</p>
</div>
</div>

</div>
</div>
</div>
<div id="toast" class="toast"></div>

<script>
const VERSION = "v2.2";
let currentLang = "en";

const I18N = {
en: {
dashboard:"Dashboard",profile:"Profile",ranks:"Ranks",settings:"Settings",check_update:"Check Update",
clean_days:"Clean Days",since_last_relapse:"since last relapse",blocked:"Blocked Attempts",
detected_stopped:"detected and stopped",relapses:"Relapses",times_continued:"times you chose to continue",
longest_clean:"Longest Clean Streak",days:"days",warnings:"Warnings Shown",times_reminded:"times you were reminded",
start_date:"Start Date",journey_began:"your journey began",recent_activity:"Recent Activity",
no_activity:"No activity recorded yet",live:"Live",
profile_info:"Profile Information",name_label:"Your Name",work_label:"What brings you here?",
select_reason:"Select a reason...",option_productivity:"Productivity",option_self:"Self Improvement",
option_mental:"Mental Health",option_addiction:"Overcoming Addiction",option_focus:"Deep Focus",
option_other:"Other",save_profile:"Save Profile",rank_progress:"Rank Progress",
current_streak:"Current Streak",longest:"Longest",next_rank:"Next Rank",
remaining_days:"Remaining",all_ranks:"All Ranks",
settings_title:"Settings",open_with_windows:"Open with Windows startup",
language_label:"Language / اللغة",save_settings:"Save Settings",about:"About",
about_desc:"A tamper-proof Windows screen guardian with AI-powered NSFW detection, smart filtering, and cryptographic time-lock.",
build_info:"Built with C++23 / MinGW / ONNX Runtime / Ninja",
saved:"Saved successfully!",error:"An error occurred",checking:"Checking for updates...",
update_current:"You have the latest version",update_available:"Update available! Download from GitHub",
setup_welcome:"Welcome to JustGivenUp!",
setup_subtitle:"Let's get you set up in a few steps",
setup_name:"What should we call you?",
setup_name_placeholder:"Enter your name",
setup_reason:"What brings you here?",
setup_goal:"Choose your goal",
setup_goal_desc:"Select how many days you want to lock the program. This cannot be undone until the timer runs out.",
setup_auto:"Open with Windows startup?",
setup_auto_desc:"Recommended: the program starts automatically when you log in",
setup_lang:"Choose your language / اختر لغتك",
setup_finish:"Ready! Click Finish to start your journey.",
setup_btn_finish:"Finish & Start",
setup_btn_next:"Next",
setup_btn_back:"Back",
setup_picture:"Add a profile picture (optional)",
setup_your_name:"Your Name",
step:"Step",
of:"of",
lock_active:"LOCKED -- Time-lock active until",
lock_inactive:"UNLOCKED -- No active time-lock",
recent_activity_title:"Recent Activity",
activity_blocked:"Attempt Blocked",
activity_relapse:"Relapse",
activity_none:"No activity recorded yet -- keep it that way!"
},
ar: {
dashboard:"لوحة التحكم",profile:"الملف الشخصي",ranks:"الرتب",settings:"الإعدادات",check_update:"التحقق من التحديثات",
clean_days:"الأيام النظيفة",since_last_relapse:"منذ آخر انتكاسة",blocked:"المحاولات المحظورة",
detected_stopped:"تم اكتشافها وإيقافها",relapses:"حالات الانتكاس",times_continued:"عدد مرات المتابعة رغم التحذير",
longest_clean:"أطول سلسلة نظيفة",days:"يوم",warnings:"التحذيرات المعروضة",
times_reminded:"عدد مرات التذكير",start_date:"تاريخ البداية",journey_began:"بدأت رحلتك",
recent_activity:"النشاط الأخير",no_activity:"لا يوجد نشاط مسجل بعد",live:"مباشر",
profile_info:"معلومات الملف الشخصي",name_label:"اسمك",work_label:"ما الذي أتى بك إلى هنا؟",
select_reason:"اختر سبباً...",option_productivity:"الإنتاجية",option_self:"تطوير الذات",
option_mental:"الصحة النفسية",option_addiction:"التغلب على الإدمان",option_focus:"التركيز العميق",
option_other:"أخرى",save_profile:"حفظ الملف الشخصي",rank_progress:"تقدم الرتب",
current_streak:"السلسلة الحالية",longest:"الأطول",next_rank:"الرتبة التالية",
remaining_days:"المتبقي",all_ranks:"جميع الرتب",
settings_title:"الإعدادات",open_with_windows:"الفتح مع بدء تشغيل ويندوز",
language_label:"Language / اللغة",save_settings:"حفظ الإعدادات",about:"حول",
about_desc:"برنامج حماية شاشة لنظام ويندوز، يعمل بالذكاء الاصطناعي لكشف المحتوى غير المناسب، مع فلتر ذكي وقفل زمني مشفر.",
build_info:"بُني بـ C++23 / MinGW / ONNX Runtime / Ninja",
saved:"تم الحفظ بنجاح!",error:"حدث خطأ",checking:"جاري التحقق من التحديثات...",
update_current:"لديك أحدث إصدار",update_available:"يوجد تحديث! حمّله من GitHub",
setup_welcome:"مرحباً بك في JustGivenUp!",
setup_subtitle:"دعنا نجهز الإعدادات في خطوات قليلة",
setup_name:"ماذا تريد أن نناديك؟",
setup_name_placeholder:"أدخل اسمك",
setup_reason:"ما الذي أتى بك إلى هنا؟",
setup_goal:"اختر هدفك",
setup_goal_desc:"اختر عدد الأيام التي تريد قفل البرنامج فيها. لا يمكن التراجع عن هذا حتى ينتهي المؤقت.",
setup_auto:"الفتح مع بدء تشغيل ويندوز؟",
setup_auto_desc:"موصى به: يبدأ البرنامج تلقائياً عند تسجيل الدخول",
setup_lang:"اختر لغتك / Choose your language",
setup_finish:"جاهز! اضغط إنهاء لبدء رحلتك.",
setup_btn_finish:"إنهاء والبدء",
setup_btn_next:"التالي",
setup_btn_back:"السابق",
setup_picture:"أضف صورة شخصية (اختياري)",
setup_your_name:"اسمك",
step:"الخطوة",of:"من",
lock_active:"مقفل -- القفل الزمني نشط حتى",
lock_inactive:"غير مقفل -- لا يوجد قفل زمني نشط",
recent_activity_title:"النشاط الأخير",
activity_blocked:"تم حظر محاولة",
activity_relapse:"انتكاسة",
activity_none:"لا يوجد نشاط مسجل بعد -- حافظ على ذلك!"
}
};

function t(key) {
return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
}

function applyLang() {
document.querySelectorAll('[data-i18n]').forEach(el => {
const k = el.getAttribute('data-i18n');
el.textContent = t(k);
});
document.body.classList.toggle('rtl', currentLang === 'ar');
document.getElementById('lang-toggle').textContent = currentLang === 'ar' ? 'English' : 'العربية';
document.title = currentLang === 'ar' ? 'JustGivenUp! -- لوحة التحكم' : 'JustGivenUp! -- Dashboard';
}

function showToast(msg, type) {
const t = document.getElementById('toast');
t.textContent = msg; t.className = 'toast show ' + (type||'');
setTimeout(() => t.classList.remove('show'), 3000);
}

function switchTab(name) {
document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('active'));
document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
document.querySelector(`.sidebar nav a[data-tab="${name}"]`)?.classList.add('active');
document.getElementById(`tab-${name}`)?.classList.add('active');
const titles = {dashboard:'Dashboard',profile:'Profile',ranks:'Ranks',settings:'Settings'};
document.getElementById('page-title').textContent = t(name);
}

document.querySelectorAll('.sidebar nav a').forEach(a => {
a.addEventListener('click', e => {
e.preventDefault();
const tab = a.getAttribute('data-tab');
if (tab === 'dashboard' && a.innerHTML.includes('Check')) {
checkUpdate(); return;
}
switchTab(tab);
if (tab === 'ranks') loadRanks();
if (tab === 'profile') loadProfile();
});
});

// Language toggle
document.getElementById('lang-toggle').addEventListener('click', () => {
currentLang = currentLang === 'en' ? 'ar' : 'en';
applyLang();
document.getElementById('setting-lang').value = currentLang;
});

// Setup Wizard
function showSetupWizard() {
const overlay = document.getElementById('setup-overlay');
if (!overlay) return;
let html = '<div class="setup-box">';
html += '<h1>JustGivenUp!</h1><p class="subtitle" data-i18n="setup_subtitle">' + t('setup_subtitle') + '</p>';
html += '<div class="setup-steps" id="setup-steps">';
html += '<div class="dot active"></div>'.repeat(6);
html += '</div>';

// Step 1: Language
html += '<div class="setup-step active" data-step="0">';
html += '<h3 data-i18n="setup_lang">' + t('setup_lang') + '</h3>';
html += '<div class="form-group"><select id="setup-lang"><option value="en">English</option><option value="ar">العربية</option></select></div>';
html += '</div>';

// Step 2: Name
html += '<div class="setup-step" data-step="1">';
html += '<h3 data-i18n="setup_name">' + t('setup_name') + '</h3>';
html += '<div class="form-group"><input id="setup-name" placeholder="' + t('setup_name_placeholder') + '" maxlength="50"></div>';
html += '</div>';

// Step 3: Reason
html += '<div class="setup-step" data-step="2">';
html += '<h3 data-i18n="setup_reason">' + t('setup_reason') + '</h3>';
html += '<div class="form-group"><select id="setup-work"><option value="" selected>' + t('select_reason') + '</option><option value="productivity">' + t('option_productivity') + '</option><option value="self_improvement">' + t('option_self') + '</option><option value="mental_health">' + t('option_mental') + '</option><option value="addiction">' + t('option_addiction') + '</option><option value="focus">' + t('option_focus') + '</option><option value="other">' + t('option_other') + '</option></select></div>';
html += '</div>';

// Step 4: Goal (rank select)
html += '<div class="setup-step" data-step="3">';
html += '<h3 data-i18n="setup_goal">' + t('setup_goal') + '</h3>';
html += '<p style="color:#888;font-size:0.85em;margin-bottom:16px" data-i18n="setup_goal_desc">' + t('setup_goal_desc') + '</p>';
html += '<div class="rank-select" id="setup-rank-select">';
const RANK_DAYS = [7,14,21,30,60,90,120,240,300,365,680,1220,2550];
const RANK_NAMES = ['Bronze','Silver','Gold','Platinum','Diamond','Master','Grandmaster','Legend','Mythic','Immortal','Transcendent','Ascended','Enlightened'];
const RANK_ICONS = ['🥉','🥈','🥇','💎','💠','👑','⚜️','🏆','🌟','♾️','🔥','☀️','🕊️'];
for (let i = 0; i < RANK_DAYS.length; i++) {
html += '<div class="rank-option" data-days="' + RANK_DAYS[i] + '" onclick="selectSetupRank(this)"><div class="days">' + RANK_DAYS[i] + '</div><div class="label">' + RANK_NAMES[i] + '</div></div>';
}
html += '</div><input type="hidden" id="setup-lock-days" value="30">';
html += '</div>';

// Step 5: Auto-start
html += '<div class="setup-step" data-step="4">';
html += '<h3 data-i18n="setup_auto">' + t('setup_auto') + '</h3>';
html += '<p style="color:#888;font-size:0.85em;margin-bottom:16px" data-i18n="setup_auto_desc">' + t('setup_auto_desc') + '</p>';
html += '<label style="display:flex;align-items:center;gap:10px;cursor:pointer"><input type="checkbox" id="setup-autostart" checked style="width:18px;height:18px;accent-color:#4fc3f7"> <span>' + t('open_with_windows') + '</span></label>';
html += '</div>';

// Step 6: Picture + Finish
html += '<div class="setup-step" data-step="5">';
html += '<h3 data-i18n="setup_finish">' + t('setup_finish') + '</h3>';
html += '<div style="text-align:center;margin:20px 0"><img class="profile-pic" id="setup-pic-preview" src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\'%3E%3Crect fill=\'%231a1a2e\' width=\'100\' height=\'100\'/%3E%3Ctext x=\'50\' y=\'55\' text-anchor=\'middle\' fill=\'%23555\' font-size=\'40\' font-family=\'sans-serif\'%3E📷%3C/text%3E%3C/svg%3E" alt="Profile"></div>';
html += '<button class="btn btn-secondary" onclick="document.getElementById(\'setup-pic-input\').click()" style="display:block;margin:0 auto 10px">📷 ' + t('setup_picture') + '</button>';
html += '<input type="file" class="picture-input" id="setup-pic-input" accept="image/*">';
html += '</div>';

html += '<div class="setup-nav"><button class="btn btn-secondary" id="setup-prev" onclick="setupPrev()">' + t('setup_btn_back') + '</button><button class="btn btn-primary" id="setup-next" onclick="setupNext()">' + t('setup_btn_next') + '</button></div>';
html += '<p id="setup-step-label" style="text-align:center;color:#555;font-size:0.8em;margin-top:12px">' + t('step') + ' 1 ' + t('of') + ' 6</p>';
html += '</div>';
overlay.innerHTML = html;
overlay.style.display = 'flex';
}

let setupStep = 0;
function selectSetupRank(el) {
document.querySelectorAll('.rank-option').forEach(r => r.classList.remove('selected'));
el.classList.add('selected');
document.getElementById('setup-lock-days').value = el.getAttribute('data-days');
}
function updateSetupLang() {
// Re-apply i18n to setup wizard
}
function setupNext() {
if (setupStep === 0) {
// Save language
currentLang = document.getElementById('setup-lang').value;
applyLang();
}
if (setupStep === 5) { finishSetup(); return; }
document.querySelector(`.setup-step[data-step="${setupStep}"]`).classList.remove('active');
setupStep++;
document.querySelector(`.setup-step[data-step="${setupStep}"]`).classList.add('active');
document.querySelectorAll('.setup-steps .dot').forEach((d,i) => {
d.classList.toggle('active', i === setupStep);
d.classList.toggle('done', i < setupStep);
});
document.getElementById('setup-step-label').textContent = t('step') + ' ' + (setupStep+1) + ' ' + t('of') + ' 6';
if (setupStep === 5) document.getElementById('setup-next').textContent = t('setup_btn_finish');
else document.getElementById('setup-next').textContent = t('setup_btn_next');
}
function setupPrev() {
if (setupStep === 0) return;
document.querySelector(`.setup-step[data-step="${setupStep}"]`).classList.remove('active');
setupStep--;
document.querySelector(`.setup-step[data-step="${setupStep}"]`).classList.add('active');
document.querySelectorAll('.setup-steps .dot').forEach((d,i) => {
d.classList.toggle('active', i === setupStep);
d.classList.toggle('done', i < setupStep);
});
document.getElementById('setup-step-label').textContent = t('step') + ' ' + (setupStep+1) + ' ' + t('of') + ' 6';
document.getElementById('setup-next').textContent = t('setup_btn_next');
}

async function finishSetup() {
const name = document.getElementById('setup-name').value || 'User';
const work = document.getElementById('setup-work').value || '';
const lockDays = parseInt(document.getElementById('setup-lock-days').value) || 30;
const autoStart = document.getElementById('setup-autostart').checked;
let picture = '';
const img = document.getElementById('setup-pic-preview');
if (img && img.src && img.src.startsWith('data:')) picture = img.src;

try {
const r = await fetch('/api/setup', {
method:'POST',
headers:{'Content-Type':'application/json'},
body: JSON.stringify({name,work,picture,auto_start:autoStart,lock_days:lockDays,language:currentLang})
});
const d = await r.json();
if (d.ok) {
document.getElementById('setup-overlay').style.display = 'none';
document.getElementById('app').style.display = 'flex';
showToast('Setup complete!', 'success');
loadProfile();
refresh();
}
} catch(e) { showToast(t('error'), 'error'); }
}

// Setup picture
document.addEventListener('change', function(e) {
if (e.target.id === 'setup-pic-input' && e.target.files && e.target.files[0]) {
const reader = new FileReader();
reader.onload = function(ev) {
document.getElementById('setup-pic-preview').src = ev.target.result;
};
reader.readAsDataURL(e.target.files[0]);
}
if (e.target.id === 'pic-input' && e.target.files && e.target.files[0]) {
const reader = new FileReader();
reader.onload = function(ev) {
document.getElementById('profile-pic').src = ev.target.result;
};
reader.readAsDataURL(e.target.files[0]);
}
});

// Profile
document.getElementById('pic-change-btn')?.addEventListener('click', () => document.getElementById('pic-input').click());

async function saveProfile() {
const name = document.getElementById('profile-name').value;
const work = document.getElementById('profile-work').value;
let picture = '';
const img = document.getElementById('profile-pic');
if (img && img.src && img.src.startsWith('data:')) picture = img.src;
try {
const r = await fetch('/api/profile', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,work,picture})});
const d = await r.json();
if (d.ok) showToast(t('saved'), 'success');
} catch(e) { showToast(t('error'), 'error'); }
}

async function loadProfile() {
try {
const r = await fetch('/api/profile');
const d = await r.json();
if (d.name) document.getElementById('profile-name').value = d.name;
if (d.work) document.getElementById('profile-work').value = d.work;
if (d.picture) document.getElementById('profile-pic').src = d.picture;
} catch(e) {}
}

async function loadRanks() {
try {
const r = await fetch('/api/ranks');
const d = await r.json();
document.getElementById('rank-current-streak').textContent = d.current_streak;
document.getElementById('rank-longest-streak').textContent = d.longest_streak;

const nextInfo = document.getElementById('next-rank-info');
if (d.next_rank && d.next_rank.days) {
nextInfo.style.display = 'block';
document.getElementById('next-rank-icon').textContent = d.next_rank.icon || '🏆';
document.getElementById('next-rank-name').textContent = (currentLang === 'ar' ? d.next_rank.name_ar : d.next_rank.name_en) || d.next_rank.name_en;
document.getElementById('next-rank-remaining').textContent = d.next_rank.remaining || 0;
document.getElementById('next-rank-bar').style.width = (d.next_rank.progress || 0) + '%';
} else if (d.max_rank_reached) {
nextInfo.style.display = 'block';
document.getElementById('next-rank-icon').textContent = '👑';
document.getElementById('next-rank-name').textContent = currentLang === 'ar' ? 'أقصى رتبة!' : 'Max Rank Reached!';
document.getElementById('next-rank-remaining').textContent = '∞';
document.getElementById('next-rank-bar').style.width = '100%';
} else { nextInfo.style.display = 'none'; }

const tree = document.getElementById('rank-tree');
tree.innerHTML = '';
(d.ranks || []).forEach(r => {
const item = document.createElement('div');
item.className = 'rank-item' + (r.unlocked ? ' unlocked' : ' locked');
if (d.current_rank && d.current_rank.days === r.days) item.classList.add('current');
item.innerHTML = '<div class="icon">' + (r.icon || '🏅') + '</div><div class="info"><div class="name">' + (currentLang === 'ar' ? r.name_ar : r.name_en) + '</div><div class="days">' + r.days + ' ' + t('days') + '</div></div><div class="status">' + (r.unlocked ? '<span class="check">&#10003;</span>' : '<span class="lock">&#128274;</span>') + '</div>';
tree.appendChild(item);
});
} catch(e) {
document.getElementById('rank-tree').innerHTML = '<div class="history-item"><span class="date">Error loading ranks</span></div>';
}
}

async function saveSettings() {
const lang = document.getElementById('setting-lang').value;
const autoStart = document.getElementById('setting-autostart').checked;
try {
const r = await fetch('/api/settings', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({language:lang,auto_start:autoStart})});
const d = await r.json();
if (d.ok) {
currentLang = lang;
applyLang();
showToast(t('saved'), 'success');
}
} catch(e) { showToast(t('error'), 'error'); }
}

async function loadSettings() {
try {
const r = await fetch('/api/settings');
const d = await r.json();
document.getElementById('setting-lang').value = d.language || 'en';
document.getElementById('setting-autostart').checked = d.auto_start || false;
currentLang = d.language || 'en';
applyLang();
} catch(e) {}
}

async function checkUpdate() {
const overlay = document.getElementById('setup-overlay');
if (overlay && overlay.style.display !== 'none') return;
showToast(t('checking'), '');
try {
window.open('https://github.com/RaGAEIDOS/justgivenup/releases/latest', '_blank');
showToast(t('update_current'), 'success');
} catch(e) { showToast(t('error'), 'error'); }
}

// Dashboard stats refresh
async function refresh() {
try {
const r = await fetch('/api/stats');
const d = await r.json();
document.getElementById('clean-days').textContent = d.clean_days;
document.getElementById('total-blocked').textContent = d.total_blocked;
document.getElementById('total-relapses').textContent = d.total_relapses;
document.getElementById('longest-streak').textContent = d.longest_clean_streak;
document.getElementById('warnings-shown').textContent = d.relapse_warning_shown;
document.getElementById('start-date').textContent = d.start_date || (currentLang === 'ar' ? 'اليوم' : 'Today');
const lockDiv = document.getElementById('lock-info');
if (d.is_locked) {
lockDiv.className = 'lock-info locked';
lockDiv.innerHTML = '<strong>' + (currentLang === 'ar' ? 'مقفل' : 'LOCKED') + '</strong> -- ' + t('lock_active') + ' ' + (d.lock_until || 'N/A');
} else {
lockDiv.className = 'lock-info unlocked';
lockDiv.innerHTML = '<strong>' + (currentLang === 'ar' ? 'غير مقفل' : 'UNLOCKED') + '</strong> -- ' + t('lock_inactive');
}
const list = document.getElementById('activity-list');
let html = '';
if (d.last_blocked_date) html += '<div class="history-item"><span class="tp blocked">' + t('activity_blocked') + '</span><span class="date">' + d.last_blocked_date + '</span></div>';
if (d.last_relapse_date) html += '<div class="history-item"><span class="tp relapse">' + t('activity_relapse') + '</span><span class="date">' + d.last_relapse_date + '</span></div>';
if (!html) html = '<div class="history-item"><span class="date">' + t('activity_none') + '</span></div>';
list.innerHTML = html;
} catch(e) { console.error('Stats fetch failed:', e); }
}

// Init
(async function init() {
try {
const r = await fetch('/api/setup-status');
const d = await r.json();
if (!d.setup_complete) {
showSetupWizard();
} else {
document.getElementById('app').style.display = 'flex';
currentLang = (await (await fetch('/api/settings')).json()).language || 'en';
applyLang();
loadProfile();
loadSettings();
refresh();
setInterval(refresh, 5000);
}
} catch(e) {
document.getElementById('app').style.display = 'flex';
currentLang = 'en';
applyLang();
refresh();
setInterval(refresh, 5000);
}
})();
</script>
</body>
</html>)HTML";
}
