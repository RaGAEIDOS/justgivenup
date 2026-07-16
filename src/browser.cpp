#include "browser.h"
#include "log.h"
#include <windows.h>
#include <tlhelp32.h>
#include <string>
#include <thread>
#include <chrono>

bool BrowserManager::close_active_tab() {
    // Bring foreground window to top
    HWND hwnd = GetForegroundWindow();
    if (!hwnd) {
        Log::instance().error("[BROWSER] No foreground window to close tab");
        return false;
    }

    // Make sure the window is visible and not our own
    wchar_t class_name[256];
    GetClassNameW(hwnd, class_name, 256);
    std::wstring cls(class_name);
    if (cls.find(L"JustGivenUp") != std::wstring::npos) {
        Log::instance().warn("[BROWSER] Foreground window is JustGivenUp, not closing tab");
        return false;
    }

    Log::instance().warn("[BROWSER] Closing foreground tab via Ctrl+W");

    // Use SendInput to simulate Ctrl+W
    INPUT inputs[4] = {};

    // Ctrl key down
    inputs[0].type = INPUT_KEYBOARD;
    inputs[0].ki.wVk = VK_CONTROL;
    inputs[0].ki.dwFlags = 0;

    // W key down
    inputs[1].type = INPUT_KEYBOARD;
    inputs[1].ki.wVk = 'W';
    inputs[1].ki.dwFlags = 0;

    // W key up
    inputs[2].type = INPUT_KEYBOARD;
    inputs[2].ki.wVk = 'W';
    inputs[2].ki.dwFlags = KEYEVENTF_KEYUP;

    // Ctrl key up
    inputs[3].type = INPUT_KEYBOARD;
    inputs[3].ki.wVk = VK_CONTROL;
    inputs[3].ki.dwFlags = KEYEVENTF_KEYUP;

    SendInput(4, inputs, sizeof(INPUT));
    return true;
}

bool BrowserManager::show_warning_dialog(const std::string& reason, int timeout_seconds) {
    Log::instance().warn("[BROWSER] Showing warning dialog: " + reason);

    std::string title = "JustGivenUp! - Warning";
    std::string message = "WARNING: " + reason + "\n\n"
                          "This content has been detected as inappropriate.\n"
                          "Click 'Go Back' to close this tab and stay on track.\n"
                          "Click 'Continue' to proceed anyway (this will be logged as a relapse).";

    if (timeout_seconds > 0) {
        message += "\n\nAuto-closing tab in " + std::to_string(timeout_seconds) + " seconds if no response.";
    }

    HWND parent = GetForegroundWindow();
    wchar_t cls[256] = {};
    if (parent) GetClassNameW(parent, cls, 256);
    std::wstring parent_cls(cls);
    if (parent_cls.find(L"JustGivenUp") != std::wstring::npos)
        parent = NULL;

    std::wstring wtitle(title.begin(), title.end());
    std::wstring wmsg(message.begin(), message.end());

    int result = MessageBoxW(parent, wmsg.c_str(), wtitle.c_str(),
                             MB_YESNO | MB_ICONWARNING | MB_SYSTEMMODAL |
                             MB_SETFOREGROUND | MB_TOPMOST | MB_DEFBUTTON2);

    if (result == IDYES) {
        Log::instance().warn("[BROWSER] User chose to go back - closing tab");
        close_active_tab();
        return false;
    }
    Log::instance().warn("[BROWSER] User chose to continue - relapse logged");
    return true;
}

void BrowserManager::kill_all_browsers() {
    Log::instance().warn("[BROWSER] Killing all browser processes...");
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return;
    PROCESSENTRY32W pe = { sizeof(PROCESSENTRY32W) };
    if (Process32FirstW(snap, &pe)) {
        do {
            std::wstring exe(pe.szExeFile);
            for (auto& target : _targets) {
                std::wstring wtarget(target.begin(), target.end());
                // Case-insensitive compare
                std::wstring uexe = exe, utarget = wtarget;
                for (auto& c : uexe) c = towlower(c);
                for (auto& c : utarget) c = towlower(c);
                if (uexe == utarget) {
                    HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                    if (hProc) {
                        TerminateProcess(hProc, 1);
                        CloseHandle(hProc);
                        Log::instance().warn("[BROWSER] Killed: " + target);
                    }
                    break;
                }
            }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
}
