#include "config.h"
#include "log.h"
#include <fstream>
#include <shlobj.h>
#include <shlwapi.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "shlwapi.lib")

Config::Config() {
    wchar_t appdata[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_APPDATA, NULL, 0, appdata))) {
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"JustGivenUp");
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"config.json");
        char pathA[MAX_PATH];
        WideCharToMultiByte(CP_UTF8, 0, appdata, -1, pathA, MAX_PATH, NULL, NULL);
        _path = pathA;

        std::ifstream ifs(_path);
        if (ifs.good()) {
            try {
                json j; ifs >> j;
                _cfg = from_json(j);
                Log::instance().info("Config loaded: " + _path);
                return;
            } catch (...) {
                Log::instance().error("Config parse failed, using defaults");
            }
        }
    }
    load_defaults();
    save();
}

void Config::load_defaults() {
    _cfg.interval_seconds = 3;
    _cfg.nsfw_threshold = 0.45f;
    _cfg.cooldown_seconds = 10;
    _cfg.browsers = {"chrome.exe","firefox.exe","msedge.exe","brave.exe","opera.exe"};
    // ── Whitelist: skip detection entirely ──
    _cfg.whitelist_skip = {
        "youtube","youtu.be",
        "coursera","udemy","edx","edx.org","khanacademy","udacity","skillshare",
        "pluralsight","codecademy","freecodecamp","mit ocw","stanford online",
        "canvas","blackboard","moodle","schoology","google classroom","classroom",
        "stackoverflow","github","gitlab","bitbucket","codepen","replit",
        "leetcode","hackerrank","linkedin","linkedin learning",
        "google scholar","researchgate","academia.edu","pubmed","jstor","wikipedia",
        "zoom","teams","microsoft teams","meet","google meet","webex","slack","discord",
        "colab","google colab","medium.com","dev.to","geeksforgeeks",
        "w3schools","tutorialspoint","programiz",
        "outlook","gmail",
    };
    // ── Whitelist: lenient detection (higher threshold) ──
    _cfg.whitelist_lenient = {};
    // ── Blacklist: instant kill (proxy/porn/streaming/.ru) ──
    _cfg.blacklist_kill = {
        "proxy","vpn","unblock","unblocked","bypass",
        "ok.ru","vk.ru","mail.ru","yandex.ru","rutube.ru","rambler.ru",
        ".ru ",".ru/","xnxx","xhamster","pornhub","xvideos","redtube",
        "youporn","tube8","spankbang","porntube","eporner",
        "netflix","hulu","disney+","hbomax","prime video",
        "twitch.tv","kick.com","onlyfans","fansly",
    };
}

AppConfig Config::from_json(const json& j) {
    AppConfig c;
    if (j.contains("interval_seconds")) c.interval_seconds = j["interval_seconds"];
    if (j.contains("nsfw_threshold")) c.nsfw_threshold = j["nsfw_threshold"];
    if (j.contains("cooldown_seconds")) c.cooldown_seconds = j["cooldown_seconds"];
    if (j.contains("browsers")) c.browsers = j["browsers"].get<std::vector<std::string>>();
    if (j.contains("whitelist_skip")) c.whitelist_skip = j["whitelist_skip"].get<std::vector<std::string>>();
    if (j.contains("whitelist_lenient")) c.whitelist_lenient = j["whitelist_lenient"].get<std::vector<std::string>>();
    if (j.contains("blacklist_kill")) c.blacklist_kill = j["blacklist_kill"].get<std::vector<std::string>>();
    if (j.contains("lock_until")) c.lock_until = j["lock_until"];
    if (j.contains("lock_seal")) c.lock_seal = j["lock_seal"];
    return c;
}

json Config::to_json(const AppConfig& c) {
    return {
        {"interval_seconds", c.interval_seconds},
        {"nsfw_threshold", c.nsfw_threshold},
        {"cooldown_seconds", c.cooldown_seconds},
        {"browsers", c.browsers},
        {"whitelist_skip", c.whitelist_skip},
        {"whitelist_lenient", c.whitelist_lenient},
        {"blacklist_kill", c.blacklist_kill},
        {"lock_until", c.lock_until},
        {"lock_seal", c.lock_seal},
    };
}

void Config::save() {
    std::ofstream ofs(_path);
    if (ofs.good()) {
        ofs << to_json(_cfg).dump(4);
        Log::instance().info("Config saved");
    }
}
