#include "image_analysis.hpp"

#include <exception>
#include <iomanip>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "Usage: image-inspect IMAGE.png|IMAGE.jpg\n";
        return 2;
    }
    try {
        const auto summary = image_inspector::inspect(argv[1]);
        std::cout << std::fixed << std::setprecision(2)
                  << "{\"width\":" << summary.width
                  << ",\"height\":" << summary.height
                  << ",\"channels\":" << summary.channels
                  << ",\"mean_luminance\":" << summary.mean_luminance
                  << ",\"standard_deviation\":" << summary.standard_deviation
                  << ",\"pixels_luminance_over_200\":" << summary.bright_pixels << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "image-inspect: " << error.what() << '\n';
        return 1;
    }
}
