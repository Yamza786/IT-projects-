cmake_minimum_required(VERSION 3.20)
project(smart_home_iot VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)
find_package(PahoMqttCpp 1.6 REQUIRED CONFIG)

add_library(smarthome_core
    src/command.cpp
    src/device_registry.cpp
)
target_include_directories(smarthome_core PUBLIC include)
target_compile_options(smarthome_core PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(smarthome
    src/main.cpp
    src/mqtt_session.cpp
)
target_link_libraries(smarthome PRIVATE smarthome_core PahoMqttCpp::paho-mqttpp3 Threads::Threads)
target_compile_options(smarthome PRIVATE -Wall -Wextra -Wpedantic -Werror)

enable_testing()
add_executable(smarthome_core_tests tests/core_tests.cpp)
target_link_libraries(smarthome_core_tests PRIVATE smarthome_core)
target_compile_options(smarthome_core_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_test(NAME core COMMAND smarthome_core_tests "${CMAKE_SOURCE_DIR}/config/devices.csv")
