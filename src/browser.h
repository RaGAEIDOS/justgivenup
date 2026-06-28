#pragma once
#include <string>
#include <vector>

class BrowserKiller {
public:
    void set_targets(const std::vector<std::string>& names) { _targets = names; }
    int kill_all();
private:
    std::vector<std::string> _targets;
};
