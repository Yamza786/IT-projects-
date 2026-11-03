#include "smarthome/device_registry.hpp"

#include <cctype>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace smarthome {
namespace {

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::vector<std::string> split_row(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (true) {
        const auto comma = line.find(',', start);
        fields.push_back(trim(line.substr(start, comma == std::string::npos ? comma : comma - start)));
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return fields;
}

} // namespace

bool valid_identifier(const std::string& value) noexcept {
    if (value.empty() || value.size() > 48) return false;
    for (const unsigned char character : value) {
        if (!std::isalnum(character) && character != '-' && character != '_') return false;
    }
    return true;
}

DeviceRegistry DeviceRegistry::load(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot read device registry: " + path.string());
    DeviceRegistry registry;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        line = trim(line);
        if (line.empty() || line.starts_with('#') || line == "id,kind,room") continue;
        const auto fields = split_row(line);
        if (fields.size() != 3 || !valid_identifier(fields[0]) || !valid_identifier(fields[2]))
            throw std::runtime_error("Invalid registry row " + std::to_string(line_number));
        if (fields[1] != "light" && fields[1] != "switch" && fields[1] != "thermostat")
            throw std::runtime_error("Unsupported device kind at row " + std::to_string(line_number));
        const Device device{fields[0], fields[1], fields[2]};
        if (!registry.devices_.emplace(device.id, device).second)
            throw std::runtime_error("Duplicate device id at row " + std::to_string(line_number));
    }
    if (registry.devices_.empty()) throw std::runtime_error("Device registry contains no devices");
    return registry;
}

const Device& DeviceRegistry::require(const std::string& id) const {
    const auto found = devices_.find(id);
    if (found == devices_.end()) throw std::runtime_error("Unknown device id: " + id);
    return found->second;
}

const std::map<std::string, Device>& DeviceRegistry::devices() const noexcept {
    return devices_;
}

} // namespace smarthome
