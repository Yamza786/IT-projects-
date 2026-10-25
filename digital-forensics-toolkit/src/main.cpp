#include "forensics.hpp"

#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void usage() {
  std::cerr << "Usage:\n"
            << "  forensic-tool hash FILE\n"
            << "  forensic-tool inspect FILE\n"
            << "  forensic-tool manifest --root DIR --out FILE --case ID --examiner NAME\n";
}

std::string option_value(int argc, char** argv, const std::string& key) {
  for (int i = 2; i + 1 < argc; ++i) {
    if (argv[i] == key) return argv[i + 1];
  }
  throw std::runtime_error("missing option: " + key);
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 3) {
      usage();
      return 2;
    }
    const std::string command = argv[1];
    if (command == "hash" && argc == 3) {
      const auto record = forensics::fingerprint_file(argv[2]);
      std::cout << record.sha256 << "  " << argv[2] << '\n';
    } else if (command == "inspect" && argc == 3) {
      std::cout << forensics::inspect_file(argv[2]) << '\n';
    } else if (command == "manifest") {
      forensics::ManifestOptions options;
      options.root = option_value(argc, argv, "--root");
      options.output = option_value(argc, argv, "--out");
      options.case_id = option_value(argc, argv, "--case");
      options.examiner = option_value(argc, argv, "--examiner");
      forensics::write_manifest(options);
      std::cout << "Manifest written to " << options.output << '\n';
    } else {
      usage();
      return 2;
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "forensic-tool: " << error.what() << '\n';
    return 1;
  }
}
