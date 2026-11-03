#pragma once

#include "smarthome/device_registry.hpp"

#include <optional>
#include <string>

namespace smarthome {

struct Command {
    std::string action;
    std::optional<int> value;

    static Command parse(const Device& device, const std::string& action, const std::optional<std::string>& value);
    std::string to_json() const;
};

struct DeviceState {
    bool online{true};
    bool on{false};
    int level{0};
    int target_c{20};

    void apply(const Device& device, const Command& command);
    std::string to_json(const Device& device) const;
};

Command parse_command_json(const Device& device, const std::string& payload);
std::string topic_for(const Device& device, const std::string& suffix);

} // namespace smarthome
