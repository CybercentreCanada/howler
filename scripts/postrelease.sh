#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# postrelease.sh — Bump component versions and commit after a release.
#
# Usage:
#   ./scripts/postrelease.sh {major|minor|patch} [--component COMP[,COMP...]]
#
# --component accepts a comma-separated list or multiple flags:
#   --component api,ui
#   --component api --component ui
#
# Supported components: api, ui, client  (default: api, ui)
# ---------------------------------------------------------------------------

usage() {
    echo "Usage: $(basename "$0") {major|minor|patch} [--component COMP[,COMP]]"
    echo ""
    echo "  COMP  One or more of: api, ui, client  (default: api ui)"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") minor"
    echo "  $(basename "$0") patch --component api"
    echo "  $(basename "$0") major --component api,ui,client"
    exit 1
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
BUMP_TYPE=""
declare -a COMPONENTS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        major|minor|patch)
            BUMP_TYPE="$1"
            shift
            ;;
        --component)
            [[ $# -lt 2 ]] && { echo "Error: --component requires a value."; usage; }
            shift
            IFS=',' read -ra _PARTS <<< "$1"
            for _part in "${_PARTS[@]}"; do
                COMPONENTS+=("$_part")
            done
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: unexpected argument '$1'."
            usage
            ;;
    esac
done

if [[ -z "$BUMP_TYPE" ]]; then
    echo "Error: bump type (major, minor, or patch) is required."
    usage
fi

if [[ ${#COMPONENTS[@]} -eq 0 ]]; then
    COMPONENTS=(api ui)
fi

for _comp in "${COMPONENTS[@]}"; do
    case "$_comp" in
        api|ui|client) ;;
        *) echo "Error: unknown component '$_comp'. Must be api, ui, or client."; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Locate repo root
# ---------------------------------------------------------------------------
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

# ---------------------------------------------------------------------------
# Bump versions
# ---------------------------------------------------------------------------
declare -A NEW_VERSIONS
declare -a STAGED_FILES=()

for _comp in "${COMPONENTS[@]}"; do
    case "$_comp" in
        api)
            echo "==> Bumping API version ($BUMP_TYPE)..."
            pushd "$REPO_ROOT/api" > /dev/null
            poetry version "$BUMP_TYPE"
            NEW_VERSIONS[api]="$(poetry version -s)"
            STAGED_FILES+=("api/pyproject.toml")
            popd > /dev/null
            ;;
        ui)
            echo "==> Bumping UI version ($BUMP_TYPE)..."
            pushd "$REPO_ROOT/ui" > /dev/null
            npm version --no-git-tag-version "$BUMP_TYPE" > /dev/null
            NEW_VERSIONS[ui]="$(node -p "require('./package.json').version")"
            STAGED_FILES+=("ui/package.json")
            popd > /dev/null
            ;;
        client)
            echo "==> Bumping client version ($BUMP_TYPE)..."
            pushd "$REPO_ROOT/client" > /dev/null
            poetry version "$BUMP_TYPE"
            NEW_VERSIONS[client]="$(poetry version -s)"
            STAGED_FILES+=("client/pyproject.toml")
            popd > /dev/null
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Stage changed files
# ---------------------------------------------------------------------------
echo ""
echo "Staging: ${STAGED_FILES[*]}"
git -C "$REPO_ROOT" add "${STAGED_FILES[@]}"

# ---------------------------------------------------------------------------
# Build default commit message
# ---------------------------------------------------------------------------
_SCOPE_PARTS=()
_VERSION_LINES=()
for _comp in "${COMPONENTS[@]}"; do
    _SCOPE_PARTS+=("$_comp")
    _VERSION_LINES+=("  ${_comp}: v${NEW_VERSIONS[$_comp]}")
done

_SCOPE="$(
    IFS=','
    echo "${_SCOPE_PARTS[*]}"
)"

_VERSION_BLOCK="$(
    IFS=$'\n'
    echo "${_VERSION_LINES[*]}"
)"

COMMIT_MSG="chore(${_SCOPE}): post-release version bumps

New versions:
${_VERSION_BLOCK}"

# ---------------------------------------------------------------------------
# Show message and prompt to accept / edit
# ---------------------------------------------------------------------------
echo ""
echo "Proposed commit message:"
echo "────────────────────────────────────────"
echo "$COMMIT_MSG"
echo "────────────────────────────────────────"
echo ""
read -r -p "Accept this commit message? [Y/n/e(dit)]: " _CONFIRM_MSG
_CONFIRM_MSG="${_CONFIRM_MSG:-Y}"

case "$_CONFIRM_MSG" in
    [Yy])
        : # keep COMMIT_MSG as-is
        ;;
    [Ee])
        _TMPFILE="$(mktemp)"
        echo "$COMMIT_MSG" > "$_TMPFILE"
        "${EDITOR:-vi}" "$_TMPFILE"
        COMMIT_MSG="$(cat "$_TMPFILE")"
        rm -f "$_TMPFILE"
        echo ""
        echo "Using edited commit message:"
        echo "────────────────────────────────────────"
        echo "$COMMIT_MSG"
        echo "────────────────────────────────────────"
        echo ""
        ;;
    *)
        echo "Commit message rejected. Changes are staged but not committed."
        exit 0
        ;;
esac

# ---------------------------------------------------------------------------
# Prompt to commit
# ---------------------------------------------------------------------------
read -r -p "Commit these changes? [Y/n]: " _DO_COMMIT
_DO_COMMIT="${_DO_COMMIT:-Y}"

if [[ "$_DO_COMMIT" =~ ^[Yy]$ ]]; then
    git -C "$REPO_ROOT" commit -m "$COMMIT_MSG"
    echo ""
    echo "Done. Post-release version bump committed."
else
    echo "Skipping commit. Changes remain staged."
fi
