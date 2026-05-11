#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# release.sh — Cut a release from main.
#
# Usage:
#   ./scripts/release.sh [--component COMP[,COMP...]]
#
# --component accepts a comma-separated list or multiple flags:
#   --component api,ui
#   --component api --component ui
#
# Supported components: api, ui, client  (default: api ui)
#
# Steps:
#   1. Verify current branch is `main` and up to date with remote.
#   2. Rebase `main` onto `develop` (bring develop's commits into main).
#   3. Check RELEASES.md for existing release notes for each component version.
#   4. Prompt the user to write release notes if they are absent.
#   5. Commit the release (staging RELEASES.md if updated; empty commit otherwise).
#   6. Create a git tag per component in the form `v<version>-<component>`.
#   7. Prompt the user to push branch and tags.
# ---------------------------------------------------------------------------

RELEASES_FILE="docs/RELEASES.md"

usage() {
    echo "Usage: $(basename "$0") [--component COMP[,COMP]]"
    echo ""
    echo "  COMP  One or more of: api, ui, client  (default: api ui)"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0")"
    echo "  $(basename "$0") --component api"
    echo "  $(basename "$0") --component api,ui,client"
    exit 1
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
declare -a COMPONENTS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
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
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Step 1: Ensure we are on main and up to date
# ---------------------------------------------------------------------------
echo "==> Checking branch..."
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Error: must be on 'main' to cut a release (currently on '$CURRENT_BRANCH')."
        echo "Your working tree has uncommitted changes — please commit or stash them first."
        exit 1
    fi
    echo "  Currently on '$CURRENT_BRANCH'. Working tree is clean."
    read -r -p "  Switch to 'main'? [Y/n]: " _DO_SWITCH
    _DO_SWITCH="${_DO_SWITCH:-Y}"
    if [[ "$_DO_SWITCH" =~ ^[Yy]$ ]]; then
        git checkout main
        CURRENT_BRANCH="main"
    else
        echo "Aborting."
        exit 1
    fi
fi

echo "==> Fetching from remote..."
git fetch --prune

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse @{u} 2>/dev/null || true)"

if [[ -z "$REMOTE_SHA" ]]; then
    echo "Warning: no upstream tracking branch found for 'main'. Skipping up-to-date check."
elif [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
    echo "Error: local 'main' is not up to date with its remote tracking branch."
    echo "  local:  $LOCAL_SHA"
    echo "  remote: $REMOTE_SHA"
    echo "Run 'git pull --rebase' and try again."
    exit 1
fi

echo "  main is up to date."

# ---------------------------------------------------------------------------
# Step 2: Rebase main onto develop
# ---------------------------------------------------------------------------
echo ""
echo "==> Rebasing 'main' onto 'develop'..."
git rebase develop

echo "  main rebased onto develop."

# ---------------------------------------------------------------------------
# Step 3: Read current versions for each component
# ---------------------------------------------------------------------------
declare -A VERSIONS

for _comp in "${COMPONENTS[@]}"; do
    case "$_comp" in
        api)
            pushd "$REPO_ROOT/api" > /dev/null
            VERSIONS[api]="$(poetry version -s)"
            popd > /dev/null
            ;;
        ui)
            VERSIONS[ui]="$(node -p "require('$REPO_ROOT/ui/package.json').version")"
            ;;
        client)
            pushd "$REPO_ROOT/client" > /dev/null
            VERSIONS[client]="$(poetry version -s)"
            popd > /dev/null
            ;;
    esac
done

echo ""
echo "Component versions to release:"
for _comp in "${COMPONENTS[@]}"; do
    echo "  $_comp: v${VERSIONS[$_comp]}"
done

# ---------------------------------------------------------------------------
# Step 4: Check RELEASES.md for existing notes; prompt if absent
# ---------------------------------------------------------------------------
RELEASES_PATH="$REPO_ROOT/$RELEASES_FILE"
RELEASES_UPDATED=false

component_heading() {
    local comp="$1"
    local ver="$2"
    case "$comp" in
        api)    echo "## Howler API \`v${ver}\`" ;;
        ui)     echo "## Howler UI \`v${ver}\`" ;;
        client) echo "## Howler Client \`v${ver}\`" ;;
    esac
}

echo ""
for _comp in "${COMPONENTS[@]}"; do
    _ver="${VERSIONS[$_comp]}"
    _heading="$(component_heading "$_comp" "$_ver")"

    if grep -qF "$_heading" "$RELEASES_PATH"; then
        echo "  Release notes found for $_comp v$_ver."
    else
        echo ""
        echo "  No release notes found for $_comp v$_ver (expected heading: '$_heading')."
        echo "  Please write release notes. Enter them below."
        echo "  Type your notes, then press Ctrl-D (EOF) when done."
        echo "  (Leave blank and press Ctrl-D to skip — an empty commit will be used.)"
        echo "────────────────────────────────────────"
        _NOTES="$(cat)"
        echo "────────────────────────────────────────"

        if [[ -n "$_NOTES" ]]; then
            # Prepend the new section directly after the first line (# Howler Releases)
            _TMPFILE="$(mktemp)"
            awk -v heading="$_heading" -v notes="$_NOTES" '
                NR == 1 { print; print ""; print heading; print ""; print notes; print ""; next }
                { print }
            ' "$RELEASES_PATH" > "$_TMPFILE"
            mv "$_TMPFILE" "$RELEASES_PATH"
            RELEASES_UPDATED=true
            echo "  Release notes added for $_comp v$_ver."
        else
            echo "  Skipping release notes for $_comp v$_ver."
        fi
    fi
done

# ---------------------------------------------------------------------------
# Step 5: Commit
# ---------------------------------------------------------------------------

# Build commit message
_VERSION_PARTS=()
for _comp in "${COMPONENTS[@]}"; do
    _VERSION_PARTS+=("${_comp}@v${VERSIONS[$_comp]}")
done

# Join with ", "
_RELEASE_LABEL="$(printf '%s, ' "${_VERSION_PARTS[@]}")"
_RELEASE_LABEL="${_RELEASE_LABEL%, }"

COMMIT_MSG="release: ${_RELEASE_LABEL}"

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
        : # keep as-is
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
        echo "Commit message rejected. Aborting."
        exit 1
        ;;
esac

echo ""
read -r -p "Commit? [Y/n]: " _DO_COMMIT
_DO_COMMIT="${_DO_COMMIT:-Y}"

if [[ "$_DO_COMMIT" =~ ^[Yy]$ ]]; then
    if [[ "$RELEASES_UPDATED" == true ]]; then
        git add "$RELEASES_FILE"
        git commit -m "$COMMIT_MSG"
    else
        git commit --allow-empty -m "$COMMIT_MSG"
    fi
    echo "  Release commit created."
else
    echo "Skipping commit."
fi

# ---------------------------------------------------------------------------
# Step 6: Tag each component
# ---------------------------------------------------------------------------
echo ""
declare -a TAGS_CREATED=()
for _comp in "${COMPONENTS[@]}"; do
    _tag="v${VERSIONS[$_comp]}-${_comp}"
    echo "==> Tagging: $_tag"
    git tag "$_tag"
    TAGS_CREATED+=("$_tag")
done

echo ""
echo "Tags created: ${TAGS_CREATED[*]}"

# ---------------------------------------------------------------------------
# Step 7: Prompt to push
# ---------------------------------------------------------------------------
echo ""
echo "Ready to push:"
echo "  Branch: main  →  origin/main"
echo "  Tags:   ${TAGS_CREATED[*]}"
echo ""
read -r -p "Push branch and tags to 'origin'? [Y/n]: " _DO_PUSH
_DO_PUSH="${_DO_PUSH:-Y}"

if [[ "$_DO_PUSH" =~ ^[Yy]$ ]]; then
    git push origin main
    git push origin "${TAGS_CREATED[@]}"
    echo ""
    echo "Done. Release pushed."
else
    echo ""
    echo "Skipping push. To push manually:"
    echo "  git push origin main"
    echo "  git push origin ${TAGS_CREATED[*]}"
fi
