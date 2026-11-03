#include "checksum.h"
#include <assert.h>

int main(void) {
    const uint8_t known[] = {0x00, 0x01, 0xf2, 0x03, 0xf4, 0xf5, 0xf6, 0xf7};
    assert(internet_checksum(known, sizeof known) == 0x220d);
    assert(internet_checksum(known, 0) == 0xffff);
    assert(internet_checksum(0, sizeof known) == 0xffff);
    return 0;
}
