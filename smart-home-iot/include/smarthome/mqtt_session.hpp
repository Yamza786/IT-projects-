#pragma once

#include <mqtt/async_client.h>

#include <functional>
#include <string>

namespace smarthome {

struct MqttSettings {
    std::string uri;
    std::string username;
    std::string password;
    std::string ca_file;

    static MqttSettings from_environment();
};

class MqttSession final : public mqtt::callback {
public:
    using MessageHandler = std::function<void(const std::string&, const std::string&)>;

    explicit MqttSession(const MqttSettings& settings);
    ~MqttSession() override;
    void connect();
    void subscribe(const std::string& topic);
    void publish(const std::string& topic, const std::string& payload, bool retained = false);
    void publish_async(const std::string& topic, const std::string& payload, bool retained = false);
    void set_message_handler(MessageHandler handler);
    void disconnect();
    void connection_lost(const std::string& cause) override;
    void message_arrived(mqtt::const_message_ptr message) override;

private:
    mqtt::async_client client_;
    mqtt::connect_options options_;
    MessageHandler handler_;
};

} // namespace smarthome
