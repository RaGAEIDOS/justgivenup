#pragma once
#include <windows.h>
#include <string>

class Guardian; // forward decl

class Tray {
public:
    Tray(Guardian* g);
    ~Tray();
    bool create();
    void update_status(const std::string& text);
    void run();
    void stop();
    HWND hwnd() const { return _hwnd; }

private:
    static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp);
    void on_tray_msg(UINT msg);
    void show_menu();
    void set_icon(bool active);

    Guardian* _guardian;
    HWND _hwnd{nullptr};
    HINSTANCE _hinst{nullptr};
    bool _running = false;
    std::string _status = "Starting...";
    HICON _icon_on{nullptr};
    HICON _icon_off{nullptr};
    UINT _taskbar_msg;
};
