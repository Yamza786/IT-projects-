# Computer Vision Application

`image-inspect` is a C++17/OpenCV command-line image analysis demo. It accepts PNG and JPEG files and reports dimensions, channel count, grayscale mean and standard deviation, and the number of pixels above luminance 200.

## Build and run

Install CMake, a C++17 compiler, and OpenCV 4 development libraries, then:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/image-inspect sample.png
```

Output is one JSON object suitable for piping into other tools. The analysis is deterministic; the threshold is a simple descriptive statistic and is not a classifier or medical/industrial decision.

## Input limits and verification

The tool rejects symlinks and non-regular files, caps input at 16 MiB, and checks PNG/JPEG dimensions before OpenCV decodes the image (maximum side 8192 pixels and maximum area 16 megapixels). CTest generates a synthetic fixture and checks statistics, symlink rejection, and oversized-header rejection. GitHub Actions builds with strict compiler warnings and runs CTest.

OpenCV decoders are complex native code; keep OpenCV patched and run the tool on untrusted images only in an appropriately isolated process. This MVP does not transform or store source images.
