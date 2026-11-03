#ifndef PROC_SNAPSHOT_H
#define PROC_SNAPSHOT_H

#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>

typedef struct {
    pid_t pid;
    pid_t parent_pid;
    char state;
    char command[256];
    uint64_t virtual_bytes;
    uint64_t resident_bytes;
} process_snapshot;

typedef struct {
    uint64_t total_bytes;
    uint64_t available_bytes;
} memory_snapshot;

int parse_proc_stat(const char *line, process_snapshot *result);
int read_process_snapshot(pid_t pid, process_snapshot *result, char *error, size_t error_size);
int read_memory_snapshot(memory_snapshot *result, char *error, size_t error_size);

#endif
