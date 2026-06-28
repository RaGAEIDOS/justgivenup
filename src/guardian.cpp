#include "guardian.h"
#include "config.h"
#include "filter.h"
#include "browser.h"
#include "capture.h"
#include "detector.h"
#include "lock.h"
#include "log.h"
#include <chrono>
#include <thread>

Guardian::Guardian(Config* cfg, Filter* filter, BrowserKiller* killer,
                   Capture* capture, Detector* detector, Lock* lock)
    : _cfg(cfg), _filter(filter), _killer(killer), _capture(capture),
      _detector(detector), _lock(lock) {}

Guardian::~Guardian() { stop(); }

bool Guardian::is_locked() { return _lock && _lock->is_locked(); }

std::string Guardian::lock_until_str() { return _lock ? _lock->until_str() : ""; }

std::string Guardian::status() {
    if (is_locked()) {
        int rem = _lock->remaining_seconds();
        int h = rem / 3600, m = (rem % 3600) / 60, s = rem % 60;
        char buf[64];
        snprintf(buf, sizeof(buf), "Locked %02d:%02d:%02d", h, m, s);
        if (!_running) return std::string("Stopped - ") + buf;
        return buf;
    }
    return _status_msg;
}

void Guardian::start() {
    if (_running) return;
    _running = true;
    if (_lock) _lock->check_integrity();
    _status_msg = "Starting...";
    _thread = new std::thread(&Guardian::loop, this);
    Log::instance().info("[GUARDIAN] Started");
}

void Guardian::stop() {
    _running = false;
    if (_thread) {
        if (_thread->joinable()) _thread->join();
        delete _thread;
        _thread = nullptr;
    }
    _status_msg = "Stopped";
    Log::instance().info("[GUARDIAN] Stopped");
}

void Guardian::loop() {
    Log::instance().info("[GUARDIAN] Monitor loop started");
    int interval = _cfg->get().interval_seconds;
    float threshold = _cfg->get().nsfw_threshold;

    while (_running) {
        try {
            // Cooldown check
            auto now = std::chrono::steady_clock::now();
            double now_sec = std::chrono::duration<double>(now.time_since_epoch()).count();
            if (now_sec < _cooldown_until) {
                std::this_thread::sleep_for(std::chrono::milliseconds(500));
                continue;
            }

            _status_msg = "Monitoring";

            // Check ALL visible window titles (not just foreground)
            FilterMode mode = _filter->check_all_windows();

            // Blacklist kill: close browser immediately, no NSFW check needed
            if (mode == FilterMode::KILL) {
                Log::instance().warn("[GUARDIAN] Blacklist match — killing browser immediately");
                int killed = _killer->kill_all();
                if (killed > 0) {
                    _status_msg = "Closed browser (blacklist)";
                    _cooldown_until = now_sec + _cfg->get().cooldown_seconds;
                }
                std::this_thread::sleep_for(std::chrono::seconds(interval));
                continue;
            }

            // Whitelist skip: no detection at all
            if (mode == FilterMode::SKIP) {
                std::this_thread::sleep_for(std::chrono::seconds(interval));
                continue;
            }

            // Capture screen
            ScreenCapture sc = _capture->capture();
            if (sc.bgra.empty()) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                continue;
            }

            // Determine threshold (lenient = higher threshold, e.g. 0.75)
            float use_threshold = threshold;
            if (mode == FilterMode::LENIENT)
                use_threshold = 0.75f;

            // NSFW detection
            auto detections = _detector->detect(sc.bgra.data(), sc.width, sc.height, use_threshold);
            bool found_nsfw = false;
            for (auto& d : detections) {
                if (d.score >= use_threshold) {
                    found_nsfw = true;
                    Log::instance().warn(std::string("[GUARDIAN] NSFW: ")
                        + d.label + " score=" + std::to_string(d.score));
                }
            }

            if (found_nsfw) {
                int killed = _killer->kill_all();
                if (killed > 0) {
                    _status_msg = "Closed browser (NSFW)";
                    _cooldown_until = now_sec + _cfg->get().cooldown_seconds;
                }
            }

            std::this_thread::sleep_for(std::chrono::seconds(interval));

        } catch (const std::exception& e) {
            Log::instance().error(std::string("[GUARDIAN] Loop error: ") + e.what());
            std::this_thread::sleep_for(std::chrono::seconds(1));
        } catch (...) {
            Log::instance().error("[GUARDIAN] Loop unknown error");
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
    Log::instance().info("[GUARDIAN] Monitor loop stopped");
}
