#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace forensics {

struct FileRecord {
  std::string path;
  std::string sha256;
  std::uint64_t size_bytes{};
  std::uint32_t mode{};
  std::int64_t modified_seconds{};
  std::int64_t modified_nanoseconds{};
};

struct ManifestOptions {
  std::filesystem::path root;
  std::filesystem::path output;
  std::string case_id;
  std::string examiner;
};

FileRecord fingerprint_file(const std::filesystem::path& path, std::string relative_path = {});
std::string inspect_file(const std::filesystem::path& path);
std::vector<FileRecord> collect_evidence(const std::filesystem::path& root);
void write_manifest(const ManifestOptions& options);
std::string escape_json(const std::string& value);

}  // namespace forensics
