#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# releasenotes.sh — Create GitHub releases from RELEASES.md for given tags.
#
# Usage:
#   ./scripts/releasenotes.sh TAG [TAG...]
#
# TAG must be in the form v<version>-<component>, e.g.:
#   v2.17.2-ui
#   v3.3.0-api
#   v2.4.1-client
#
# The matching section in docs/RELEASES.md is used as the release body.
# ---------------------------------------------------------------------------

RELEASES_FILE="docs/RELEASES.md"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
RELEASES_PATH="$REPO_ROOT/$RELEASES_FILE"

usage() {
    echo "Usage: $(basename "$0") TAG [TAG...]"
    echo ""
    echo "  TAG  A git tag in the form v<version>-<component>"
    echo "       Supported components: api, ui, client"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") v2.17.2-ui"
    echo "  $(basename "$0") v3.3.0-api v2.18.0-ui"
    exit 1
}

[[ $# -eq 0 ]] && usage

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' (GitHub CLI) is not installed or not in PATH."
    exit 1
fi

if ! gh auth status &>/dev/null 2>&1; then
    echo "Error: not authenticated with GitHub CLI. Run 'gh auth login' first."
    exit 1
fi

if [[ ! -f "$RELEASES_PATH" ]]; then
    echo "Error: release notes file not found at $RELEASES_PATH"
    exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
component_display_name() {
    case "$1" in
        api)    echo "Howler API" ;;
        ui)     echo "Howler UI" ;;
        client) echo "Howler Client" ;;
        *)      echo "Howler $1" ;;
    esac
}

# Find the previous tag for a given version and component using semver ordering.
# Iterates tags sorted by version and returns the one immediately before the current.
# If the current tag isn't in the list yet (not yet pushed), returns the latest existing tag.
find_previous_tag() {
    local version="$1"
    local component="$2"
    local prev=""

    while IFS= read -r tag_ver; do
        if [[ "$tag_ver" == "v${version}" ]]; then
            break
        fi
        prev="$tag_ver"
    done < <(git tag -l "v*-${component}" | sed "s/-${component}$//" | sort -V)

    if [[ -n "$prev" ]]; then
        echo "${prev}-${component}"
    fi
}

# Extract the section of RELEASES.md under a given heading.
# Prints lines between the heading and the next ## heading (exclusive).
extract_section() {
    local heading="$1"
    awk -v h="$heading" '
        $0 == h      { found=1; next }
        found && /^## / { exit }
        found        { print }
    ' "$RELEASES_PATH" \
    | awk 'NF { found=1 } found { print }' \
    | sed -e 's/[[:space:]]*$//'
}

# ---------------------------------------------------------------------------
# Process each tag
# ---------------------------------------------------------------------------
for TAG in "$@"; do
    if [[ ! "$TAG" =~ ^v([^-]+)-([a-z]+)$ ]]; then
        echo "Error: '$TAG' is not a valid tag format. Expected v<version>-<component> (e.g. v2.17.2-ui)."
        exit 1
    fi

    VERSION="${BASH_REMATCH[1]}"
    COMPONENT="${BASH_REMATCH[2]}"
    DISPLAY_NAME="$(component_display_name "$COMPONENT")"
    HEADING="## ${DISPLAY_NAME} \`v${VERSION}\`"
    RELEASE_TITLE="${DISPLAY_NAME} ${VERSION}"

    echo ""
    echo "==> $TAG  →  \"$RELEASE_TITLE\""

    # Determine previous tag for comparison display
    PREV_TAG="$(find_previous_tag "$VERSION" "$COMPONENT")"
    if [[ -n "$PREV_TAG" ]]; then
        echo "  Previous tag: $PREV_TAG"
    else
        echo "  Previous tag: (none found — this will be the first release for $COMPONENT)"
    fi

    # Check the tag exists locally or on the remote
    if ! git rev-parse --verify "refs/tags/$TAG" &>/dev/null && \
       ! git ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
        echo "  Warning: tag '$TAG' not found locally or on remote. The release will still be attempted."
    fi

    # Check if a GitHub release already exists for this tag
    if gh release view "$TAG" &>/dev/null 2>&1; then
        echo "  Error: a GitHub release for '$TAG' already exists. Skipping."
        continue
    fi

    # Extract release notes
    NOTES="$(extract_section "$HEADING")"

    if [[ -z "$NOTES" ]]; then
        echo "  Error: no release notes found for '$TAG'."
        echo "  Expected heading in $RELEASES_FILE: $HEADING"
        exit 1
    fi

    echo "  Release notes:"
    echo "────────────────────────────────────────"
    echo "$NOTES"
    echo "────────────────────────────────────────"
    echo ""
    read -r -p "  Create GitHub release '$TAG' titled '$RELEASE_TITLE'? [Y/n]: " _CONFIRM
    _CONFIRM="${_CONFIRM:-Y}"

    if [[ ! "$_CONFIRM" =~ ^[Yy]$ ]]; then
        echo "  Skipped."
        continue
    fi

    gh release create "$TAG" \
        --title "$RELEASE_TITLE" \
        --notes "$NOTES" \
        ${PREV_TAG:+--notes-start-tag "$PREV_TAG"}

    echo "  GitHub release '$TAG' created successfully."
done
