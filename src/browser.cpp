#include "browser.h"
#include "log.h"
#include <windows.h>
#include <tlhelp32.h>
#include <algorithm>

int BrowserKiller::kill_all() {
    if (_targets.empty()) return 0;

    // Lowercase our targets
    std::vector<std::string> targets_lower;
    for (auto& t : _targets) {
        std::string low = t;
        std::transform(low.begin(), low.end(), low.begin(), ::tolower);
        targets_lower.push_back(low);
    }

    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;

    PROCESSENTRY32W pe = { sizeof(PROCESSENTRY32W) };
    int killed = 0;

    if (Process32FirstW(snap, &pe)) {
        do {
            // Convert exe name to lower
            wchar_t* exe = pe.szExeFile;
            std::wstring wname(exe);
            std::string name(wname.begin(), wname.end());
            std::transform(name.begin(), name.end(), name.begin(), ::tolower);

            for (const auto& target : targets_lower) {
                if (name == target || name.find(target) != std::string::npos) {
                    HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                    if (hProc) {
                        if (TerminateProcess(hProc, 1)) {
                            killed++;
                            Log::instance().warn("[BROWSER] Terminated " + name + " (PID:" + std::to_string(pe.th32ProcessID) + ")");
                        }
                        CloseHandle(hProc);
                    }
                    break;
                }
            }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return killed;
}
