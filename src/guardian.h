#pragma once
#include <string>
#include <atomic>
#include <thread>
#include <memory>

class Config;
class Filter;
class BrowserManager;
class Capture;
class Detector;
class Lock;

class Guardian {
public:
    Guardian(Config* cfg, Filter* filter, BrowserManager* killer,
             Capture* capture, Detector* detector, Lock* lock);
    ~Guardian();
    bool is_locked();
    bool is_running() const { return _running; }
    std::string status();
    std::string lock_until_str();
    void start();
    void stop();

private:
    void loop();
    bool handle_nsfw_detected(const std::string& reason);

    Config* _cfg;
    Filter* _filter;
    BrowserManager* _killer;
    Capture* _capture;
    Detector* _detector;
    Lock* _lock;

    std::atomic<bool> _running{false};
    std::thread* _thread{nullptr};
    double _cooldown_until{0};
    int _refusal_count{0};
    std::string _status_msg = "Stopped";
};
