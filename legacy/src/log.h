#pragma once
#include <string>

class Log {
public:
    enum Level { LVL_DEBUG, LVL_INFO, LVL_WARN, LVL_ERROR };
    static Log& instance();
    void write(Level lvl, const std::string& msg);
    void debug(const std::string& msg) { write(LVL_DEBUG, msg); }
    void info(const std::string& msg)  { write(LVL_INFO, msg); }
    void warn(const std::string& msg)  { write(LVL_WARN, msg); }
    void error(const std::string& msg) { write(LVL_ERROR, msg); }
    static std::string level_str(Level lvl);
private:
    Log();
    ~Log();
    FILE* _file{nullptr};
    std::string _path;
};
