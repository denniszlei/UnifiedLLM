# Release Process

This document describes how to create a new release of UnifiedLLM.

## Release Checklist

Before creating a release:

- [ ] All tests are passing
- [ ] Documentation is up to date
- [ ] CHANGELOG.md is updated (if exists)
- [ ] Version number follows [Semantic Versioning](https://semver.org/)
- [ ] No known critical bugs

## Semantic Versioning

UnifiedLLM follows semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR** version: Incompatible API changes
- **MINOR** version: New functionality (backwards compatible)
- **PATCH** version: Bug fixes (backwards compatible)

Examples:
- `v1.0.0` - First stable release
- `v1.1.0` - New features added
- `v1.1.1` - Bug fixes
- `v2.0.0` - Breaking changes

## Creating a Release

### Step 1: Update Version Numbers

Update the version in these files:

1. **pyproject.toml**:
   ```toml
   [project]
   version = "1.0.0"
   ```

2. **app/main.py**:
   ```python
   app = FastAPI(
       title="UnifiedLLM",
       version="1.0.0",
   )
   ```

### Step 2: Commit Version Changes

```bash
git add pyproject.toml app/main.py
git commit -m "chore: Bump version to 1.0.0"
git push origin master
```

### Step 3: Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push tag to GitHub
git push origin v1.0.0
```

### Step 4: Verify Build

1. Go to [GitHub Actions](https://github.com/denniszlei/UnifiedLLM/actions)
2. Wait for "Build and Push Docker Image" workflow to complete
3. Verify the build succeeded

### Step 5: Verify Published Images

Check that images are published:

```bash
# Pull the new version
docker pull ghcr.io/denniszlei/unifiedllm:v1.0.0
docker pull ghcr.io/denniszlei/unifiedllm:1.0
docker pull ghcr.io/denniszlei/unifiedllm:1
docker pull ghcr.io/denniszlei/unifiedllm:latest

# Verify the version
docker run --rm ghcr.io/denniszlei/unifiedllm:v1.0.0 python -c "from app.main import app; print(app.version)"
```

### Step 6: Create GitHub Release (Optional)

1. Go to [Releases](https://github.com/denniszlei/UnifiedLLM/releases)
2. Click "Draft a new release"
3. Select the tag you just created (v1.0.0)
4. Fill in release notes:

```markdown
## What's New in v1.0.0

### Features
- Feature 1 description
- Feature 2 description

### Bug Fixes
- Fix 1 description
- Fix 2 description

### Breaking Changes
- Breaking change 1 (if any)

### Docker Images

Multi-architecture images are available:

\`\`\`bash
docker pull ghcr.io/denniszlei/unifiedllm:v1.0.0
\`\`\`

**Supported Platforms:**
- linux/amd64
- linux/arm64

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete details.
```

5. Click "Publish release"

## Release Types

### Stable Release

For production-ready releases:

```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### Pre-release (Beta/RC)

For testing before stable release:

```bash
git tag -a v1.0.0-beta.1 -m "Beta release 1.0.0-beta.1"
git push origin v1.0.0-beta.1
```

Mark as "pre-release" when creating GitHub release.

### Hotfix Release

For urgent bug fixes:

```bash
# Create hotfix branch from tag
git checkout -b hotfix/1.0.1 v1.0.0

# Make fixes
git add .
git commit -m "fix: Critical bug fix"

# Update version
# ... update version files ...

# Create tag
git tag -a v1.0.1 -m "Hotfix release 1.0.1"
git push origin v1.0.1

# Merge back to master
git checkout master
git merge hotfix/1.0.1
git push origin master
```

## Automated Builds

GitHub Actions automatically builds and publishes images when:

### On Tag Push (Releases)

Creates these tags:
- `v1.0.0` (exact version)
- `1.0` (major.minor)
- `1` (major only)
- `latest` (if on default branch)

### On Master Push

Creates these tags:
- `latest`
- `master`
- `master-<git-sha>`

### On Pull Request

Creates these tags (not pushed to registry):
- `pr-<number>`

## Rollback

If you need to rollback a release:

### Option 1: Delete Tag and Re-release

```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin :refs/tags/v1.0.0

# Fix issues and create new tag
git tag -a v1.0.0 -m "Release version 1.0.0 (fixed)"
git push origin v1.0.0
```

### Option 2: Create New Patch Release

```bash
# Revert changes
git revert <commit-hash>

# Create new patch release
git tag -a v1.0.1 -m "Release version 1.0.1 (rollback fix)"
git push origin v1.0.1
```

### Option 3: Point Users to Previous Version

Update documentation to recommend previous stable version:

```yaml
# In docker-compose.yml or documentation
image: ghcr.io/denniszlei/unifiedllm:v0.9.0
```

## Best Practices

1. **Test Before Release**
   - Run all tests locally
   - Test Docker build locally
   - Test in staging environment

2. **Document Changes**
   - Update CHANGELOG.md
   - Write clear release notes
   - Document breaking changes

3. **Version Consistently**
   - Update all version references
   - Follow semantic versioning
   - Use annotated tags (not lightweight)

4. **Communicate**
   - Announce releases to users
   - Highlight breaking changes
   - Provide migration guides

5. **Monitor After Release**
   - Watch for issues
   - Monitor GitHub Actions
   - Check image downloads

## Troubleshooting

### Build Fails After Tag Push

1. Check [GitHub Actions logs](https://github.com/denniszlei/UnifiedLLM/actions)
2. Fix the issue
3. Delete and recreate the tag:
   ```bash
   git tag -d v1.0.0
   git push origin :refs/tags/v1.0.0
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

### Image Not Available

Wait a few minutes for the build to complete. Check:
- GitHub Actions status
- Package visibility (should be public)
- Tag format (must start with 'v')

### Wrong Version in Image

Make sure you updated version in:
- pyproject.toml
- app/main.py

Then recreate the tag.

## Support

For questions about releases:
- Open an issue on GitHub
- Check GitHub Actions logs
- Review this document

## References

- [Semantic Versioning](https://semver.org/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Git Tagging](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
