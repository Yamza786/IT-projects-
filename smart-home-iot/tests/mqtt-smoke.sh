#!/bin/sh
set -eu

binary=${1:-./build/smarthome}
port=${SMART_HOME_TEST_PORT:-18884}
temporary=$(mktemp -d)
broker_pid=
simulator_pid=

cleanup() {
    if [ -n "$simulator_pid" ]; then kill "$simulator_pid" 2>/dev/null || true; wait "$simulator_pid" 2>/dev/null || true; fi
    if [ -n "$broker_pid" ]; then kill "$broker_pid" 2>/dev/null || true; wait "$broker_pid" 2>/dev/null || true; fi
    rm -rf "$temporary"
}
trap cleanup EXIT INT TERM

export SMART_HOME_MQTT_URI="tcp://127.0.0.1:$port"
export SMART_HOME_ALLOW_ANONYMOUS_LOCAL=1
mosquitto -p "$port" -v >"$temporary/broker.log" 2>&1 &
broker_pid=$!

ready=0
attempt=0
while [ "$attempt" -lt 30 ]; do
    if mosquitto_pub -h 127.0.0.1 -p "$port" -t portfolio/smarthome/test/health -m ready >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then cat "$temporary/broker.log"; exit 1; fi

"$binary" simulate demo-lamp >"$temporary/simulator.log" 2>&1 &
simulator_pid=$!
sleep 1
"$binary" publish demo-lamp on
output=$("$binary" monitor 2)
printf '%s\n' "$output" | grep -F '"on":true' >/dev/null
printf '%s\n' 'MQTT broker simulator smoke: passed'
