#pragma once
#include <string>
#include <nlohmann/json.hpp>
using json = nlohmann::json;

struct StatsData {
    std::string start_date;
    int total_blocked = 0;
    int total_relapses = 0;
    int relapse_warning_shown = 0;
    int current_streak_days = 0;
    int longest_streak_days = 0;
    std::string last_blocked_date;
    std::string last_relapse_date;
    std::string last_clean_date;
    int clean_days_streak = 0;
    int longest_clean_streak = 0;
};

class Stats {
public:
    static Stats& instance();
    void load();
    void save();
    StatsData& data() { return _data; }

    void record_blocked();
    void record_relapse();
    void record_warning_shown();
    void update_streak();
    int clean_days() const;

    json to_json() const;
    void from_json(const json& j);

    std::string path() const { return _path; }

private:
    Stats();
    StatsData _data;
    std::string _path;
};
