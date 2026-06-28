#pragma once
#include <string>

class Watchdog {
public:
    static bool is_main_running();
    static void restart_main(const std::string& main_path);
    static void run(const std::string& main_path);
};
