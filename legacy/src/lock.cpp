#include "lock.h"
#include "log.h"
#include <windows.h>
#include <bcrypt.h>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <vector>
#pragma comment(lib, "bcrypt.lib")

const char* Lock::SALT = "JvG!7k#9mL2$xR*p";

Lock::Lock() {
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\JustGivenUp", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        wchar_t buf[256]; DWORD sz = sizeof(buf);
        if (RegQueryValueExW(hKey, L"lock_until", NULL, NULL, (BYTE*)buf, &sz) == ERROR_SUCCESS)
            _lock_until = std::to_string(_wtoi64(buf));
        sz = sizeof(buf);
        if (RegQueryValueExW(hKey, L"lock_seal", NULL, NULL, (BYTE*)buf, &sz) == ERROR_SUCCESS) {
            char narrow[256];
            WideCharToMultiByte(CP_UTF8, 0, buf, -1, narrow, sizeof(narrow), NULL, NULL);
            _lock_seal = narrow;
        }
        RegCloseKey(hKey);
    }
}

std::string Lock::sha256(const std::string& data) {
    BCRYPT_ALG_HANDLE hAlg = NULL;
    if (BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_SHA256_ALGORITHM, NULL, 0) != 0)
        return "";

    // Get hash object size
    DWORD hashObjLen = 0, cbResult = 0;
    if (BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (BYTE*)&hashObjLen,
                          sizeof(hashObjLen), &cbResult, 0) != 0) {
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return "";
    }

    DWORD hashLen = 32; // SHA-256 always 32 bytes

    std::vector<BYTE> hashObj(hashObjLen);
    BCRYPT_HASH_HANDLE hHash = NULL;
    if (BCryptCreateHash(hAlg, &hHash, hashObj.data(), (ULONG)hashObj.size(),
                         NULL, 0, 0) != 0) {
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return "";
    }

    if (BCryptHashData(hHash, (BYTE*)data.data(), (ULONG)data.size(), 0) != 0) {
        BCryptDestroyHash(hHash); BCryptCloseAlgorithmProvider(hAlg, 0);
        return "";
    }

    std::vector<BYTE> hash(hashLen);
    if (BCryptFinishHash(hHash, hash.data(), hashLen, 0) != 0) {
        BCryptDestroyHash(hHash); BCryptCloseAlgorithmProvider(hAlg, 0);
        return "";
    }

    BCryptDestroyHash(hHash);
    BCryptCloseAlgorithmProvider(hAlg, 0);

    std::stringstream ss;
    for (BYTE b : hash)
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
    return ss.str();
}

std::string Lock::seal(const std::string& value) {
    return sha256(value + SALT);
}

bool Lock::is_locked() {
    if (_lock_until.empty()) return false;
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    try {
        long long lock_time = std::stoll(_lock_until);
        return now < lock_time;
    } catch (...) {
        return false;
    }
}

bool Lock::is_valid() {
    if (_lock_until.empty() && _lock_seal.empty()) return true;
    if (_lock_until.empty() || _lock_seal.empty()) return false;
    return _lock_seal == seal(_lock_until);
}

void Lock::check_integrity() {
    if (!is_valid() && !_lock_until.empty()) {
        Log::instance().warn("[LOCK] Tamper detected! Extending lock 90 days.");
        auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        now += 90 * 86400;
        _lock_until = std::to_string(now);
        _lock_seal = seal(_lock_until);

        HKEY hKey;
        if (RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\JustGivenUp", 0, NULL, 0, KEY_WRITE, NULL, &hKey, NULL) == ERROR_SUCCESS) {
            std::wstring wval = std::to_wstring(now);
            RegSetValueExW(hKey, L"lock_until", 0, REG_SZ, (const BYTE*)wval.c_str(), (DWORD)(wval.size() + 1) * 2);
            std::wstring wseal = std::wstring(_lock_seal.begin(), _lock_seal.end());
            RegSetValueExW(hKey, L"lock_seal", 0, REG_SZ, (const BYTE*)wseal.c_str(), (DWORD)(wseal.size() + 1) * 2);
            RegCloseKey(hKey);
        }
    }
}

void Lock::set_lock(int days_from_now) {
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    now += days_from_now * 86400;
    _lock_until = std::to_string(now);
    _lock_seal = seal(_lock_until);

    HKEY hKey;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\JustGivenUp", 0, NULL, 0, KEY_WRITE, NULL, &hKey, NULL) == ERROR_SUCCESS) {
        std::wstring wval = std::to_wstring(now);
        RegSetValueExW(hKey, L"lock_until", 0, REG_SZ, (const BYTE*)wval.c_str(), (DWORD)(wval.size() + 1) * 2);
        std::wstring wseal = std::wstring(_lock_seal.begin(), _lock_seal.end());
        RegSetValueExW(hKey, L"lock_seal", 0, REG_SZ, (const BYTE*)wseal.c_str(), (DWORD)(wseal.size() + 1) * 2);
        RegCloseKey(hKey);
    }
    Log::instance().info("[LOCK] Lock set for " + std::to_string(days_from_now) + " days");
}

void Lock::remove_lock() {
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\JustGivenUp", 0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {
        RegDeleteValueW(hKey, L"lock_until");
        RegDeleteValueW(hKey, L"lock_seal");
        RegCloseKey(hKey);
    }
    _lock_until.clear();
    _lock_seal.clear();
    Log::instance().info("[LOCK] Removed");
}

int Lock::remaining_seconds() {
    if (!is_locked()) return 0;
    auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    try {
        long long lock_time = std::stoll(_lock_until);
        return std::max(0LL, lock_time - now);
    } catch (...) {
        return 0;
    }
}

std::string Lock::until_str() {
    if (_lock_until.empty()) return "";
    try {
        time_t t = (time_t)std::stoll(_lock_until);
        struct tm local;
        localtime_s(&local, &t);
        char buf[64];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M", &local);
        return buf;
    } catch (...) {
        return "";
    }
}
