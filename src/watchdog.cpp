#include "watchdog.h"
#include "log.h"
#include <windows.h>
#include <tlhelp32.h>
#include <string>
#include <algorithm>
#include <iostream>

bool Watchdog::is_main_running() {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return false;
    bool found = false;
    PROCESSENTRY32W pe = { sizeof(PROCESSENTRY32W) };
    if (Process32FirstW(snap, &pe)) {
        do {
            // Check for JustGivenUp.exe in command line
            HANDLE hProc = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pe.th32ProcessID);
            if (hProc) {
                wchar_t cmdline[32768];
                DWORD sz = sizeof(cmdline);
                if (QueryFullProcessImageNameW(hProc, 0, cmdline, &sz)) {
                    std::wstring wpath(cmdline);
                    if (wpath.find(L"JustGivenUp.exe") != std::wstring::npos &&
                        wpath.find(L"watchdog") == std::wstring::npos) {
                        found = true;
                        CloseHandle(hProc);
                        break;
                    }
                }
                CloseHandle(hProc);
            }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return found;
}

void Watchdog::restart_main(const std::string& main_path) {
    Log::instance().warn("[WATCHDOG] Restarting JustGivenUp");
    std::wstring wpath(main_path.begin(), main_path.end());
    std::wstring dir = wpath.substr(0, wpath.find_last_of(L"\\/"));

    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    if (CreateProcessW(wpath.c_str(), NULL, NULL, NULL, FALSE,
                       CREATE_NO_WINDOW, NULL, dir.c_str(), &si, &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    } else {
        Log::instance().error("[WATCHDOG] Failed to restart");
    }
}

void Watchdog::run(const std::string& main_path) {
    Log::instance().info("[WATCHDOG] Started");
    restart_main(main_path);
    while (true) {
        if (!is_main_running()) {
            restart_main(main_path);
        }
        Sleep(8000);
    }
}

int main() {
    HWND console = GetConsoleWindow();
    if (console) ShowWindow(console, SW_HIDE);
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    wchar_t* last = wcsrchr(path, L'\\');
    if (last) wcscpy(last + 1, L"JustGivenUp.exe");
    char pathA[MAX_PATH];
    WideCharToMultiByte(CP_UTF8, 0, path, -1, pathA, MAX_PATH, NULL, NULL);
    Watchdog::run(pathA);
    return 0;
}
