#include "image_analysis.hpp"

#include <opencv2/imgcodecs.hpp>

#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    namespace fs = std::filesystem;
    const fs::path root = fs::temp_directory_path() / "portfolio-image-inspector-test";
    fs::remove_all(root);
    fs::create_directories(root);
    const fs::path valid = root / "fixture.png";
    cv::Mat pixels(2, 3, CV_8UC3, cv::Scalar(255, 255, 255));
    pixels.at<cv::Vec3b>(0, 0) = cv::Vec3b(0, 0, 0);
    require(cv::imwrite(valid.string(), pixels), "could not create synthetic fixture");
    auto summary = image_inspector::inspect(valid);
    require(summary.width == 3 && summary.height == 2 && summary.channels == 3, "unexpected image dimensions");
    require(summary.bright_pixels == 5, "unexpected bright pixel count");
    require(summary.mean_luminance > 200.0, "unexpected mean luminance");

    const fs::path oversized = root / "oversized.png";
    {
        std::ofstream file(oversized, std::ios::binary);
        const unsigned char header[] = {137,80,78,71,13,10,26,10, 0,0,0,13, 73,72,68,82, 0,1,0,0, 0,1,0,0};
        file.write(reinterpret_cast<const char*>(header), sizeof(header));
    }
    bool rejected_oversized = false;
    try { (void) image_inspector::inspect(oversized); }
    catch (const std::runtime_error& error) { rejected_oversized = std::string(error.what()).find("dimensions") != std::string::npos; }
    require(rejected_oversized, "oversized image dimensions were not rejected");

    const fs::path link = root / "linked.png";
    fs::create_symlink(valid, link);
    bool rejected_link = false;
    try { (void) image_inspector::inspect(link); }
    catch (const std::runtime_error&) { rejected_link = true; }
    require(rejected_link, "symlink input was not rejected");
    fs::remove_all(root);
}
