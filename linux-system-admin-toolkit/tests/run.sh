#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
temporary_root=$(mktemp -d)
trap 'rm -rf -- "$temporary_root"' EXIT
tool="$project_root/bin/syscare"
source_dir="$temporary_root/fixture files"
mkdir -p -- "$source_dir/subdir"
printf 'synthetic configuration\n' > "$source_dir/subdir/sample.conf"
printf 'outside fixture\n' > "$temporary_root/outside.txt"
ln -s "$temporary_root/outside.txt" "$source_dir/external-link"

diagnostics=$(bash "$tool" diagnose "$source_dir")
jq -s -e 'any(.[]; .event == "system_check" and .check == "filesystem" and (.detail | contains("KiB available")))' <<< "$diagnostics" >/dev/null
jq -s -e 'any(.[]; .event == "system_check" and .check == "memory")' <<< "$diagnostics" >/dev/null

inspection=$(bash "$tool" inspect "$source_dir")
jq -e --arg path "$source_dir" '.event == "directory_inspection" and .path == $path and .files == "1"' <<< "$inspection" >/dev/null

export SYSCARE_BACKUP_DIR="$temporary_root/backups"
backup=$(bash "$tool" backup "$source_dir")
archive=$(jq -r '.archive' <<< "$backup")
checksum=$(jq -r '.checksum_file' <<< "$backup")
[[ -f $archive && -f $checksum ]]
(cd -- "$SYSCARE_BACKUP_DIR" && sha256sum -c "${archive##*/}.sha256") >/dev/null
[[ $(tar -xOzf "$archive" ./subdir/sample.conf) == "synthetic configuration" ]]
tar -tzvf "$archive" | grep -F 'external-link ->' >/dev/null
[[ $(stat -c '%a' "$archive") == 600 ]]

if SYSCARE_BACKUP_DIR="$source_dir/nested-backups" bash "$tool" backup "$source_dir" >/dev/null 2>&1; then
  printf '%s\n' 'backup accepted a destination inside its source' >&2
  exit 1
fi

mkfifo "$source_dir/unsupported-pipe"
if bash "$tool" backup "$source_dir" >/dev/null 2>&1; then
  printf '%s\n' 'backup accepted a special file' >&2
  exit 1
fi

preview=$(bash "$tool" service-restart ssh.service)
jq -e '.event == "service_restart_preview" and .service_name == "ssh.service" and .command == "systemctl restart ssh.service"' <<< "$preview" >/dev/null
if bash "$tool" service-restart '--dangerous.service' >/dev/null 2>&1; then
  printf '%s\n' 'service preview accepted an option-like unit name' >&2
  exit 1
fi
if SYSCARE_ALLOWED_SERVICES=not-ssh.service bash "$tool" service-restart ssh.service --apply --confirm >/dev/null 2>&1; then
  printf '%s\n' 'service apply bypassed the current-user/root boundary' >&2
  exit 1
fi
[[ $(bash "$tool" version) == 'syscare 0.1.0' ]]
printf '%s\n' 'syscare tests: passed'
