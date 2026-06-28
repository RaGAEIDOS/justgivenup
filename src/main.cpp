#include <iostream>
#include <string>
#include <windows.h>
#include <tlhelp32.h>
#include <shlobj.h>
#include <shlwapi.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "shlwapi.lib")

#include "log.h"
#include "config.h"
#include "filter.h"
#include "browser.h"
#include "capture.h"
#include "detector.h"
#include "lock.h"
#include "guardian.h"
#include "tray.h"

// ── Helpers ─────────────────────────────────────────────

std::string exe_dir() {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    wchar_t* last = wcsrchr(path, L'\\');
    if (last) *last = L'\0';
    char pathA[MAX_PATH];
    WideCharToMultiByte(CP_UTF8, 0, path, -1, pathA, MAX_PATH, NULL, NULL);
    return pathA;
}

// ── Auto-start (Registry Run key) ──────────────────────

bool install_auto_start() {
    wchar_t exe_path[MAX_PATH];
    GetModuleFileNameW(NULL, exe_path, MAX_PATH);

    HKEY hKey;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                        0, NULL, 0, KEY_SET_VALUE, NULL, &hKey, NULL) != ERROR_SUCCESS)
        return false;

    LSTATUS ret = RegSetValueExW(hKey, L"JustGivenUp", 0, REG_SZ,
        (const BYTE*)exe_path, (DWORD)(wcslen(exe_path) + 1) * 2);
    RegCloseKey(hKey);
    Log::instance().info("[SETUP] Auto-start installed in registry");
    return ret == ERROR_SUCCESS;
}

bool remove_auto_start() {
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                      0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {
        RegDeleteValueW(hKey, L"JustGivenUp");
        RegCloseKey(hKey);
        Log::instance().info("[SETUP] Auto-start removed");
        return true;
    }
    return false;
}

// ── CLI ─────────────────────────────────────────────────

void print_help(const std::string& name) {
    std::cout << "JustGivenUp! - Screen Guardian (C++)\n\n";
    std::cout << "  " << name << "                        Run with system tray\n";
    std::cout << "  " << name << " --install               Add to Windows startup\n";
    std::cout << "  " << name << " --remove                Remove from Windows startup\n";
    std::cout << "  " << name << " --lock--DAYS            Lock for N days (3 confirmations required)\n";
    std::cout << "  " << name << " --emergency-stop        Kill all JustGivenUp processes\n";
    std::cout << "  " << name << " --watchdog              Run as watchdog process\n";
    std::cout << "  " << name << " --help                  Show this help\n";
}

bool prompt_confirm(const std::string& action, int round) {
    for (int i = 0; i < 3; i++) {
        std::cout << "\n!! WARNING (" << (round + 1) << "/3) -- " << action << std::endl;
        std::cout << "Type YES to confirm: ";
        std::string input;
        std::getline(std::cin, input);
        if (input == "YES") return true;
        std::cout << "Confirmation failed.\n";
    }
    std::cout << "Too many failed attempts. Aborting.\n";
    return false;
}

void emergency_stop() {
    Lock lock;
    if (lock.is_locked() && lock.is_valid()) {
        std::cout << "[BLOCKED] A time-lock is active until " << lock.until_str()
                  << ". --emergency-stop cannot remove the lock." << std::endl;
        Log::instance().warn("[EMERGENCY STOP] Refused — lock active");
        return;
    }

    Log::instance().warn("[EMERGENCY STOP] Killing all JustGivenUp processes...");
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap != INVALID_HANDLE_VALUE) {
        PROCESSENTRY32W pe = { sizeof(PROCESSENTRY32W) };
        if (Process32FirstW(snap, &pe)) {
            do {
                HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                if (hProc) {
                    wchar_t path[MAX_PATH];
                    DWORD sz = MAX_PATH;
                    if (QueryFullProcessImageNameW(hProc, 0, path, &sz)) {
                        std::wstring wpath(path);
                        if (wpath.find(L"JustGivenUp") != std::wstring::npos) {
                            TerminateProcess(hProc, 1);
                        }
                    }
                    CloseHandle(hProc);
                }
            } while (Process32NextW(snap, &pe));
        }
        CloseHandle(snap);
    }
    std::cout << "[EMERGENCY STOP] All JustGivenUp processes killed." << std::endl;
}

// ── Main ────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    std::string exe = exe_dir() + "\\JustGivenUp.exe";
    std::string model_path = exe_dir() + "\\320n.onnx";
    std::string config_path = ""; // Config auto-loads from %APPDATA%

    Log::instance().info("=== JustGivenUp! v2.0 (C++) ===");

    // Parse CLI
    if (argc > 1) {
        std::string cmd = argv[1];

        // --lock--DAYS
        if (cmd.rfind("--lock--", 0) == 0) {
            std::string days_str = cmd.substr(8);
            int days = 0;
            try { days = std::stoi(days_str); } catch (...) {}
            if (days < 1 || days > 3650) {
                std::cout << "[FAIL] Invalid days. Use --lock--N where N is 1–3650." << std::endl;
                return 1;
            }

            Lock lock;
            if (lock.is_locked() && lock.is_valid()) {
                std::cout << "[LOCK] Already locked until " << lock.until_str() << std::endl;
                if (!prompt_confirm("Overwrite existing lock with " + std::to_string(days) + " days?", 1)) return 1;
            }

            for (int r = 0; r < 3; r++) {
                if (!prompt_confirm("Lock the program for " + std::to_string(days) + " days? This CANNOT be undone.", r))
                    return 1;
            }

            lock.set_lock(days);
            install_auto_start();

            std::cout << "[LOCK] Locked for " << days << " day(s) until " << lock.until_str() << std::endl;
            return 0;
        }

        if (cmd == "--install") {
            std::cout << (install_auto_start() ? "[OK] Auto-start installed" : "[FAIL] Install failed") << std::endl;
            return 0;
        }
        if (cmd == "--remove") {
            std::cout << (remove_auto_start() ? "[OK] Auto-start removed" : "[FAIL] Not found") << std::endl;
            return 0;
        }
        if (cmd == "--emergency-stop") {
            emergency_stop();
            return 0;
        }
        if (cmd == "--watchdog") {
            // Not available in main exe — run JustGivenUp_watchdog.exe instead
            std::cout << "[WATCHDOG] Use JustGivenUp_watchdog.exe separately" << std::endl;
            return 0;
        }
        if (cmd == "--help") {
            std::string name = argv[0];
            size_t pos = name.find_last_of("\\/");
            if (pos != std::string::npos) name = name.substr(pos + 1);
            print_help(name);
            return 0;
        }
        std::cout << "Unknown: " << cmd << "\nUse --help" << std::endl;
        return 1;
    }

    // ── Normal mode (tray) ───────────────────────────────
    ShowWindow(GetConsoleWindow(), SW_HIDE);
    // Init modules
    Config config;
    Lock lock;
    Filter filter;
    BrowserKiller killer;
    Capture capture;
    Detector detector(model_path);

    if (!detector.loaded()) {
        Log::instance().error("[MAIN] Detector failed to load — aborting");
        std::cerr << "[FATAL] Cannot load NSFW model. Check " << model_path << std::endl;
        return 1;
    }

    // Configure filter
    filter.set_whitelist_skip(config.get().whitelist_skip);
    filter.set_whitelist_lenient(config.get().whitelist_lenient);
    filter.set_blacklist_kill(config.get().blacklist_kill);
    killer.set_targets(config.get().browsers);

    // Create guardian
    Guardian guardian(&config, &filter, &killer, &capture, &detector, &lock);

    // Create tray
    Tray tray(&guardian);
    if (!tray.create()) {
        Log::instance().error("[MAIN] Tray creation failed");
        return 1;
    }

    // Auto-start guardian if locked or configured
    if (guardian.is_locked() || true) { // always start for simplicity
        guardian.start();
        tray.update_status(guardian.status());
    }

    // Run message loop
    Log::instance().info("[MAIN] Tray running");
    tray.run();

    // Cleanup
    guardian.stop();
    Log::instance().info("[MAIN] Exited");
    return 0;
}
