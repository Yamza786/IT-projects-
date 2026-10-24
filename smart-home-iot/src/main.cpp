#include "smarthome/command.hpp"
#include "smarthome/device_registry.hpp"
#include "smarthome/mqtt_session.hpp"

#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>

namespace {

volatile std::sig_atomic_t stop_requested = 0;

void handle_signal(int) {
    stop_requested = 1;
}

std::string environment(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value == nullptr ? fallback : value;
}

void usage() {
    std::cerr << "Usage:\n"
              << "  smarthome list\n"
              << "  smarthome publish <device-id> <on|off|level|target> [value]\n"
              << "  smarthome monitor [seconds]\n"
              << "  smarthome simulate <device-id>\n";
}

smarthome::DeviceRegistry load_registry() {
    return smarthome::DeviceRegistry::load(environment("SMART_HOME_DEVICES", "config/devices.csv"));
}

void publish_command(int argc, char** argv) {
    if (argc < 4 || argc > 5) throw std::invalid_argument("publish expects a device, action, and optional value");
    const auto registry = load_registry();
    const auto& device = registry.require(argv[2]);
    const std::optional<std::string> value = argc == 5
            ? std::optional<std::string>(argv[4]) : std::nullopt;
    const auto command = smarthome::Command::parse(device, argv[3], value);
    smarthome::MqttSession session(smarthome::MqttSettings::from_environment());
    session.connect();
    const auto topic = smarthome::topic_for(device, "command");
    session.publish(topic, command.to_json(), true);
    std::cout << "Published retained command for " << device.id << " on " << topic << '\n';
}

void monitor(int argc, char** argv) {
    int seconds = 10;
    if (argc == 3) {
        seconds = std::stoi(argv[2]);
        if (seconds < 1 || seconds > 300) throw std::invalid_argument("monitor seconds must be from 1 to 300");
    }
    smarthome::MqttSession session(smarthome::MqttSettings::from_environment());
    session.set_message_handler([](const std::string& topic, const std::string& payload) {
        std::cout << topic << ' ' << payload << std::endl;
    });
    session.connect();
    session.subscribe("portfolio/smarthome/v1/devices/+/status");
    std::this_thread::sleep_for(std::chrono::seconds(seconds));
}

void simulate(int argc, char** argv) {
    if (argc != 3) throw std::invalid_argument("simulate expects one device id");
    const auto registry = load_registry();
    const auto& device = registry.require(argv[2]);
    smarthome::DeviceState state;
    smarthome::MqttSession session(smarthome::MqttSettings::from_environment());
    session.set_message_handler([&](const std::string& topic, const std::string& payload) {
        if (topic != smarthome::topic_for(device, "command")) return;
        try {
            state.apply(device, smarthome::parse_command_json(device, payload));
            const auto status_topic = smarthome::topic_for(device, "status");
            session.publish_async(status_topic, state.to_json(device), true);
            std::cout << status_topic << ' ' << state.to_json(device) << std::endl;
        } catch (const std::exception& exception) {
            std::cerr << "Rejected device command: " << exception.what() << '\n';
        }
    });
    session.connect();
    session.subscribe(smarthome::topic_for(device, "command"));
    session.publish(smarthome::topic_for(device, "status"), state.to_json(device), true);
    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);
    std::cout << "Simulating " << device.id << "; press Ctrl-C to stop.\n";
    while (!stop_requested) std::this_thread::sleep_for(std::chrono::milliseconds(100));
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            usage();
            return 2;
        }
        const std::string mode = argv[1];
        if (mode == "list" && argc == 2) {
            for (const auto& [id, device] : load_registry().devices())
                std::cout << id << '\t' << device.kind << '\t' << device.room << '\n';
        } else if (mode == "publish") publish_command(argc, argv);
        else if (mode == "monitor" && argc <= 3) monitor(argc, argv);
        else if (mode == "simulate") simulate(argc, argv);
        else {
            usage();
            return 2;
        }
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "smarthome: " << exception.what() << '\n';
        return 1;
    }
}
