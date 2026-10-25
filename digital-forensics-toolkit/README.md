# Digital Forensics Toolkit

A small read-only evidence utility for hashing regular files, displaying metadata, and generating a private JSON chain-of-custody manifest. It never edits evidence files. It rejects symlinks and special files and bounds a manifest scan to 5,000 files and 5 GiB.

## Build and verify

Requirements: C++17, CMake, OpenSSL development headers, and Bash.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
bash tests/smoke.sh build/forensic-tool
```

On Debian or Ubuntu, install build dependencies with `sudo apt install build-essential cmake libssl-dev`.

## Commands

```sh
build/forensic-tool hash ./evidence/disk-image.raw
build/forensic-tool inspect ./evidence/event.log
scripts/collect-evidence.sh ./evidence ./case-42-manifest.json CASE-42 "Analyst Name"
```

The manifest records a UTC creation time, case identifier, examiner label, evidence-root path, and a sorted list of relative file paths with SHA-256, size, mode, and modification timestamps. It is created with mode `0600`, is never overwritten, and must be placed outside the evidence directory. The Bash wrapper only validates arguments and invokes the same C++ manifest command.

## Evidence handling limits

Use a mounted read-only source where possible and preserve the original media separately. The tool hashes regular files sequentially and checks that each file's identity, size, and modification timestamp did not change during hashing. This is a learning-scale helper, not a forensic acquisition suite or legal chain-of-custody certification. It does not image disks, recover deleted files, interpret timestamps, or prevent an external process from changing a file after a scan. Validate procedures with your organization's evidence-handling policy.

## Contribution and license

Use the repository's [contribution guidance](../CONTRIBUTING.md). This project is distributed under the repository's [license](../LICENSE).
