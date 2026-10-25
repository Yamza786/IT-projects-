cmake_minimum_required(VERSION 3.20)
project(image_inspector LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(OpenCV 4 REQUIRED COMPONENTS core imgcodecs imgproc)

add_library(image_analysis src/image_analysis.cpp)
target_include_directories(image_analysis PUBLIC include)
target_link_libraries(image_analysis PUBLIC ${OpenCV_LIBS})
target_compile_options(image_analysis PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(image-inspect src/main.cpp)
target_link_libraries(image-inspect PRIVATE image_analysis)
target_compile_options(image-inspect PRIVATE -Wall -Wextra -Wpedantic -Werror)

include(CTest)
if(BUILD_TESTING)
  add_executable(image-analysis-test tests/image_analysis_test.cpp)
  target_link_libraries(image-analysis-test PRIVATE image_analysis)
  target_compile_options(image-analysis-test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  add_test(NAME image-analysis-test COMMAND image-analysis-test)
endif()
