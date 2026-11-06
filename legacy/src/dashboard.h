#pragma once
#include <string>
#include <atomic>
#include <thread>
#include <vector>

class Config;

class Dashboard {
public:
    Dashboard(Config* cfg, int port = 8081);
    ~Dashboard();
    void start();
    void stop();
    bool is_running() const { return _running; }
private:
    void server_thread();
    std::string handle_request(const std::string& method, const std::string& path, const std::string& body);
    std::string dashboard_html();
    std::string api_setup_status();
    std::string api_handle_setup(const std::string& body);
    std::string api_profile();
    std::string api_save_profile(const std::string& body);
    std::string api_ranks();
    std::string api_settings();
    std::string api_save_settings(const std::string& body);
    std::string api_check_update();
    std::string api_stats();
    std::string api_changelog();
    void read_body(int sock, std::string& body, int content_len);
    Config* _cfg;
    int _port;
    std::atomic<bool> _running{false};
    std::thread* _thread{nullptr};
    void* _server_socket{nullptr};
};
