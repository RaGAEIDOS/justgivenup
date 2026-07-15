#pragma once
#include <string>
#include <atomic>
#include <thread>

class Dashboard {
public:
    Dashboard(int port = 8081);
    ~Dashboard();
    void start();
    void stop();
    bool is_running() const { return _running; }
private:
    void server_thread();
    std::string handle_request(const std::string& path);
    std::string dashboard_html();
    int _port;
    std::atomic<bool> _running{false};
    std::thread* _thread{nullptr};
    void* _server_socket{nullptr}; // SOCKET
};
