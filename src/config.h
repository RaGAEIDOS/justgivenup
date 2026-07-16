#pragma once
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
using json = nlohmann::json;

struct AppConfig {
    int interval_seconds = 3;
    float nsfw_threshold = 0.45f;
    int cooldown_seconds = 10;
    int dashboard_port = 8081;
    std::vector<std::string> browsers;
    std::vector<std::string> whitelist_skip;
    std::vector<std::string> whitelist_lenient;
    std::vector<std::string> blacklist_kill;
    std::string lock_until;
    std::string lock_seal;
    bool setup_complete = false;
    std::string language = "en";
    std::string user_name;
    std::string user_work;
    std::string user_picture;
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
