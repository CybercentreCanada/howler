#!/usr/bin/env bash

set -e

if [ "$#" -eq 0 ]; then
    echo "No TypeScript files staged. Skipping check."
    exit 0
fi

echo "Checking $# modified TypeScript file(s)..."

# "$@" expands to all individual file paths safely, preserving spaces in filenames
npx tsc --noEmit --skipLibCheck "$@"

echo "TypeScript check passed!"
