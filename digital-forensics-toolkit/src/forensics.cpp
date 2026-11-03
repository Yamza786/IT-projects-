#include "forensics.hpp"

#include <openssl/evp.h>

#include <array>
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <sys/stat.h>
#include <unistd.h>
#include <utility>

namespace forensics {
namespace {

constexpr std::size_t kMaximumFiles = 5000;
constexpr std::uint64_t kMaximumBytes = 5ULL * 1024 * 1024 * 1024;

using DigestContext = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;

std::runtime_error system_error(const std::string& action, const std::filesystem::path& path) {
  return std::runtime_error(action + " " + path.string() + ": " + std::strerror(errno));
}

bool path_is_within(const std::filesystem::path& parent, const std::filesystem::path& candidate) {
  auto p = parent.begin();
  auto c = candidate.begin();
  for (; p != parent.end(); ++p, ++c) {
    if (c == candidate.end() || *p != *c) return false;
  }
  return true;
}

std::filesystem::path canonical_evidence_root(const std::filesystem::path& path) {
  if (std::filesystem::is_symlink(std::filesystem::symlink_status(path))) {
    throw std::runtime_error("evidence root cannot be a symbolic link");
  }
  const auto root = std::filesystem::canonical(path);
  if (!std::filesystem::is_directory(root)) throw std::runtime_error("evidence root must be a directory");
  return root;
}

std::string digest_fd(int fd) {
  DigestContext context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
  if (!context || EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) != 1) {
    throw std::runtime_error("could not initialize SHA-256");
  }
  std::array<unsigned char, 64 * 1024> buffer{};
  while (true) {
    const auto count = ::read(fd, buffer.data(), buffer.size());
    if (count == 0) break;
    if (count < 0) {
      if (errno == EINTR) continue;
      throw std::runtime_error(std::string("read evidence file: ") + std::strerror(errno));
    }
    if (EVP_DigestUpdate(context.get(), buffer.data(), static_cast<std::size_t>(count)) != 1) {
      throw std::runtime_error("could not update SHA-256 digest");
    }
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
  unsigned int length = 0;
  if (EVP_DigestFinal_ex(context.get(), bytes.data(), &length) != 1) {
    throw std::runtime_error("could not finish SHA-256 digest");
  }
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (unsigned int i = 0; i < length; ++i) output << std::setw(2) << static_cast<unsigned int>(bytes[i]);
  return output.str();
}

FileRecord fingerprint_open_file(const std::filesystem::path& path, std::string relative_path) {
  const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) throw system_error("cannot open evidence", path);
  struct CloseFd {
    int fd;
    ~CloseFd() { if (fd >= 0) ::close(fd); }
  } close_fd{fd};

  struct stat metadata {};
  if (::fstat(fd, &metadata) != 0) throw system_error("cannot inspect evidence", path);
  if (!S_ISREG(metadata.st_mode)) throw std::runtime_error("evidence must be a regular file: " + path.string());
  FileRecord result;
  result.path = relative_path.empty() ? path.string() : std::move(relative_path);
  result.size_bytes = static_cast<std::uint64_t>(metadata.st_size);
  result.mode = static_cast<std::uint32_t>(metadata.st_mode & 0777);
  result.modified_seconds = static_cast<std::int64_t>(metadata.st_mtim.tv_sec);
  result.modified_nanoseconds = static_cast<std::int64_t>(metadata.st_mtim.tv_nsec);
  result.sha256 = digest_fd(fd);
  struct stat after_hash {};
  if (::fstat(fd, &after_hash) != 0) throw system_error("cannot recheck evidence", path);
  if (metadata.st_dev != after_hash.st_dev || metadata.st_ino != after_hash.st_ino ||
      metadata.st_size != after_hash.st_size || metadata.st_mtim.tv_sec != after_hash.st_mtim.tv_sec ||
      metadata.st_mtim.tv_nsec != after_hash.st_mtim.tv_nsec) {
    throw std::runtime_error("evidence changed while it was being hashed: " + path.string());
  }
  return result;
}

void write_all(int fd, std::string_view contents) {
  std::size_t offset = 0;
  while (offset < contents.size()) {
    const auto count = ::write(fd, contents.data() + offset, contents.size() - offset);
    if (count < 0) {
      if (errno == EINTR) continue;
      throw std::runtime_error(std::string("write manifest: ") + std::strerror(errno));
    }
    offset += static_cast<std::size_t>(count);
  }
}

std::string now_utc() {
  const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
  std::tm utc{};
  if (gmtime_r(&now, &utc) == nullptr) throw std::runtime_error("could not format UTC timestamp");
  std::ostringstream output;
  output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
  return output.str();
}

}  // namespace

FileRecord fingerprint_file(const std::filesystem::path& path, std::string relative_path) {
  return fingerprint_open_file(path, std::move(relative_path));
}

std::string escape_json(const std::string& value) {
  std::ostringstream output;
  for (const unsigned char ch : value) {
    switch (ch) {
      case '"': output << "\\\""; break;
      case '\\': output << "\\\\"; break;
      case '\b': output << "\\b"; break;
      case '\f': output << "\\f"; break;
      case '\n': output << "\\n"; break;
      case '\r': output << "\\r"; break;
      case '\t': output << "\\t"; break;
      default:
        if (ch < 0x20) output << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<unsigned int>(ch);
        else output << ch;
    }
  }
  return output.str();
}

std::string inspect_file(const std::filesystem::path& path) {
  const auto record = fingerprint_file(path);
  std::ostringstream output;
  output << "{\"path\":\"" << escape_json(std::filesystem::canonical(path).string())
         << "\",\"sizeBytes\":" << record.size_bytes << ",\"modeOctal\":\""
         << std::oct << record.mode << std::dec << "\",\"modifiedSeconds\":"
         << record.modified_seconds << ",\"modifiedNanoseconds\":" << record.modified_nanoseconds
         << ",\"sha256\":\"" << record.sha256 << "\"}";
  return output.str();
}

std::vector<FileRecord> collect_evidence(const std::filesystem::path& root_path) {
  const auto root = canonical_evidence_root(root_path);
  std::vector<FileRecord> records;
  std::uint64_t total_bytes = 0;
  for (const auto& entry : std::filesystem::recursive_directory_iterator(root)) {
    const auto status = entry.symlink_status();
    if (std::filesystem::is_symlink(status)) throw std::runtime_error("symbolic links are not accepted: " + entry.path().string());
    if (std::filesystem::is_directory(status)) continue;
    if (!std::filesystem::is_regular_file(status)) throw std::runtime_error("unsupported evidence entry: " + entry.path().string());
    if (records.size() >= kMaximumFiles) throw std::runtime_error("evidence set exceeds 5000 files");
    auto relative = std::filesystem::relative(entry.path(), root).generic_string();
    auto record = fingerprint_open_file(entry.path(), relative);
    if (record.size_bytes > kMaximumBytes - total_bytes) throw std::runtime_error("evidence set exceeds 5 GiB");
    total_bytes += record.size_bytes;
    records.push_back(std::move(record));
  }
  std::sort(records.begin(), records.end(), [](const auto& left, const auto& right) { return left.path < right.path; });
  return records;
}

void write_manifest(const ManifestOptions& options) {
  if (options.case_id.empty() || options.examiner.empty()) throw std::runtime_error("case ID and examiner are required");
  const auto root = canonical_evidence_root(options.root);
  const auto output_parent = std::filesystem::canonical(options.output.parent_path().empty() ? "." : options.output.parent_path());
  const auto output_path = output_parent / options.output.filename();
  if (path_is_within(root, output_path)) throw std::runtime_error("manifest output must be outside the evidence root");
  const auto records = collect_evidence(root);

  std::ostringstream document;
  document << "{\n  \"format\": \"evidence-manifest-v1\",\n"
           << "  \"caseId\": \"" << escape_json(options.case_id) << "\",\n"
           << "  \"examiner\": \"" << escape_json(options.examiner) << "\",\n"
           << "  \"createdUtc\": \"" << now_utc() << "\",\n"
           << "  \"evidenceRoot\": \"" << escape_json(root.string()) << "\",\n"
           << "  \"files\": [";
  for (std::size_t i = 0; i < records.size(); ++i) {
    const auto& record = records[i];
    document << (i == 0 ? "\n" : ",\n") << "    {\"path\": \"" << escape_json(record.path)
             << "\", \"sizeBytes\": " << record.size_bytes << ", \"modeOctal\": \""
             << std::oct << record.mode << std::dec << "\", \"modifiedSeconds\": "
             << record.modified_seconds << ", \"modifiedNanoseconds\": " << record.modified_nanoseconds
             << ", \"sha256\": \"" << record.sha256 << "\"}";
  }
  document << (records.empty() ? "]\n}\n" : "\n  ]\n}\n");

  const int fd = ::open(output_path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (fd < 0) throw system_error("cannot create manifest", output_path);
  try {
    write_all(fd, document.str());
    if (::fsync(fd) != 0) throw system_error("cannot sync manifest", output_path);
    if (::close(fd) != 0) throw system_error("cannot close manifest", output_path);
  } catch (...) {
    ::close(fd);
    ::unlink(output_path.c_str());
    throw;
  }
}

}  // namespace forensics
