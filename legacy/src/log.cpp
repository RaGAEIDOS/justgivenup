#include "log.h"
#include <cstdio>
#include <ctime>
#include <chrono>
#include <shlobj.h>
#include <shlwapi.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "shlwapi.lib")

Log& Log::instance() {
    static Log inst;
    return inst;
}

Log::Log() {
    wchar_t appdata[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_APPDATA, NULL, 0, appdata))) {
        PathAppendW(appdata, L"JustGivenUp");
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"guardian.log");
        char pathA[MAX_PATH];
        WideCharToMultiByte(CP_UTF8, 0, appdata, -1, pathA, MAX_PATH, NULL, NULL);
        _path = pathA;
        _file = fopen(pathA, "a");
        if (_file) info("=== Guardian started ===");
    }
}

Log::~Log() {
    if (_file) fclose(_file);
}

std::string Log::level_str(Level lvl) {
    switch (lvl) {
        case LVL_DEBUG: return "DEBUG";
        case LVL_INFO:  return "INFO";
        case LVL_WARN:  return "WARN";
        case LVL_ERROR: return "ERROR";
        default:        return "?";
    }
}

void Log::write(Level lvl, const std::string& msg) {
    if (!_file) return;
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    struct tm local;
    localtime_s(&local, &now);
    char buf[64];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &local);
    fprintf(_file, "%s [%s] %s\n", buf, level_str(lvl).c_str(), msg.c_str());
    fflush(_file);
}
