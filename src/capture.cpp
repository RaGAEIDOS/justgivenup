#include "capture.h"
#include "log.h"
#include <windows.h>

Capture::Capture() {
    _hdc = CreateDCW(L"DISPLAY", NULL, NULL, NULL);
    if (!_hdc)
        Log::instance().error("[CAPTURE] CreateDC failed");
}

Capture::~Capture() {
    cleanup();
}

void Capture::cleanup() {
    if (_hdc) { DeleteDC(_hdc); _hdc = nullptr; }
}

ScreenCapture Capture::capture() {
    ScreenCapture result;
    if (!_hdc) return result;

    result.width = GetDeviceCaps(_hdc, HORZRES);
    result.height = GetDeviceCaps(_hdc, VERTRES);
    int stride = result.width * 4;

    HDC memDC = CreateCompatibleDC(_hdc);
    if (!memDC) {
        Log::instance().error("[CAPTURE] CreateCompatibleDC failed");
        return result;
    }

    HBITMAP hBmp = CreateCompatibleBitmap(_hdc, result.width, result.height);
    if (!hBmp) {
        Log::instance().error("[CAPTURE] CreateCompatibleBitmap failed");
        DeleteDC(memDC);
        return result;
    }

    SelectObject(memDC, hBmp);
    BitBlt(memDC, 0, 0, result.width, result.height, _hdc, 0, 0, SRCCOPY);

    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = result.width;
    bmi.bmiHeader.biHeight = -result.height; // top-down
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    result.bgra.resize(stride * result.height);
    if (!GetDIBits(memDC, hBmp, 0, result.height, result.bgra.data(), &bmi, DIB_RGB_COLORS)) {
        Log::instance().error("[CAPTURE] GetDIBits failed");
        result.bgra.clear();
    }

    DeleteObject(hBmp);
    DeleteDC(memDC);
    return result;
}
