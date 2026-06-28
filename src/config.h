#pragma once
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
using json = nlohmann::json;

struct AppConfig {
    int interval_seconds = 3;
    float nsfw_threshold = 0.45f;
    int cooldown_seconds = 10;
    std::vector<std::string> browsers = {"chrome.exe", "firefox.exe", "msedge.exe", "brave.exe", "opera.exe"};
    std::vector<std::string> whitelist_skip;
    std::vector<std::string> whitelist_lenient;  // youtube only
    std::vector<std::string> blacklist_kill;     // proxy/porn/streaming → instant kill
    std::string lock_until;
    std::string lock_seal;
};

class Config {
public:
    Config();
    AppConfig& get() { return _cfg; }
    void save();
    std::string path() const { return _path; }
private:
    AppConfig _cfg;
    std::string _path;
    void load_defaults();
    AppConfig from_json(const json& j);
    json to_json(const AppConfig& cfg);
};
