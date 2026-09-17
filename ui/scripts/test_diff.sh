#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ui_dir="$(cd -- "$script_dir/.." && pwd)"

cd "$ui_dir"

get_changed_test_files() {
  {
    git diff --name-only --relative HEAD
    git ls-files --others --exclude-standard
  } | while IFS= read -r file; do
    case "$file" in
      *.test.ts|*.test.tsx)
        if [[ -f "$file" ]]; then
          printf '%s\n' "$file"
        fi
        ;;
      *.ts)
        test_file="${file%.ts}.test.ts"
        if [[ -f "$test_file" ]]; then
          printf '%s\n' "$test_file"
        fi
        ;;
      *.tsx)
        test_file="${file%.tsx}.test.tsx"
        if [[ -f "$test_file" ]]; then
          printf '%s\n' "$test_file"
        fi
        ;;
    esac
  done | sort -u
}

mapfile -t test_files < <(get_changed_test_files)

if ((${#test_files[@]} == 0)); then
  echo 'No changed files have matching unit tests.'
  exit 0
fi

exec pnpm test "${test_files[@]}"
