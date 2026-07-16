#include "dashboard.h"
#include "stats.h"
#include "log.h"
#include "lock.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <sstream>
#include <thread>
#include <chrono>
#pragma comment(lib, "ws2_32.lib")

Dashboard::Dashboard(int port) : _port(port) {}

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
        struct timeval tv = {1, 0}; // 1 second timeout

        int activity = select(0, &readfds, NULL, NULL, &tv);
        if (activity < 0) break;
        if (activity == 0) continue;
        if (!FD_ISSET(server, &readfds)) continue;

        sockaddr_in client;
        int client_len = sizeof(client);
        SOCKET client_sock = accept(server, (sockaddr*)&client, &client_len);
        if (client_sock == INVALID_SOCKET) continue;

        // Read request
        char buf[4096] = {};
        recv(client_sock, buf, sizeof(buf) - 1, 0);
        std::string request(buf);

        // Parse path from "GET /path HTTP/1.1"
        std::string path = "/";
        size_t get_pos = request.find("GET ");
        if (get_pos != std::string::npos) {
            size_t path_start = get_pos + 4;
            size_t path_end = request.find(' ', path_start);
            if (path_end != std::string::npos)
                path = request.substr(path_start, path_end - path_start);
        }

        std::string response = handle_request(path);
        send(client_sock, response.c_str(), (int)response.size(), 0);
        closesocket(client_sock);
    }

    closesocket(server);
    WSACleanup();
    _server_socket = nullptr;
}

std::string Dashboard::handle_request(const std::string& path) {
    if (path == "/stats") {
        Stats::instance().update_streak();
        json j = Stats::instance().to_json();

        Lock lock;
        j["is_locked"] = lock.is_locked();
        j["lock_until"] = lock.until_str();
        j["clean_days"] = Stats::instance().clean_days();

        std::string body = j.dump(2);
        std::ostringstream resp;
        resp << "HTTP/1.1 200 OK\r\n"
             << "Content-Type: application/json\r\n"
             << "Access-Control-Allow-Origin: *\r\n"
             << "Content-Length: " << body.size() << "\r\n"
             << "\r\n"
             << body;
        return resp.str();
    }

    std::string body = dashboard_html();
    std::ostringstream resp;
    resp << "HTTP/1.1 200 OK\r\n"
         << "Content-Type: text/html\r\n"
         << "Content-Length: " << body.size() << "\r\n"
         << "\r\n"
         << body;
    return resp.str();
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
  .container{max-width:900px;margin:0 auto;padding:30px 20px}
  h1{text-align:center;font-size:2em;color:#fff;margin-bottom:5px;letter-spacing:1px}
  .subtitle{text-align:center;color:#888;margin-bottom:30px;font-size:0.9em}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:30px}
  .card{background:#1a1a2e;border-radius:12px;padding:20px;text-align:center;border:1px solid #2a2a4a}
  .card .value{font-size:2.5em;font-weight:700;color:#4fc3f7;margin:10px 0}
  .card .value.green{color:#66bb6a}
  .card .value.red{color:#ef5350}
  .card .value.yellow{color:#ffa726}
  .card .label{color:#888;font-size:0.85em;text-transform:uppercase;letter-spacing:1px}
  .card .sub{font-size:0.75em;color:#666;margin-top:5px}
  .history{background:#1a1a2e;border-radius:12px;padding:20px;border:1px solid #2a2a4a}
  .history h3{color:#aaa;margin-bottom:15px;letter-spacing:1px}
  .history-item{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #2a2a4a;font-size:0.9em}
  .history-item:last-child{border-bottom:none}
  .history-item .type{color:#4fc3f7}
  .history-item .type.blocked{color:#66bb6a}
  .history-item .type.relapse{color:#ef5350}
  .history-item .date{color:#666}
  .footer{text-align:center;margin-top:30px;color:#555;font-size:0.8em}
  .badge{display:inline-block;background:#1a1a2e;border-radius:20px;padding:4px 14px;font-size:0.75em;color:#4fc3f7;border:1px solid #2a2a4a}
  .streak-fire{font-size:1.5em;vertical-align:middle}
  @keyframes pulse{0%{opacity:1}50%{opacity:0.6}100%{opacity:1}}
  .live-dot{display:inline-block;width:8px;height:8px;background:#66bb6a;border-radius:50%;animation:pulse 2s infinite;margin-right:6px;vertical-align:middle}
  .lock-info{text-align:center;margin-bottom:20px;padding:12px;border-radius:8px;font-size:0.9em}
  .lock-info.locked{background:#3e2723;border:1px solid #6d4c41;color:#ff8a65}
  .lock-info.unlocked{background:#1b3a1b;border:1px solid #2e7d32;color:#81c784}
</style>
</head>
<body>
<div class="container">
  <h1>JustGivenUp!</h1>
  <p class="subtitle">Your Digital Accountability Dashboard</p>

  <div id="lock-info"></div>

  <div class="grid">
    <div class="card">
      <div class="label">Clean Days</div>
      <div class="value green" id="clean-days">0</div>
      <div class="sub">since last relapse</div>
    </div>
    <div class="card">
      <div class="label">Blocked Attempts</div>
      <div class="value" id="total-blocked">0</div>
      <div class="sub">detected and stopped</div>
    </div>
    <div class="card">
      <div class="label">Relapses</div>
      <div class="value red" id="total-relapses">0</div>
      <div class="sub">times you chose to continue</div>
    </div>
    <div class="card">
      <div class="label">Longest Clean Streak</div>
      <div class="value yellow" id="longest-streak">0</div>
      <div class="sub">days</div>
    </div>
    <div class="card">
      <div class="label">Warnings Shown</div>
      <div class="value" id="warnings-shown">0</div>
      <div class="sub">times you were reminded</div>
    </div>
    <div class="card">
      <div class="label">Start Date</div>
      <div class="value" style="font-size:1.2em" id="start-date">--</div>
      <div class="sub">your journey began</div>
    </div>
  </div>

  <div class="history">
    <h3>Recent Activity</h3>
    <div id="activity-list">
      <div class="history-item"><span class="date">No activity recorded yet</span></div>
    </div>
  </div>

  <div class="footer">
    <span class="badge"><span class="live-dot"></span>Live</span>
    JustGivenUp! -- Your commitment, protected by code.
  </div>
</div>

<script>
async function refresh() {
  try {
    const r = await fetch('/stats');
    const d = await r.json();

    document.getElementById('clean-days').textContent = d.clean_days;
    document.getElementById('total-blocked').textContent = d.total_blocked;
    document.getElementById('total-relapses').textContent = d.total_relapses;
    document.getElementById('longest-streak').textContent = d.longest_clean_streak;
    document.getElementById('warnings-shown').textContent = d.relapse_warning_shown;
    document.getElementById('start-date').textContent = d.start_date || 'Today';

    // Lock info
    const lockDiv = document.getElementById('lock-info');
    if (d.is_locked) {
      lockDiv.className = 'lock-info locked';
      lockDiv.innerHTML = '<strong>LOCKED</strong> -- Time-lock active until ' + (d.lock_until || 'N/A');
    } else {
      lockDiv.className = 'lock-info unlocked';
      lockDiv.innerHTML = '<strong>UNLOCKED</strong> -- No active time-lock';
    }

    // Build activity list
    const list = document.getElementById('activity-list');
    let html = '';
    if (d.last_blocked_date) {
      html += '<div class="history-item"><span class="type blocked">Attempt Blocked</span><span class="date">' + d.last_blocked_date + '</span></div>';
    }
    if (d.last_relapse_date) {
      html += '<div class="history-item"><span class="type relapse">Relapse</span><span class="date">' + d.last_relapse_date + '</span></div>';
    }
    if (!html) {
      html = '<div class="history-item"><span class="date">No activity recorded yet -- keep it that way!</span></div>';
    }
    list.innerHTML = html;

  } catch(e) {
    console.error('Stats fetch failed:', e);
  }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>)HTML";
}
