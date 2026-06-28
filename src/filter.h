#pragma once
#include <string>
#include <vector>

enum class FilterMode { NONE, SKIP, LENIENT, KILL };

class Filter {
public:
    Filter();
    FilterMode check_window();
    FilterMode check_all_windows();
    static std::string get_active_window_title();
    static std::vector<std::string> get_all_window_titles();
    void set_whitelist_skip(const std::vector<std::string>& kw) { _whitelist_skip = kw; }
    void set_whitelist_lenient(const std::vector<std::string>& kw) { _whitelist_lenient = kw; }
    void set_blacklist_kill(const std::vector<std::string>& kw) { _blacklist_kill = kw; }
private:
    bool matches_any(const std::string& title_lower, const std::vector<std::string>& keywords);
    std::vector<std::string> _whitelist_skip;
    std::vector<std::string> _whitelist_lenient;
    std::vector<std::string> _blacklist_kill;
};
