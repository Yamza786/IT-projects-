#pragma once

#include <cstdint>
#include <filesystem>

namespace image_inspector {

struct Summary {
    int width;
    int height;
    int channels;
    double mean_luminance;
    double standard_deviation;
    std::uint64_t bright_pixels;
};

Summary inspect(const std::filesystem::path& path);

} // namespace image_inspector
