#!/bin/bash
set -euo pipefail

cd "$(dirname "$(dirname "$0")")"

lintable_files=()

for file in "$@"; do
	# pre-commit passes repo-root-relative paths (for example: ui/src/foo.ts)
	if [[ "$file" == ui/src/* ]]; then
		relative_path="${file#ui/}"
		if [[ "$relative_path" =~ \.(js|jsx|ts|tsx|mjs|cjs)$ ]] && [[ -f "$relative_path" ]]; then
			lintable_files+=("$relative_path")
		fi
	fi
done

if [[ ${#lintable_files[@]} -eq 0 ]]; then
	echo "No changed lintable files in ui/src; skipping oxlint."
	exit 0
fi

pnpx oxlint --fix "${lintable_files[@]}"
