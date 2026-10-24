#include "smarthome/command.hpp"

#include <charconv>
#include <regex>
#include <stdexcept>

namespace smarthome {
namespace {

int parse_integer(const std::string& text) {
    int result = 0;
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), result);
    if (error != std::errc{} || end != text.data() + text.size())
        throw std::invalid_argument("Command value must be an integer");
    return result;
}

} // namespace

Command Command::parse(const Device& device, const std::string& action, const std::optional<std::string>& raw_value) {
    if (action == "on" || action == "off") {
        if (raw_value) throw std::invalid_argument("on/off commands do not take a value");
        if (device.kind == "thermostat") throw std::invalid_argument("Thermostats do not support on/off commands");
        return {action, std::nullopt};
    }
    if (action == "level") {
        if (device.kind != "light") throw std::invalid_argument("level is only valid for light devices");
        if (!raw_value) throw std::invalid_argument("level requires a value from 0 to 100");
        const int level = parse_integer(*raw_value);
        if (level < 0 || level > 100) throw std::invalid_argument("level must be between 0 and 100");
        return {"set_level", level};
    }
    if (action == "target") {
        if (device.kind != "thermostat") throw std::invalid_argument("target is only valid for thermostats");
        if (!raw_value) throw std::invalid_argument("target requires a Celsius value from 5 to 35");
        const int target = parse_integer(*raw_value);
        if (target < 5 || target > 35) throw std::invalid_argument("target must be between 5 and 35 Celsius");
        return {"set_target", target};
    }
    throw std::invalid_argument("Unsupported action: " + action);
}

std::string Command::to_json() const {
    if (value) return "{\"command\":\"" + action + "\",\"value\":" + std::to_string(*value) + "}";
    return "{\"command\":\"" + action + "\"}";
}

Command parse_command_json(const Device& device, const std::string& payload) {
    static const std::regex schema(R"json(^\{"command":"([a-z_]+)"(?:,"value":(-?[0-9]+))?\}$)json");
    std::smatch match;
    if (!std::regex_match(payload, match, schema)) throw std::invalid_argument("Malformed command JSON");
    const std::string action = match[1].str();
    const auto value = match[2].matched ? std::optional<std::string>(match[2].str()) : std::nullopt;
    if (action == "set_level") return Command::parse(device, "level", value);
    if (action == "set_target") return Command::parse(device, "target", value);
    return Command::parse(device, action, value);
}

void DeviceState::apply(const Device& device, const Command& command) {
    if (command.action == "on") on = true;
    else if (command.action == "off") on = false;
    else if (command.action == "set_level" && device.kind == "light" && command.value) {
        level = *command.value;
        on = level > 0;
    } else if (command.action == "set_target" && device.kind == "thermostat" && command.value) {
        target_c = *command.value;
    } else {
        throw std::invalid_argument("Command is incompatible with device");
    }
}

std::string DeviceState::to_json(const Device& device) const {
    if (device.kind == "thermostat") {
        return "{\"device\":\"" + device.id + "\",\"room\":\"" + device.room
                + "\",\"online\":true,\"target_c\":" + std::to_string(target_c) + "}";
    }
    return "{\"device\":\"" + device.id + "\",\"room\":\"" + device.room
            + "\",\"online\":true,\"on\":" + (on ? "true" : "false")
            + ",\"level\":" + std::to_string(level) + "}";
}

std::string topic_for(const Device& device, const std::string& suffix) {
    if (suffix != "command" && suffix != "status") throw std::invalid_argument("Unsupported topic suffix");
    return "portfolio/smarthome/v1/devices/" + device.id + "/" + suffix;
}

} // namespace smarthome
