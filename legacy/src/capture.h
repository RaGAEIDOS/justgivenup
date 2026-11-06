#pragma once
#include <cstdint>
#include <vector>
#include <windows.h>

struct ScreenCapture {
    int width = 0;
    int height = 0;
    std::vector<uint8_t> bgra; // BGRA 32bpp
};

class Capture {
public:
    Capture();
    ~Capture();
    ScreenCapture capture();
private:
    void cleanup();
    HDC _hdc{nullptr};
};
