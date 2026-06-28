#include "filter.h"
#include "log.h"
#include <windows.h>
#include <algorithm>

Filter::Filter() {}

// ── EnumWindows callback ──────────────────────────────────
struct EnumCtx { std::vector<std::string>* out; };
static BOOL CALLBACK enum_proc(HWND hwnd, LPARAM lp) {
    auto ctx = (EnumCtx*)lp;
    if (!IsWindowVisible(hwnd)) return TRUE;
    int len = GetWindowTextLengthW(hwnd) + 1;
    if (len <= 1) return TRUE;
    std::wstring buf(len, L'\0');
    GetWindowTextW(hwnd, &buf[0], len);
    buf.resize(wcslen(buf.c_str()));
    int need = WideCharToMultiByte(CP_UTF8, 0, buf.c_str(), (int)buf.size(), NULL, 0, NULL, NULL);
    std::string title(need, '\0');
    WideCharToMultiByte(CP_UTF8, 0, buf.c_str(), (int)buf.size(), &title[0], need, NULL, NULL);
    ctx->out->push_back(title);
    return TRUE;
}

std::vector<std::string> Filter::get_all_window_titles() {
    std::vector<std::string> titles;
    EnumCtx ctx{&titles};
    EnumWindows(enum_proc, (LPARAM)&ctx);
    return titles;
}

std::string Filter::get_active_window_title() {
    HWND hwnd = GetForegroundWindow();
    if (!hwnd) return "";
    int len = GetWindowTextLengthW(hwnd) + 1;
    if (len <= 1) return "";
    std::wstring buf(len, L'\0');
    GetWindowTextW(hwnd, &buf[0], len);
    buf.resize(wcslen(buf.c_str()));
    int need = WideCharToMultiByte(CP_UTF8, 0, buf.c_str(), (int)buf.size(), NULL, 0, NULL, NULL);
    std::string title(need, '\0');
    WideCharToMultiByte(CP_UTF8, 0, buf.c_str(), (int)buf.size(), &title[0], need, NULL, NULL);
    return title;
}

bool Filter::matches_any(const std::string& title_lower, const std::vector<std::string>& keywords) {
    for (const auto& kw : keywords) {
        if (title_lower.find(kw) != std::string::npos)
            return true;
    }
    return false;
}

FilterMode Filter::check_window() {
    std::string title = get_active_window_title();
    if (title.empty()) return FilterMode::NONE;

    std::string lower = title;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);

    // Blacklist first (instant kill)
    if (matches_any(lower, _blacklist_kill)) {
        Log::instance().warn("[FILTER] KILL matched (foreground): " + title);
        return FilterMode::KILL;
    }

    // Whitelist skip
    if (matches_any(lower, _whitelist_skip)) {
        Log::instance().debug("[FILTER] SKIP matched (foreground): " + title);
        return FilterMode::SKIP;
    }

    // Whitelist lenient
    if (matches_any(lower, _whitelist_lenient)) {
        Log::instance().debug("[FILTER] LENIENT matched (foreground): " + title);
        return FilterMode::LENIENT;
    }

    return FilterMode::NONE;
}

FilterMode Filter::check_all_windows() {
    // First check foreground window
    FilterMode mode = check_window();
    if (mode != FilterMode::NONE)
        return mode;

    auto titles = get_all_window_titles();
    for (const auto& t : titles) {
        std::string lower = t;
        std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);

        // Blacklist in any window → instant kill
        if (matches_any(lower, _blacklist_kill)) {
            Log::instance().warn("[FILTER] KILL matched (any window): " + t);
            return FilterMode::KILL;
        }

        // Whitelist skip in any visible window → skip
        if (matches_any(lower, _whitelist_skip)) {
            Log::instance().debug("[FILTER] SKIP matched (any window): " + t);
            return FilterMode::SKIP;
        }

        // Whitelist lenient
        if (matches_any(lower, _whitelist_lenient)) {
            Log::instance().debug("[FILTER] LENIENT matched (any window): " + t);
            return FilterMode::LENIENT;
        }
    }

    return FilterMode::NONE;
}
