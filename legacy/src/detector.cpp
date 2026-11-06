#include "detector.h"
#include "log.h"
#include <windows.h>
#include <algorithm>
#include <cmath>
#include <cfloat>

static const char* CLASS_NAMES[] = {
    "FEMALE_GENITALIA_COVERED", "FACE_FEMALE", "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_BREAST_EXPOSED",
    "ANUS_EXPOSED", "FEET_EXPOSED", "BELLY_COVERED", "FEET_COVERED",
    "ARMPITS_COVERED", "ARMPITS_EXPOSED", "FACE_MALE", "BELLY_EXPOSED",
    "MALE_GENITALIA_EXPOSED", "ANUS_COVERED", "FEMALE_BREAST_COVERED", "BUTTOCKS_COVERED"
};
static const int NUM_CLASSES = 18;

Detector::Detector(const std::string& model_path)
    : _env(ORT_LOGGING_LEVEL_WARNING, "guardian")
{
    try {
        Ort::SessionOptions opts;
        opts.SetIntraOpNumThreads(1);
        opts.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        opts.DisableMemPattern();
        opts.EnableCpuMemArena();

        // Support session creation from file path
#ifdef _WIN32
        int wlen = MultiByteToWideChar(CP_UTF8, 0, model_path.c_str(), -1, NULL, 0);
        std::wstring wpath(wlen, L'\0');
        MultiByteToWideChar(CP_UTF8, 0, model_path.c_str(), -1, &wpath[0], wlen);
        wpath.resize(wlen - 1);
        _session = Ort::Session(_env, wpath.c_str(), opts);
#else
        _session = Ort::Session(_env, model_path.c_str(), opts);
#endif

        _memInfo = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        _labels.assign(CLASS_NAMES, CLASS_NAMES + NUM_CLASSES);
        _loaded = true;
        Log::instance().info("[DETECTOR] Model loaded: " + model_path);
    } catch (const Ort::Exception& e) {
        Log::instance().error(std::string("[DETECTOR] Failed: ") + e.what());
    }
}

std::vector<Detection> Detector::detect(const uint8_t* bgra, int img_w, int img_h, float threshold) {
    if (!_loaded) return {};

    int target_w = input_width();
    int target_h = input_height();

    // ── Preprocess ────────────────────────────────────────
    // 1. Pad to square, 2. Resize to 320x320, 3. Convert BGRA→BGR, 4. Blob (NCHW, RGB, norm)
    int max_dim = std::max(img_w, img_h);
    float scale = (float)target_w / max_dim;
    int pad_x = max_dim - img_w;
    int pad_y = max_dim - img_h;

    // Create padded buffer (square max_dim x max_dim, BGR)
    std::vector<float> padded(max_dim * max_dim * 3);
    for (int y = 0; y < img_h; y++) {
        for (int x = 0; x < img_w; x++) {
            int src_idx = (y * img_w + x) * 4; // BGRA
            int dst_idx = (y * max_dim + x) * 3; // BGR in padded
            padded[dst_idx + 0] = bgra[src_idx + 0] / 255.0f; // B
            padded[dst_idx + 1] = bgra[src_idx + 1] / 255.0f; // G
            padded[dst_idx + 2] = bgra[src_idx + 2] / 255.0f; // R
        }
    }
    // Pad area stays 0 (black)

    // Resize padded to target_w x target_h using nearest neighbor (fast)
    std::vector<float> blob(3 * target_h * target_w);
    float x_ratio = (float)max_dim / target_w;
    float y_ratio = (float)max_dim / target_h;
    for (int cy = 0; cy < target_h; cy++) {
        for (int cx = 0; cx < target_w; cx++) {
            int src_x = (int)(cx * x_ratio);
            int src_y = (int)(cy * y_ratio);
            src_x = std::min(src_x, max_dim - 1);
            src_y = std::min(src_y, max_dim - 1);
            int idx = (src_y * max_dim + src_x) * 3;
            float b = padded[idx + 0];
            float g = padded[idx + 1];
            float r = padded[idx + 2];
            // CHW format: R,G,B channels
            blob[0 * target_h * target_w + cy * target_w + cx] = r; // swapRB
            blob[1 * target_h * target_w + cy * target_w + cx] = g;
            blob[2 * target_h * target_w + cy * target_w + cx] = b;
        }
    }

    // ── Run inference ──────────────────────────────────────
    std::vector<int64_t> input_shape = {1, 3, target_h, target_w};
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        _memInfo, blob.data(), blob.size(), input_shape.data(), input_shape.size());

    const char* input_names[] = {"images"};
    const char* output_names[] = {"output0"};

    try {
        auto outputs = _session.Run(Ort::RunOptions{nullptr},
            input_names, &input_tensor, 1,
            output_names, 1);

        float* raw_data = outputs[0].GetTensorMutableData<float>();
        auto output_shape = outputs[0].GetTensorTypeAndShapeInfo().GetShape();
        int64_t total_elements = 1;
        for (auto d : output_shape) total_elements *= d;

        return postprocess(raw_data, (int)total_elements, img_w, img_h, threshold);
    } catch (const Ort::Exception& e) {
        Log::instance().error(std::string("[DETECTOR] Inference failed: ") + e.what());
        return {};
    }
}

std::vector<Detection> Detector::postprocess(const float* raw, int output_count, int img_w, int img_h, float threshold) {
    std::vector<Detection> results;

    // Output shape: [1, 22, total_cells] where total_cells depends on input size
    // For 320x320: 40*40 + 20*20 + 10*10 = 2100 cells
    int total_cells = output_count / 22;
    if (total_cells == 0) return results;

    // Transpose from [22 x cells] to [cells x 22] for easier access
    // Each row: [x_center, y_center, w, h, 18 class_scores]
    for (int i = 0; i < total_cells; i++) {
        float max_score = 0;
        int best_class = -1;
        for (int c = 0; c < NUM_CLASSES; c++) {
            float s = raw[(4 + c) * total_cells + i];
            if (s > max_score) {
                max_score = s;
                best_class = c;
            }
        }
        if (max_score >= threshold && best_class >= 0) {
            Detection det;
            det.label = _labels[best_class];
            det.score = max_score;
            // Convert from center coords + cell offset to absolute coords
            det.box[0] = raw[0 * total_cells + i]; // x_center
            det.box[1] = raw[1 * total_cells + i]; // y_center
            det.box[2] = raw[2 * total_cells + i]; // w
            det.box[3] = raw[3 * total_cells + i]; // h
            results.push_back(det);
        }
    }

    // NMS not implemented here (the raw model outputs need grid decoding)
    // But for our use case (flag NSFW/not), any detection above threshold suffices
    return results;
}
