#define _POSIX_C_SOURCE 200809L
#include "proc_snapshot.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define CHECK(condition) do { if (!(condition)) { fprintf(stderr, "check failed at line %d: %s\n", __LINE__, #condition); return 1; } } while (0)

int main(void) {
    char line[1024] = "42 (worker ) pool) R 7";
    for (int field = 5; field <= 22; ++field) {
        (void)snprintf(line + strlen(line), sizeof(line) - strlen(line), " 0");
    }
    (void)snprintf(line + strlen(line), sizeof(line) - strlen(line), " 4096 3");
    process_snapshot parsed;
    CHECK(parse_proc_stat(line, &parsed) == 0);
    CHECK(parsed.pid == 42 && parsed.parent_pid == 7 && parsed.state == 'R');
    CHECK(strcmp(parsed.command, "worker ) pool") == 0 && parsed.virtual_bytes == 4096);
    CHECK(parsed.resident_bytes == 3U * (uint64_t)sysconf(_SC_PAGESIZE));

    CHECK(parse_proc_stat("42 (broken) R 7", &parsed) != 0);
    CHECK(parse_proc_stat("not-a-pid (worker) R 7", &parsed) != 0);
    char error[192];
    CHECK(read_process_snapshot(getpid(), &parsed, error, sizeof(error)) == 0);
    CHECK(parsed.pid == getpid());
    memory_snapshot memory;
    CHECK(read_memory_snapshot(&memory, error, sizeof(error)) == 0);
    CHECK(memory.total_bytes > 0 && memory.available_bytes <= memory.total_bytes);
    return 0;
}
