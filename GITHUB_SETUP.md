# GitHub Setup Guide

This guide walks you through the one-time setup needed for GitHub Actions to publish Docker images.

## Prerequisites

- GitHub repository created: ✅ https://github.com/denniszlei/UnifiedLLM
- Code pushed to repository: ✅ Done
- GitHub Actions workflow added: ✅ Done

## Step 1: Enable GitHub Actions (Already Done)

GitHub Actions is enabled by default for public repositories. The workflow file is already in place at `.github/workflows/docker-publish.yml`.

## Step 2: Configure Package Permissions

The workflow uses `GITHUB_TOKEN` which is automatically provided by GitHub Actions. No additional secrets needed!

### Verify Package Settings

1. Go to your repository: https://github.com/denniszlei/UnifiedLLM
2. Click on "Settings" tab
3. In the left sidebar, click "Actions" → "General"
4. Scroll to "Workflow permissions"
5. Ensure "Read and write permissions" is selected
6. Click "Save" if you made changes

## Step 3: Trigger First Build

The workflow will automatically trigger when you push to master. Since we just pushed, it should already be running!

### Check Build Status

1. Go to: https://github.com/denniszlei/UnifiedLLM/actions
2. You should see "Build and Push Docker Image" workflow running
3. Click on it to see the build progress

### What the Workflow Does

1. **Checkout code** - Gets your repository code
2. **Set up QEMU** - Enables multi-architecture builds
3. **Set up Docker Buildx** - Advanced Docker build features
4. **Login to ghcr.io** - Authenticates with GitHub Container Registry
5. **Extract metadata** - Generates image tags and labels
6. **Build and push** - Builds for amd64 and arm64, then pushes to registry
7. **Generate attestation** - Creates security provenance

## Step 4: Make Package Public

After the first build completes, you need to make the package public:

1. Go to: https://github.com/denniszlei/UnifiedLLM/pkgs/container/unifiedllm
2. Click "Package settings" (on the right side)
3. Scroll down to "Danger Zone"
4. Click "Change visibility"
5. Select "Public"
6. Type the repository name to confirm
7. Click "I understand, change package visibility"

**Why?** By default, packages are private. Making it public allows anyone to pull your Docker images without authentication.

## Step 5: Verify Everything Works

Once the build completes and package is public:

```bash
# Pull the image (no authentication needed)
docker pull ghcr.io/denniszlei/unifiedllm:latest

# Verify it works
docker run --rm ghcr.io/denniszlei/unifiedllm:latest python -c "from app.main import app; print(f'UnifiedLLM {app.version}')"
```

## What Happens Automatically

### On Every Push to Master

- Builds Docker images for amd64 and arm64
- Pushes with tags: `latest`, `master`, `master-<sha>`
- Updates the package on ghcr.io

### On Version Tag (e.g., v1.0.0)

- Builds Docker images for amd64 and arm64
- Pushes with tags: `v1.0.0`, `1.0`, `1`, `latest`
- Creates a versioned release

### On Pull Requests

- Builds images (but doesn't push)
- Validates that the Docker build works

## Creating Your First Release

When you're ready to create v1.0.0:

```bash
# Update version in code
# Edit pyproject.toml: version = "1.0.0"
# Edit app/main.py: version="1.0.0"

# Commit version bump
git add pyproject.toml app/main.py
git commit -m "chore: Bump version to 1.0.0"
git push origin master

# Create and push tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

This will automatically:
1. Build multi-arch images
2. Push with tags: `v1.0.0`, `1.0`, `1`, `latest`
3. Make them available at ghcr.io

## Monitoring Builds

### GitHub Actions Dashboard

View all builds: https://github.com/denniszlei/UnifiedLLM/actions

### Package Page

View published images: https://github.com/denniszlei/UnifiedLLM/pkgs/container/unifiedllm

### Build Badges

Add to your README (already done):

```markdown
[![Build and Push Docker Image](https://github.com/denniszlei/UnifiedLLM/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/denniszlei/UnifiedLLM/actions/workflows/docker-publish.yml)
```

## Troubleshooting

### Build Fails

1. Check the Actions tab for error logs
2. Common issues:
   - Dockerfile syntax errors
   - Missing dependencies
   - Network timeouts

### Cannot Pull Image

If you get "unauthorized" errors:

1. Make sure package is public (Step 4)
2. Wait a few minutes after making it public
3. Try pulling again

### Wrong Architecture

Docker automatically pulls the right architecture. To verify:

```bash
docker image inspect ghcr.io/denniszlei/unifiedllm:latest | grep Architecture
```

Should show either `amd64` or `arm64` depending on your system.

## Security Notes

### GITHUB_TOKEN

- Automatically provided by GitHub Actions
- Scoped to your repository
- No need to create or manage it
- Expires after the workflow completes

### Package Permissions

- Public packages can be pulled by anyone
- Only you can push new versions
- Managed through GitHub repository settings

### Build Provenance

- Automatically generated for each build
- Provides supply chain security
- Shows exactly how the image was built

## Cost

GitHub Actions is free for public repositories:
- Unlimited build minutes
- Unlimited storage for packages
- No credit card required

## Next Steps

1. ✅ Wait for first build to complete
2. ✅ Make package public
3. ✅ Test pulling the image
4. 📝 Create your first release (when ready)
5. 📝 Share with users!

## Support

If you encounter issues:

1. Check [GitHub Actions logs](https://github.com/denniszlei/UnifiedLLM/actions)
2. Review [GitHub Packages documentation](https://docs.github.com/en/packages)
3. Open an issue in your repository

## Summary

You're all set! The workflow is configured and will automatically:

- ✅ Build multi-architecture Docker images
- ✅ Publish to GitHub Container Registry
- ✅ Tag images appropriately
- ✅ Run on every push and tag

Just push code and the rest happens automatically! 🎉
