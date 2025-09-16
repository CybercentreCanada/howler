# Howler Patching Guide

This guide provides step-by-step instructions for creating and releasing patches for both the Howler API and UI components.

## Prerequisites

- Git access to the Howler repository
- Poetry installed (for API patches)
- pnpm installed (for UI patches)
- Docker Hub access for verifying published images
- GitHub repository access for creating releases

## API Patching Process

### 1. Prepare the Patch Branch

```bash
# Checkout and update the main branch
git checkout main
git pull

# Create a descriptive patch branch
git checkout -b patch/fix-compare-metadata-functionality

# Navigate to the API directory
cd api

# Bump the patch version
poetry version patch
```

### 2. Implement Changes

Make your necessary code changes, ensuring you:

- Add or update unit tests as needed
- Follow existing code style and conventions
- Test your changes locally before committing

### 3. Create Pull Request

```bash
# Push your branch and create a PR
git add .
git commit -m "Fix compare metadata functionality"
git push -u origin HEAD
```

Open a pull request at: <https://github.com/CybercentreCanada/howler/compare>

### 4. Update Release Notes

Before merging, update `docs/RELEASES.md` with your changes. Follow this format:

```markdown
## Howler API `v2.11.3`

- **Fixed Compare Metadata Functionality** *(bugfix)*: Added check to not run matching when no hits are provided
- **Enhanced Error Handling** *(bugfix)*: Improved error handling for edge cases in metadata comparison
```

### 5. Merge and Release

1. **Merge the PR**: Use the GitHub UI to squash and merge the PR into a single commit
2. **Create the release tag**:

```bash
# Return to main and pull the merged changes
git checkout main
git pull

# Create and push the version tag
git tag "v$(poetry version -s)-api"
git push
git push --tags
```

1. **Create GitHub Release**:
   - Go to <https://github.com/CybercentreCanada/howler/releases/new>
   - Name: "Howler API v2.11.3"
   - Generate release notes and add a link to the `docs/RELEASES.md` section

### 6. Verify Deployment

Confirm the Docker image was published successfully:
<https://hub.docker.com/r/cccsaurora/howler-api/tags>

## UI Patching Process

### 1. Prepare the Patch Branch

```bash
# Checkout and update the main branch
git checkout main
git pull

# Create a descriptive patch branch
git checkout -b patch/fix-view-panel-configuration

# Navigate to the UI directory
cd ui

# Bump the patch version
pnpm version patch
```

### 2. Implement Changes

Make your necessary code changes, ensuring you:

- Add or update tests as appropriate
- Follow TypeScript and React best practices
- Test the UI changes in a development environment

### 3. Create Pull Request

```bash
# Push your branch and create a PR
git add .
git commit -m "Fix view panel configuration bug"
git push -u origin HEAD
```

Open a pull request at: <https://github.com/CybercentreCanada/howler/compare>

### 4. Update Release Notes

Before merging, update `docs/RELEASES.md` with your changes. Follow this format:

```markdown
## Howler UI `v2.13.3`

- **Fixed View Panel Configuration** *(bugfix)*: Fixed bug that stopped users from configuring new view panels on the dashboard
- **Improved Error Messages** *(UI/UX improvement)*: Enhanced error messaging for better user experience
```

### 5. Merge and Release

1. **Merge the PR**: Use the GitHub UI to squash and merge the PR into a single commit
2. **Create the release tag**:

```bash
# Return to main and pull the merged changes
git checkout main
git pull

# Create and push the version tag
git tag "v$(python -c "import json;print(json.load(open('package.json', 'r'))['version'])")-ui"
git push
git push --tags
```

1. **Create GitHub Release**:
   - Go to <https://github.com/CybercentreCanada/howler/releases/new>
   - Name: "Howler UI v2.13.3"
   - Generate release notes and add a link to the `docs/RELEASES.md` section

### 6. Verify Deployment

Confirm both the Docker image and NPM package were published successfully:

- Docker: <https://hub.docker.com/r/cccsaurora/howler-ui/tags>
- NPM: <https://www.npmjs.com/package/@cccsaurora/howler-ui?activeTab=versions>

## Best Practices

- **Branch Naming**: Use descriptive names like `patch/fix-specific-issue`
- **Code Review**: Always get approval from at least one other developer (two for larger changes)
- **Testing**: Ensure all tests pass before merging
- **Documentation**: Update release notes with clear, user-facing descriptions
- **Verification**: Always verify successful deployment after releasing
