#include "image_analysis.hpp"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace image_inspector {
namespace {
constexpr std::uintmax_t kMaxBytes = 16U * 1024U * 1024U;
constexpr std::uint64_t kMaxPixels = 16U * 1024U * 1024U;
constexpr std::uint32_t kMaxDimension = 8192;

std::uint32_t be32(const std::vector<unsigned char>& bytes, std::size_t offset) {
    return (static_cast<std::uint32_t>(bytes.at(offset)) << 24U)
        | (static_cast<std::uint32_t>(bytes.at(offset + 1)) << 16U)
        | (static_cast<std::uint32_t>(bytes.at(offset + 2)) << 8U)
        | static_cast<std::uint32_t>(bytes.at(offset + 3));
}

void check_dimensions(std::uint32_t width, std::uint32_t height) {
    if (width == 0 || height == 0 || width > kMaxDimension || height > kMaxDimension
        || static_cast<std::uint64_t>(width) * height > kMaxPixels) {
        throw std::runtime_error("image dimensions exceed the configured limit");
    }
}

std::pair<std::uint32_t, std::uint32_t> preflight(const std::vector<unsigned char>& bytes) {
    constexpr unsigned char png_signature[] = {137, 80, 78, 71, 13, 10, 26, 10};
    if (bytes.size() >= 24 && std::equal(std::begin(png_signature), std::end(png_signature), bytes.begin())) {
        auto width = be32(bytes, 16);
        auto height = be32(bytes, 20);
        check_dimensions(width, height);
        return {width, height};
    }
    if (bytes.size() < 4 || bytes[0] != 0xff || bytes[1] != 0xd8) throw std::runtime_error("only PNG and JPEG images are supported");
    std::size_t offset = 2;
    while (offset + 4 <= bytes.size()) {
        if (bytes[offset++] != 0xff) throw std::runtime_error("malformed JPEG marker stream");
        while (offset < bytes.size() && bytes[offset] == 0xff) ++offset;
        if (offset >= bytes.size()) break;
        unsigned char marker = bytes[offset++];
        if (marker == 0xd9 || marker == 0xda) break;
        if (marker == 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
        if (offset + 2 > bytes.size()) break;
        std::size_t length = (static_cast<std::size_t>(bytes[offset]) << 8U) | bytes[offset + 1];
        if (length < 2 || offset + length > bytes.size()) throw std::runtime_error("malformed JPEG segment");
        bool is_frame = (marker >= 0xc0 && marker <= 0xc3) || (marker >= 0xc5 && marker <= 0xc7)
            || (marker >= 0xc9 && marker <= 0xcb) || (marker >= 0xcd && marker <= 0xcf);
        if (is_frame) {
            if (length < 7) throw std::runtime_error("malformed JPEG frame header");
            std::uint32_t height = (static_cast<std::uint32_t>(bytes[offset + 3]) << 8U) | bytes[offset + 4];
            std::uint32_t width = (static_cast<std::uint32_t>(bytes[offset + 5]) << 8U) | bytes[offset + 6];
            check_dimensions(width, height);
            return {width, height};
        }
        offset += length;
    }
    throw std::runtime_error("JPEG dimensions not found before image data");
}
} // namespace

Summary inspect(const std::filesystem::path& path) {
    auto status = std::filesystem::symlink_status(path);
    if (!std::filesystem::is_regular_file(status)) throw std::runtime_error("input must be a regular, non-symlink file");
    auto size = std::filesystem::file_size(path);
    if (size == 0 || size > kMaxBytes) throw std::runtime_error("image file must be between 1 byte and 16 MiB");
    std::ifstream input(path, std::ios::binary);
    std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if (input.bad() || bytes.size() != size) throw std::runtime_error("could not read complete image file");
    auto [expected_width, expected_height] = preflight(bytes);
    cv::Mat image = cv::imdecode(bytes, cv::IMREAD_COLOR);
    if (image.empty() || image.cols != static_cast<int>(expected_width) || image.rows != static_cast<int>(expected_height)) {
        throw std::runtime_error("image data is invalid or does not match its header");
    }
    cv::Mat gray;
    cv::cvtColor(image, gray, cv::COLOR_BGR2GRAY);
    cv::Scalar mean;
    cv::Scalar deviation;
    cv::meanStdDev(gray, mean, deviation);
    cv::Mat bright;
    cv::threshold(gray, bright, 200, 255, cv::THRESH_BINARY);
    auto bright_pixels = static_cast<std::uint64_t>(cv::countNonZero(bright));
    return {image.cols, image.rows, image.channels(), mean[0], deviation[0], bright_pixels};
}
} // namespace image_inspector
