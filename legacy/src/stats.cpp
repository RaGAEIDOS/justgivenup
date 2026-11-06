#include "stats.h"
#include "log.h"
#include <cstdio>
#include <ctime>
#include <chrono>
#include <shlobj.h>
#include <shlwapi.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "shlwapi.lib")

Stats& Stats::instance() {
    static Stats inst;
    return inst;
}

Stats::Stats() {
    wchar_t appdata[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_APPDATA, NULL, 0, appdata))) {
        PathAppendW(appdata, L"JustGivenUp");
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"stats.json");
        char pathA[MAX_PATH];
        WideCharToMultiByte(CP_UTF8, 0, appdata, -1, pathA, MAX_PATH, NULL, NULL);
        _path = pathA;
        load();
    }
}

void Stats::load() {
    FILE* f = fopen(_path.c_str(), "r");
    if (f) {
        try {
            fseek(f, 0, SEEK_END);
            long sz = ftell(f);
            fseek(f, 0, SEEK_SET);
            std::string buf((size_t)sz, '\0');
            fread(buf.data(), 1, sz, f);
            fclose(f);
            json j = json::parse(buf);
            from_json(j);
        } catch (...) {
            Log::instance().error("[STATS] Failed to parse stats.json");
        }
    }
}

void Stats::save() {
    FILE* f = fopen(_path.c_str(), "w");
    if (f) {
        std::string data = to_json().dump(2);
        fwrite(data.data(), 1, data.size(), f);
        fclose(f);
    }
}

json Stats::to_json() const {
    return {
        {"start_date", _data.start_date},
        {"total_blocked", _data.total_blocked},
        {"total_relapses", _data.total_relapses},
        {"relapse_warning_shown", _data.relapse_warning_shown},
        {"current_streak_days", _data.current_streak_days},
        {"longest_streak_days", _data.longest_streak_days},
        {"last_blocked_date", _data.last_blocked_date},
        {"last_relapse_date", _data.last_relapse_date},
        {"last_clean_date", _data.last_clean_date},
        {"clean_days_streak", _data.clean_days_streak},
        {"longest_clean_streak", _data.longest_clean_streak}
    };
}

void Stats::from_json(const json& j) {
    if (j.contains("start_date")) _data.start_date = j["start_date"];
    if (j.contains("total_blocked")) _data.total_blocked = j["total_blocked"];
    if (j.contains("total_relapses")) _data.total_relapses = j["total_relapses"];
    if (j.contains("relapse_warning_shown")) _data.relapse_warning_shown = j["relapse_warning_shown"];
    if (j.contains("current_streak_days")) _data.current_streak_days = j["current_streak_days"];
    if (j.contains("longest_streak_days")) _data.longest_streak_days = j["longest_streak_days"];
    if (j.contains("last_blocked_date")) _data.last_blocked_date = j["last_blocked_date"];
    if (j.contains("last_relapse_date")) _data.last_relapse_date = j["last_relapse_date"];
    if (j.contains("last_clean_date")) _data.last_clean_date = j["last_clean_date"];
    if (j.contains("clean_days_streak")) _data.clean_days_streak = j["clean_days_streak"];
    if (j.contains("longest_clean_streak")) _data.longest_clean_streak = j["longest_clean_streak"];
}

void Stats::record_blocked() {
    _data.total_blocked++;
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    struct tm local; localtime_s(&local, &now);
    char buf[16]; strftime(buf, sizeof(buf), "%Y-%m-%d", &local);
    _data.last_blocked_date = buf;
    if (_data.start_date.empty()) _data.start_date = buf;
    save();
}

void Stats::record_relapse() {
    _data.total_relapses++;
    _data.clean_days_streak = 0;
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    struct tm local; localtime_s(&local, &now);
    char buf[16]; strftime(buf, sizeof(buf), "%Y-%m-%d", &local);
    _data.last_relapse_date = buf;
    if (_data.start_date.empty()) _data.start_date = buf;
    save();
}

void Stats::record_warning_shown() {
    _data.relapse_warning_shown++;
    save();
}

void Stats::update_streak() {
    if (_data.last_relapse_date.empty() && _data.last_blocked_date.empty()) {
        // No activity yet, streak from start_date
        if (!_data.start_date.empty()) {
            auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
            struct tm local; localtime_s(&local, &now);
            char today[16]; strftime(today, sizeof(today), "%Y-%m-%d", &local);
            _data.last_clean_date = today;
            // Calculate streak from start
            struct tm start_tm = {};
            sscanf(_data.start_date.c_str(), "%d-%d-%d", &start_tm.tm_year, &start_tm.tm_mon, &start_tm.tm_mday);
            start_tm.tm_year -= 1900; start_tm.tm_mon -= 1;
            time_t start_t = mktime(&start_tm);
            double days = difftime(now, start_t) / 86400;
            _data.clean_days_streak = std::max(0, (int)days);
        }
    } else if (!_data.last_relapse_date.empty()) {
        // Reset streak if relapsed today
        auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        struct tm local; localtime_s(&local, &now);
        char today[16]; strftime(today, sizeof(today), "%Y-%m-%d", &local);
        if (_data.last_relapse_date == today) {
            _data.clean_days_streak = 0;
        } else {
            // Calculate from last relapse
            struct tm relapse_tm = {};
            sscanf(_data.last_relapse_date.c_str(), "%d-%d-%d", &relapse_tm.tm_year, &relapse_tm.tm_mon, &relapse_tm.tm_mday);
            relapse_tm.tm_year -= 1900; relapse_tm.tm_mon -= 1;
            time_t relapse_t = mktime(&relapse_tm);
            double days = difftime(now, relapse_t) / 86400;
            _data.clean_days_streak = std::max(0, (int)days);
        }
    }
    _data.longest_clean_streak = std::max(_data.longest_clean_streak, _data.clean_days_streak);
    save();
}

int Stats::clean_days() const {
    if (_data.last_relapse_date.empty()) {
        // No relapses ever, calculate from start
        if (_data.start_date.empty()) return 0;
        auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        struct tm start_tm = {};
        sscanf(_data.start_date.c_str(), "%d-%d-%d", &start_tm.tm_year, &start_tm.tm_mon, &start_tm.tm_mday);
        start_tm.tm_year -= 1900; start_tm.tm_mon -= 1;
        time_t start_t = mktime(&start_tm);
        double days = difftime(now, start_t) / 86400;
        return std::max(0, (int)days);
    }
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    struct tm relapse_tm = {};
    sscanf(_data.last_relapse_date.c_str(), "%d-%d-%d", &relapse_tm.tm_year, &relapse_tm.tm_mon, &relapse_tm.tm_mday);
    relapse_tm.tm_year -= 1900; relapse_tm.tm_mon -= 1;
    time_t relapse_t = mktime(&relapse_tm);
    double days = difftime(now, relapse_t) / 86400;
    return std::max(0, (int)days);
}
