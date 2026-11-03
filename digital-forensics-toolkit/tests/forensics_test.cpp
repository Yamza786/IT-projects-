#include "forensics.hpp"

#include <sys/stat.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>

namespace {

void check(bool condition, const std::string& message) {
  if (!condition) throw std::runtime_error(message);
}

std::string read_file(const std::filesystem::path& path) {
  std::ifstream input(path);
  return std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

template <typename Function>
void expect_throw(Function&& function, const std::string& message) {
  bool threw = false;
  try { function(); } catch (const std::exception&) { threw = true; }
  check(threw, message);
}

}  // namespace

int main() {
  try {
    auto pattern = (std::filesystem::current_path() / "forensics-tests-XXXXXX").string();
    std::vector<char> temporary(pattern.begin(), pattern.end());
    temporary.push_back('\0');
    const char* created = ::mkdtemp(temporary.data());
    check(created != nullptr, "could not create test directory");
    const std::filesystem::path base(created);
    const auto root = base / "evidence";
    std::filesystem::create_directory(root);
    const auto evidence = root / "note.txt";
    { std::ofstream output(evidence); output << "abc"; }

    const auto record = forensics::fingerprint_file(evidence, "note.txt");
    check(record.size_bytes == 3, "incorrect evidence size");
    check(record.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
          "SHA-256 digest did not match the known fixture");
    check(read_file(evidence) == "abc", "hashing modified evidence");
    check(forensics::escape_json("a\"b\n") == "a\\\"b\\n", "JSON string escaping failed");

    const auto link = root / "link.txt";
    std::filesystem::create_symlink(evidence.filename(), link);
    expect_throw([&] { (void)forensics::collect_evidence(root); }, "symbolic link was accepted");
    std::filesystem::remove(link);
    const auto root_link = base / "evidence-link";
    std::filesystem::create_directory_symlink(root, root_link);
    expect_throw([&] { (void)forensics::collect_evidence(root_link); }, "symbolic-link evidence root was accepted");

    const auto manifest = base / "case.json";
    forensics::write_manifest({root, manifest, "CASE-7", "Examiner \"A\""});
    const auto contents = read_file(manifest);
    check(contents.find("evidence-manifest-v1") != std::string::npos, "manifest version missing");
    check(contents.find("CASE-7") != std::string::npos, "case identifier missing");
    check(contents.find("note.txt") != std::string::npos, "relative evidence path missing");
    check(contents.find(record.sha256) != std::string::npos, "evidence digest missing");
    struct stat metadata {};
    check(::stat(manifest.c_str(), &metadata) == 0 && (metadata.st_mode & 0777) == 0600,
          "manifest permissions are not private");
    expect_throw([&] { forensics::write_manifest({root, root / "manifest.json", "CASE-8", "Examiner"}); },
                 "manifest was allowed inside the evidence root");
    expect_throw([&] { forensics::write_manifest({root, manifest, "CASE-8", "Examiner"}); },
                 "existing manifest was overwritten");

    std::filesystem::remove_all(base);
    std::cout << "forensics checks passed\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "forensics test failed: " << error.what() << '\n';
    return 1;
  }
}
