#pragma once
#include <string>
#include <vector>

class BrowserManager {
public:
    void set_targets(const std::vector<std::string>& names) { _targets = names; }
    const std::vector<std::string>& targets() const { return _targets; }

    // Close foreground browser tab via Ctrl+W (works for ALL browsers)
    bool close_active_tab();

    // Show warning dialog and return true if user chose to continue (relapse)
    // Returns: false = user went back / tab was closed, true = user chose to continue
    bool show_warning_dialog(const std::string& reason, int timeout_seconds = 0);

private:
    std::vector<std::string> _targets;
};
