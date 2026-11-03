#include "checksum.h"

uint16_t internet_checksum(const uint8_t *data, size_t length) {
    uint32_t sum = 0;
    size_t i = 0;
    if (data == NULL) return 0xffffu;
    while (i + 1 < length) {
        sum += ((uint32_t)data[i] << 8) | data[i + 1];
        i += 2;
    }
    if (i < length) sum += (uint32_t)data[i] << 8;
    while ((sum >> 16) != 0) sum = (sum & 0xffffu) + (sum >> 16);
    return (uint16_t)(~sum & 0xffffu);
}
