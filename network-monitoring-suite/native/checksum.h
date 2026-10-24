#ifndef NETWORK_MONITOR_CHECKSUM_H
#define NETWORK_MONITOR_CHECKSUM_H
#include <stddef.h>
#include <stdint.h>
/* Internet checksum helper for offline packet fixtures; performs no network I/O. */
uint16_t internet_checksum(const uint8_t *data, size_t length);
#endif
