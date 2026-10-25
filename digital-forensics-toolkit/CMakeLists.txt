cmake_minimum_required(VERSION 3.16)
project(evidence_tool LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)

add_library(forensics src/forensics.cpp)
target_include_directories(forensics PUBLIC include)
target_link_libraries(forensics PUBLIC OpenSSL::Crypto)
target_compile_options(forensics PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(forensic-tool src/main.cpp)
target_link_libraries(forensic-tool PRIVATE forensics)
target_compile_options(forensic-tool PRIVATE -Wall -Wextra -Wpedantic -Werror)

enable_testing()
add_executable(forensics-tests tests/forensics_test.cpp)
target_link_libraries(forensics-tests PRIVATE forensics)
target_compile_options(forensics-tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_test(NAME forensics-tests COMMAND forensics-tests)
