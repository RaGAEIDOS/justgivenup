#include "tray.h"
#include "guardian.h"
#include "log.h"
#include <shellapi.h>
#include <commctrl.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "comctl32.lib")

Tray::Tray(Guardian* g) : _guardian(g) {
    _hinst = GetModuleHandleW(NULL);
    _taskbar_msg = RegisterWindowMessageW(L"TaskbarCreated");
}

Tray::~Tray() {
    stop();
}

bool Tray::create() {
    WNDCLASSW wc = {};
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = _hinst;
    wc.lpszClassName = L"JustGivenUpTray";
    RegisterClassW(&wc);

    _hwnd = CreateWindowExW(0, L"JustGivenUpTray", L"JustGivenUp", 0,
        0, 0, 0, 0, NULL, NULL, _hinst, this);
    if (!_hwnd) {
        Log::instance().error("[TRAY] CreateWindow failed");
        return false;
    }

    // Load custom icon from resources
    _icon_on = LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(100));
    _icon_off = LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(100));

    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof(NOTIFYICONDATAW);
    nid.hWnd = _hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_APP + 1;
    nid.hIcon = _icon_off;
    wcsncpy_s(nid.szTip, L"JustGivenUp — Starting...", _TRUNCATE);
    Shell_NotifyIconW(NIM_ADD, &nid);

    Log::instance().info("[TRAY] Created");
    return true;
}

void Tray::set_icon(bool active) {
    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof(NOTIFYICONDATAW);
    nid.hWnd = _hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_ICON;
    nid.hIcon = active ? _icon_on : _icon_off;
    Shell_NotifyIconW(NIM_MODIFY, &nid);
}

void Tray::update_status(const std::string& text) {
    _status = text;
    std::wstring wtext(text.begin(), text.end());
    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof(NOTIFYICONDATAW);
    nid.hWnd = _hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_TIP;
    wcsncpy_s(nid.szTip, wtext.c_str(), _TRUNCATE);
    Shell_NotifyIconW(NIM_MODIFY, &nid);
}

void Tray::show_menu() {
    HMENU hMenu = CreatePopupMenu();
    bool locked = _guardian->is_locked();

    if (locked) {
        std::string lock_text = "Locked until " + _guardian->lock_until_str();
        std::wstring wlock(lock_text.begin(), lock_text.end());
        AppendMenuW(hMenu, MF_STRING | MF_GRAYED, 100, wlock.c_str());
        AppendMenuW(hMenu, MF_SEPARATOR, 0, NULL);
        AppendMenuW(hMenu, MF_STRING | MF_GRAYED, 101, L"Stop");
        AppendMenuW(hMenu, MF_SEPARATOR, 0, NULL);
        AppendMenuW(hMenu, MF_STRING | MF_GRAYED, 102, L"Exit");
    } else {
        if (_guardian->is_running())
            AppendMenuW(hMenu, MF_STRING, 200, L"⏹ Stop");
        else
            AppendMenuW(hMenu, MF_STRING, 201, L"▶ Start");
        AppendMenuW(hMenu, MF_SEPARATOR, 0, NULL);
        AppendMenuW(hMenu, MF_STRING, 202, L"✕ Exit");
    }

    POINT pt;
    GetCursorPos(&pt);
    SetForegroundWindow(_hwnd);
    TrackPopupMenu(hMenu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, _hwnd, NULL);
    DestroyMenu(hMenu);
}

void Tray::on_tray_msg(UINT msg) {
    switch (msg) {
        case WM_LBUTTONUP:
            show_menu();
            break;
        case WM_RBUTTONUP:
            show_menu();
            break;
    }
}

LRESULT CALLBACK Tray::wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    Tray* self = (Tray*)GetWindowLongPtrW(hwnd, GWLP_USERDATA);
    if (msg == WM_CREATE) {
        CREATESTRUCTW* cs = (CREATESTRUCTW*)lp;
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)cs->lpCreateParams);
        return 0;
    }
    if (msg == WM_APP + 1 && self) {
        self->on_tray_msg((UINT)lp);
        return 0;
    }
    if (msg == WM_COMMAND && self) {
        switch (LOWORD(wp)) {
            case 200: self->_guardian->stop(); self->set_icon(false); break;
            case 201: self->_guardian->start(); self->set_icon(true); break;
            case 202: self->_guardian->stop(); PostQuitMessage(0); break;
        }
        return 0;
    }
    if (msg == WM_CLOSE || msg == WM_DESTROY) {
        if (self && self->_guardian->is_locked())
            return 0; // locked — ignore close/destroy attempts
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

void Tray::run() {
    _running = true;
    MSG msg;
    while (_running && GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}

void Tray::stop() {
    _running = false;
    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof(NOTIFYICONDATAW);
    nid.hWnd = _hwnd;
    nid.uID = 1;
    Shell_NotifyIconW(NIM_DELETE, &nid);
    if (_hwnd) {
        DestroyWindow(_hwnd);
        _hwnd = nullptr;
    }
}
