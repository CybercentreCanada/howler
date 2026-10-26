# Release and patching runbook

Howler has seven independently versioned code packages. Release Please runs on
`main` and creates a separate release pull request for each package whose
directory contains releasable conventional commits. The release PR updates that
package's native version metadata, its local `CHANGELOG.md`, and the shared
release manifest. Merging a release PR creates a native component tag and
GitHub Release; the central Release Please workflow explicitly dispatches that
package's publication workflow at the native tag because `GITHUB_TOKEN`-created
tags do not trigger the usual tag-push workflows. Do not manually bump versions,
create release tags, or add new entries to `docs/RELEASES.md`.

| Component | Package directory | Native tag | Stable publication |
| --- | --- | --- | --- |
| API | `api/` | `api-vX.Y.Z` | PyPI and API Docker image |
| UI | `ui/` | `ui-vX.Y.Z` | npm and UI Docker image |
| Client | `client/` | `client-vX.Y.Z` | PyPI |
| MCP | `mcp/` | `mcp-vX.Y.Z` | Docker image only |
| Evidence | `plugins/evidence/` | `evidence-vX.Y.Z` | PyPI |
| Sentinel | `plugins/sentinel/` | `sentinel-vX.Y.Z` | PyPI |
| Sync | `plugins/sync/` | `sync-vX.Y.Z` | PyPI |

Helm is not an independently released code package. Legacy tags are retained;
the native names above are used for all new stable releases.

## Commit and PR conventions

Use Conventional Commits. The accepted types are `feat`, `fix`, `perf`, `test`,
`tests`, `docs`, `deps`, `refactor`, `infra`, `ci`, `build`, `revert`, `style`,
`chore`, `release`, and `improvement`. Release Please scopes commits by changed
file paths, not by the textual commit scope: keep each change inside its
component directory when it should produce only that component's release PR.
Cross-package changes may update multiple component release PRs.

`feat` creates a minor release and `fix`/`perf` create patch releases for
versions at or above `1.0.0`. Other visible changelog types—including `test`,
`tests`, `docs`, and `improvement`—also create patch releases. Before `1.0.0`,
features increment the patch and breaking changes increment the minor version.
Breaking changes use the Conventional Commit `!` marker or a `BREAKING CHANGE:`
footer. `chore`, `style`, `build`, `ci`, and `release` are hidden from generated
changelogs and do not create a release by themselves.

Every release PR is checked by the regular package CI and title validation.
Merge it only after its package-specific checks pass. No manual `poetry
version`, `pnpm version`, `git tag`, or GitHub Release creation is part of the
routine flow.

## Main previews

Main-branch previews are limited to the API, UI, and MCP container images and
the UI npm package. API and MCP images use the checked-in native version and
publish only the `nightly` tag (plus an immutable SHA tag). The UI image follows
the same `nightly`/SHA policy. The UI npm package uses the next patch version
with `-dev.<GITHUB_RUN_NUMBER>.<GITHUB_RUN_ATTEMPT>` and the `development`
dist-tag. This version change is confined to the temporary npm publishing
workspace; the checked-in `ui/package.json` and every Python package's native
version metadata remain unchanged. Main does not publish Python packages to
PyPI, and a main build never assigns an exact stable version tag or `latest` to
a container image.

These previews do not create release PRs or stable GitHub Releases. Pull
requests, ordinary manual dispatches, deleted refs, and pushes to branches other
than `main` do not publish. Manual workflow dispatches default to validation
only. There are no `develop`, release-candidate, or patch-branch release
channels. Stable publication validates the component's checked-in canonical
`X.Y.Z` version, requires the native `<component>-vX.Y.Z` tag to match it, and
checks that the checked-out SHA is the peeled tag target and an ancestor of
`origin/main`.

## Initial baseline and first compare links

The manifest is initialized from the native metadata versions at the bootstrap
commit: API `4.1.0`, UI `3.1.0`, Client `3.1.0`, MCP `0.1.1`, Evidence `0.1.0`,
Sentinel `0.2.0`, and Sync `0.0.1`. Historical tags remain in the repository,
but their old naming does not satisfy the new `<component>-vX.Y.Z` scheme. The
manifest versions are therefore synthetic native baselines; the bootstrap SHA
prevents old history from being replayed into the first generated changelog.
The initial generated changelog links the corresponding archived notes in
`docs/RELEASES.md` where they exist and explicitly records that no generated
entry is created for the baseline itself.

Until every component has completed its first native release, retain the
`bootstrap-sha` in `.release-please-config.json`. Remove it only after all seven
native component tags/releases exist and the regular native-tag lookup has
become the history boundary for every package. The first native GitHub compare
link may have no native predecessor (or may span farther back than a normal
release compare); this is an expected consequence of keeping the legacy tags
and using synthetic manifest baselines. Inspect the compare link, but do not
rewrite the archived release history or create a fake historical release.

## Repository setup and credentials

The Release Please workflow uses the repository's built-in `GITHUB_TOKEN` with
write access to contents, issues, pull requests, and workflow dispatch. No
personal access token or actor-specific signature bypass is required. The
stock Release Please action used here (v17.3.0) creates and updates release PRs
through GitHub's API; it does not supply custom author/signing fields. GitHub
creates the associated API commits server-side, where they receive GitHub's
server signature. Verify the resulting commits display as **Verified** in the
repository. This workflow does not alter any repository/organization rulesets,
branch protections, approval settings, or merge permissions; existing rules
remain authoritative. Release Please also needs the existing repository
Actions setting that permits GitHub Actions to create pull requests; verify
that setting is enabled, but do not change GitHub settings as part of this
workflow change.

GitHub suppresses the usual tag-push workflow trigger for tags/releases created
with `GITHUB_TOKEN`. Therefore, after Release Please reports actual released
paths, the central workflow validates each native tag and explicitly dispatches
that component's workflow at the tag with `publish_release: true`. To recover a
missed dispatch, run the relevant component workflow manually against the
already-published native tag and set `publish_release` to `true`. That explicit
mode verifies that the exact GitHub Release exists, is published, and is not a
draft or prerelease before any publishing credentials or OIDC permissions are
used. A manual dispatch with the default `false` value is validation-only; a
true dispatch on `main` or any non-component tag fails closed.

GitHub may display an approval-required banner for checks on a
Release-Please-created PR, depending on repository workflow approval policy.
An authorized maintainer should approve the run when GitHub requests it and
confirm the regular component CI and PR-title checks complete before merging.
Once approved, the normal `opened`, `synchronize`, and `reopened` PR workflows
apply. This approval prompt is expected policy behavior, not a reason to add a
PAT or weaken repository protections.

Package publication credentials are separate from Release Please:

- Configure `PYPI_TOKEN` for stable publication of the API, Client, Evidence,
  Sentinel, and Sync distributions. PyPI publication is stable-only.
- UI npm publishing uses the existing GitHub OIDC trusted-publishing workflow
  identity and provenance. Do not add an `NPM_TOKEN` secret or token fallback.
- Configure the existing Docker Hub credentials and Chainguard identity for
  container publishing. MCP has no PyPI publication; its stable artifact is
  the MCP Docker image.

## Validation and troubleshooting

1. Confirm the Release Please workflow ran from `main` and the component path
   appears in the release PR's changed files.
2. Check the PR's native version, local changelog, and manifest entry. A
   historical-only edit to `docs/RELEASES.md` must not create a package release.
3. After merging, confirm the tag exactly matches `<component>-vX.Y.Z`, and that
   the corresponding package workflow completed its build/publication.
4. If native tag validation fails, verify the committed package version equals
   the canonical tag version and that the tag target is on `origin/main`. For a
   manual stable dispatch, also verify the GitHub Release is published and is
   not a draft or prerelease. Do not move or recreate a published tag to work
   around the check.
5. If preview publishing fails, confirm it was an eligible push to `main` and
   the relevant existing registry credential or trusted-publishing identity is
   configured. A preview failure must not be repaired by publishing from a
   feature, `develop`, `rc/*`, or `patch/*` branch.

The complete historical release archive remains at
[`docs/RELEASES.md`](RELEASES.md); it is not the destination for future release
notes.
