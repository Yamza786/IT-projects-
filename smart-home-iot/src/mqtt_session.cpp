#include "smarthome/mqtt_session.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <mqtt/ssl_options.h>
#include <random>
#include <stdexcept>
#include <utility>

namespace smarthome {
namespace {

std::string environment(const char* name, const std::string& fallback = {}) {
    const char* value = std::getenv(name);
    return value == nullptr ? fallback : value;
}

std::string client_id() {
    std::random_device random;
    return "home-node-" + std::to_string(random()) + std::to_string(random());
}

bool local_endpoint(const std::string& uri) {
    return uri.starts_with("tcp://localhost:") || uri.starts_with("tcp://127.0.0.1:")
            || uri.starts_with("tcp://[::1]:");
}

} // namespace

MqttSettings MqttSettings::from_environment() {
    MqttSettings settings{
        environment("SMART_HOME_MQTT_URI", "tcp://127.0.0.1:1883"),
        environment("SMART_HOME_MQTT_USERNAME"),
        environment("SMART_HOME_MQTT_PASSWORD"),
        environment("SMART_HOME_MQTT_CA_FILE")
    };
    const bool tls = settings.uri.starts_with("ssl://");
    const bool local = local_endpoint(settings.uri);
    const bool anonymous_local = environment("SMART_HOME_ALLOW_ANONYMOUS_LOCAL") == "1";
    if (settings.username.empty() != settings.password.empty())
        throw std::runtime_error("Set both MQTT username and password, or neither");
    if (!tls && !local)
        throw std::runtime_error("Remote MQTT brokers must use ssl:// with certificate verification");
    if (tls && (settings.ca_file.empty() || !std::filesystem::is_regular_file(settings.ca_file)))
        throw std::runtime_error("Set SMART_HOME_MQTT_CA_FILE to a readable broker trust bundle for TLS");
    if (settings.username.empty() && !(local && anonymous_local))
        throw std::runtime_error("MQTT credentials are required; anonymous access is allowed only for explicit local development");
    if (!settings.uri.starts_with("tcp://") && !tls)
        throw std::runtime_error("MQTT URI must start with tcp:// or ssl://");
    return settings;
}

MqttSession::MqttSession(const MqttSettings& settings)
    : client_(settings.uri, client_id()) {
    options_.set_clean_session(true);
    if (!settings.username.empty()) {
        options_.set_user_name(settings.username);
        options_.set_password(settings.password);
    }
    if (settings.uri.starts_with("ssl://")) {
        mqtt::ssl_options ssl;
        ssl.set_trust_store(settings.ca_file);
        ssl.set_enable_server_cert_auth(true);
        options_.set_ssl(ssl);
    }
}

MqttSession::~MqttSession() {
    try {
        disconnect();
    } catch (const mqtt::exception& exception) {
        std::cerr << "MQTT disconnect: " << exception.what() << '\n';
    }
}

void MqttSession::connect() {
    client_.set_callback(*this);
    client_.connect(options_)->wait();
}

void MqttSession::subscribe(const std::string& topic) {
    client_.subscribe(topic, 1)->wait();
}

void MqttSession::publish(const std::string& topic, const std::string& payload, bool retained) {
    client_.publish(topic, payload, 1, retained)->wait();
}

void MqttSession::publish_async(const std::string& topic, const std::string& payload, bool retained) {
    static_cast<void>(client_.publish(topic, payload, 1, retained));
}

void MqttSession::set_message_handler(MessageHandler handler) {
    handler_ = std::move(handler);
}

void MqttSession::disconnect() {
    if (client_.is_connected()) client_.disconnect()->wait();
}

void MqttSession::connection_lost(const std::string& cause) {
    std::cerr << "MQTT connection lost";
    if (!cause.empty()) std::cerr << ": " << cause;
    std::cerr << '\n';
}

void MqttSession::message_arrived(mqtt::const_message_ptr message) {
    if (handler_) handler_(message->get_topic(), message->to_string());
}

} // namespace smarthome
