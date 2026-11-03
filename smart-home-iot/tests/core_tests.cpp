#include "smarthome/command.hpp"
#include "smarthome/device_registry.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

int assertions = 0;

void expect(bool condition, const std::string& message) {
    ++assertions;
    if (!condition) throw std::runtime_error("assertion failed: " + message);
}

template <typename Function>
void expect_throws(Function&& function, const std::string& message) {
    ++assertions;
    try {
        function();
    } catch (const std::exception&) {
        return;
    }
    throw std::runtime_error("expected exception: " + message);
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::invalid_argument("test needs device registry path");
        const auto registry = smarthome::DeviceRegistry::load(argv[1]);
        const auto& lamp = registry.require("demo-lamp");
        const auto& thermostat = registry.require("demo-thermostat");

        expect(registry.devices().size() == 3, "loads fixture devices");
        expect(smarthome::valid_identifier("living_room-1"), "valid device id accepted");
        expect(!smarthome::valid_identifier("../../etc"), "path traversal id rejected");
        expect(smarthome::Command::parse(lamp, "on", std::nullopt).to_json() == "{\"command\":\"on\"}",
                "switch command serialized");
        expect(smarthome::Command::parse(lamp, "level", std::string("55")).to_json()
                        == "{\"command\":\"set_level\",\"value\":55}", "light level serialized");
        expect_throws([&] { smarthome::Command::parse(lamp, "level", std::string("101")); }, "level upper bound");
        expect_throws([&] { smarthome::Command::parse(thermostat, "on", std::nullopt); }, "device type command mismatch");
        expect_throws([&] { smarthome::Command::parse(thermostat, "target", std::string("4")); }, "target lower bound");
        expect_throws([&] { smarthome::parse_command_json(lamp, "{\"command\":\"on\",\"unexpected\":1}"); },
                "extra command fields rejected");
        expect_throws([&] { registry.require("unknown-device"); }, "unknown device rejected");

        auto command = smarthome::parse_command_json(lamp, "{\"command\":\"set_level\",\"value\":40}");
        smarthome::DeviceState state;
        state.apply(lamp, command);
        expect(state.on && state.level == 40, "simulated light state updated");
        expect(smarthome::topic_for(lamp, "status") == "portfolio/smarthome/v1/devices/demo-lamp/status",
                "device topic is canonical");
        expect_throws([&] { smarthome::topic_for(lamp, "unknown"); }, "topic suffix allow-listed");

        const auto temporary = std::filesystem::temp_directory_path() / "smarthome-invalid-devices.csv";
        {
            std::ofstream file(temporary);
            file << "id,kind,room\ninvalid id,light,living-room\n";
        }
        expect_throws([&] { smarthome::DeviceRegistry::load(temporary); }, "malformed registry row rejected");
        std::filesystem::remove(temporary);

        std::cout << "Passed " << assertions << " core assertions.\n";
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << exception.what() << '\n';
        return 1;
    }
}
