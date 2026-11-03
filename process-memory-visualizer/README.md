# Process and Memory Visualizer

`proc-viz` is a read-only Linux `/proc` snapshot utility written in C. It reports one selected process's PID, parent, state, command, virtual size and resident memory, plus system total/available memory, as JSON.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/proc-viz          # inspect this process
./build/proc-viz 1        # inspect PID 1 when permitted
```

The parser handles command names containing spaces and closing parentheses, validates numeric fields, and bounds `/proc` input. CTest checks a synthetic `/proc/PID/stat` fixture and live read-only snapshots. CI builds with warnings as errors and runs tests.

## Platform and safety limits

This version requires Linux procfs with `stat` fields and `/proc/meminfo`; Android, containers, and hardened Linux systems may hide or restrict process records. It never signals, attaches to, or modifies a process. The JSON is a point-in-time estimate, not a profiler or a complete view of container memory accounting.
