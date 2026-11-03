#pragma once

#include <filesystem>
#include <map>
#include <string>

namespace smarthome {

struct Device {
    std::string id;
    std::string kind;
    std::string room;
};

class DeviceRegistry {
public:
    static DeviceRegistry load(const std::filesystem::path& path);
    const Device& require(const std::string& id) const;
    const std::map<std::string, Device>& devices() const noexcept;

private:
    std::map<std::string, Device> devices_;
};

bool valid_identifier(const std::string& value) noexcept;

} // namespace smarthome
