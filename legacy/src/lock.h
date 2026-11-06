#pragma once
#include <string>
#include <chrono>

class Lock {
public:
    Lock();
    bool is_locked();
    bool is_valid();
    void check_integrity();
    void set_lock(int days_from_now);
    void remove_lock();
    int remaining_seconds();
    std::string until_str();

private:
    static std::string sha256(const std::string& data);
    static std::string seal(const std::string& value);
    static const char* SALT;

    std::string _lock_until;
    std::string _lock_seal;
};
