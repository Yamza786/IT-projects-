#define _POSIX_C_SOURCE 200809L
#include "proc_snapshot.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void print_json_string(const char *value) {
    putchar('"');
    for (const unsigned char *cursor = (const unsigned char *)value; *cursor != '\0'; ++cursor) {
        if (*cursor == '"' || *cursor == '\\') { putchar('\\'); putchar(*cursor); }
        else if (*cursor < 0x20) printf("\\u%04x", (unsigned int)*cursor);
        else putchar(*cursor);
    }
    putchar('"');
}

int main(int argc, char **argv) {
    pid_t pid = getpid();
    if (argc > 2) { fprintf(stderr, "Usage: %s [PID]\n", argv[0]); return 2; }
    if (argc == 2) {
        char *end = NULL;
        errno = 0;
        long value = strtol(argv[1], &end, 10);
        if (errno != 0 || end == argv[1] || *end != '\0' || value < 1 || value > INT32_MAX) {
            fprintf(stderr, "proc-viz: PID must be a positive decimal integer\n"); return 2;
        }
        pid = (pid_t)value;
    }
    char error[192];
    process_snapshot process;
    memory_snapshot memory;
    if (read_process_snapshot(pid, &process, error, sizeof(error)) != 0) {
        fprintf(stderr, "proc-viz: %s\n", error); return 1;
    }
    if (read_memory_snapshot(&memory, error, sizeof(error)) != 0) {
        fprintf(stderr, "proc-viz: %s\n", error); return 1;
    }
    printf("{\"process\":{\"pid\":%ld,\"parent_pid\":%ld,\"state\":", (long)process.pid, (long)process.parent_pid);
    char state[2] = {process.state, '\0'};
    print_json_string(state);
    printf(",\"command\":"); print_json_string(process.command);
    printf(",\"virtual_bytes\":%" PRIu64 ",\"resident_bytes\":%" PRIu64 "},", process.virtual_bytes, process.resident_bytes);
    printf("\"system_memory\":{\"total_bytes\":%" PRIu64 ",\"available_bytes\":%" PRIu64 "}}\n", memory.total_bytes, memory.available_bytes);
    return 0;
}
