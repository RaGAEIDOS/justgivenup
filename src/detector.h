#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include <onnxruntime_cxx_api.h>

struct Detection {
    std::string label;
    float score;
    float box[4]; // x, y, w, h
};

class Detector {
public:
    Detector(const std::string& model_path);
    ~Detector() = default;
    bool loaded() const { return _loaded; }
    std::vector<Detection> detect(const uint8_t* bgra, int img_w, int img_h, float threshold);
    int input_width() const { return 320; }
    int input_height() const { return 320; }
private:
    Ort::Env _env{nullptr};
    Ort::Session _session{nullptr};
    Ort::MemoryInfo _memInfo{nullptr};
    bool _loaded = false;
    std::vector<const char*> _labels;
    std::vector<Detection> postprocess(const float* raw_output, int output_count, int img_w, int img_h, float threshold);
};
