#define _POSIX_C_SOURCE 200809L
#include "proc_snapshot.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_PROC_LINE 65536

static void set_error(char *error, size_t size, const char *message) {
    if (error != NULL && size > 0) (void)snprintf(error, size, "%s", message);
}

static int parse_signed(const char *value, long long *result) {
    char *end = NULL;
    errno = 0;
    long long parsed = strtoll(value, &end, 10);
    if (errno != 0 || end == value || *end != '\0') return -1;
    *result = parsed;
    return 0;
}

int parse_proc_stat(const char *line, process_snapshot *result) {
    if (line == NULL || result == NULL) return -1;
    char *open = strchr(line, '(');
    char *close = strrchr(line, ')');
    if (open == NULL || close == NULL || close <= open || close[1] != ' ') return -1;
    char pid_text[32];
    size_t pid_len = (size_t)(open - line);
    while (pid_len > 0 && line[pid_len - 1] == ' ') --pid_len;
    if (pid_len == 0 || pid_len >= sizeof(pid_text)) return -1;
    memcpy(pid_text, line, pid_len); pid_text[pid_len] = '\0';
    long long pid_value;
    if (parse_signed(pid_text, &pid_value) != 0 || pid_value < 1 || pid_value > INT32_MAX) return -1;
    size_t command_len = (size_t)(close - open - 1);
    if (command_len >= sizeof(result->command)) return -1;
    char command[sizeof(result->command)];
    memcpy(command, open + 1, command_len); command[command_len] = '\0';

    char *tail = strdup(close + 2);
    if (tail == NULL) return -1;
    char *save = NULL;
    char *token = strtok_r(tail, " ", &save);
    size_t field = 3;
    long long parent = 0, virtual_size = 0, resident_pages = 0;
    int saw_resident_pages = 0;
    char state = '\0';
    while (token != NULL) {
        if (field == 3) {
            if (token[0] == '\0' || token[1] != '\0') { free(tail); return -1; }
            state = token[0];
        } else if (field == 4 || field == 23 || field == 24) {
            long long parsed;
            if (parse_signed(token, &parsed) != 0) { free(tail); return -1; }
            if (field == 4) parent = parsed;
            else if (field == 23) virtual_size = parsed;
            else { resident_pages = parsed; saw_resident_pages = 1; }
        }
        if (field == 24) break;
        ++field;
        token = strtok_r(NULL, " ", &save);
    }
    free(tail);
    if (field != 24 || !saw_resident_pages || state == '\0' || parent < 0 || virtual_size < 0 || resident_pages < 0) return -1;
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0 || (uint64_t)resident_pages > UINT64_MAX / (uint64_t)page_size) return -1;
    result->pid = (pid_t)pid_value;
    result->parent_pid = (pid_t)parent;
    result->state = state;
    memcpy(result->command, command, command_len + 1);
    result->virtual_bytes = (uint64_t)virtual_size;
    result->resident_bytes = (uint64_t)resident_pages * (uint64_t)page_size;
    return 0;
}

int read_process_snapshot(pid_t pid, process_snapshot *result, char *error, size_t error_size) {
    if (pid < 1 || result == NULL) { set_error(error, error_size, "PID must be positive"); return -1; }
    char path[64];
    int written = snprintf(path, sizeof(path), "/proc/%ld/stat", (long)pid);
    if (written < 0 || (size_t)written >= sizeof(path)) { set_error(error, error_size, "PID path is too long"); return -1; }
    FILE *file = fopen(path, "re");
    if (file == NULL) { set_error(error, error_size, "cannot read process data (process may have exited or access may be denied)"); return -1; }
    char *line = calloc(MAX_PROC_LINE + 1, 1);
    if (line == NULL) { fclose(file); set_error(error, error_size, "out of memory"); return -1; }
    size_t length = fread(line, 1, MAX_PROC_LINE, file);
    int failed = ferror(file) || length == MAX_PROC_LINE;
    fclose(file);
    int status = failed ? -1 : parse_proc_stat(line, result);
    free(line);
    if (status != 0) set_error(error, error_size, "invalid or oversized /proc stat record");
    return status;
}

int read_memory_snapshot(memory_snapshot *result, char *error, size_t error_size) {
    if (result == NULL) { set_error(error, error_size, "memory output is missing"); return -1; }
    FILE *file = fopen("/proc/meminfo", "re");
    if (file == NULL) { set_error(error, error_size, "cannot read /proc/meminfo"); return -1; }
    char line[256];
    uint64_t total_kb = 0, available_kb = 0;
    while (fgets(line, sizeof(line), file) != NULL) {
        unsigned long long value;
        if (sscanf(line, "MemTotal: %llu kB", &value) == 1) total_kb = value;
        if (sscanf(line, "MemAvailable: %llu kB", &value) == 1) available_kb = value;
    }
    int failed = ferror(file);
    fclose(file);
    if (failed || total_kb == 0 || available_kb > total_kb || total_kb > UINT64_MAX / 1024U) {
        set_error(error, error_size, "invalid /proc/meminfo values"); return -1;
    }
    result->total_bytes = total_kb * 1024U;
    result->available_bytes = available_kb * 1024U;
    return 0;
}
