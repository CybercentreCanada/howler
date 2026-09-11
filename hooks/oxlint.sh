#!/bin/bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ui_dir="${script_dir}/../ui"
cd "$ui_dir"

lintable_files=()

for file in "$@"; do
	case "$file" in
		"${ui_dir}"/src/*) relative_path="${file#"${ui_dir}"/}" ;;
		ui/src/*) relative_path="${file#ui/}" ;;
		./ui/src/*) relative_path="${file#./ui/}" ;;
		src/*) relative_path="$file" ;;
		./src/*) relative_path="${file#./}" ;;
		*) continue ;;
	esac

	if [[ "$relative_path" =~ \.(js|jsx|ts|tsx|mjs|cjs)$ ]] && [[ -f "$relative_path" ]]; then
		lintable_files+=("$relative_path")
	fi
done

if [[ ${#lintable_files[@]} -eq 0 ]]; then
	echo "No changed lintable files in ui/src; skipping oxlint."
	exit 0
fi

pnpx oxlint --fix "${lintable_files[@]}"
