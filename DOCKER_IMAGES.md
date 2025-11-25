# Docker Images Guide

This document explains how UnifiedLLM Docker images are built, published, and used.

## Overview

UnifiedLLM uses GitHub Actions to automatically build and publish multi-architecture Docker images to GitHub Container Registry (ghcr.io).

## Image Repository

**Registry**: GitHub Container Registry (ghcr.io)  
**Image**: `ghcr.io/denniszlei/unifiedllm`  
**Visibility**: Public (anyone can pull)

## Supported Architectures

The images are built for multiple architectures:

- **linux/amd64** - Standard x86_64 servers and desktops
- **linux/arm64** - ARM64 servers, Raspberry Pi 4/5, Apple Silicon Macs

## Available Tags

Images are tagged automatically based on the trigger:

### Branch-based Tags
- `latest` - Latest build from the master branch (recommended for production)
- `master` - Latest build from the master branch (same as latest)
- `master-<sha>` - Specific commit from master branch

### Version Tags (Semantic Versioning)
When you create a git tag like `v1.0.0`, the following tags are created:
- `v1.0.0` - Full version
- `1.0` - Major.minor version
- `1` - Major version only

### Pull Request Tags
- `pr-<number>` - Built from pull requests (for testing)

## Using Pre-built Images

### Quick Start

The easiest way to use UnifiedLLM is with the pre-built image:

```bash
# Pull the latest image
docker pull ghcr.io/denniszlei/unifiedllm:latest

# Run the container
docker run -d \
  -p 8000:8000 \
  -e ENCRYPTION_KEY=your-key-here \
  -e GPTLOAD_URL=http://gptload:3001 \
  -e GPTLOAD_AUTH_KEY=your-auth-key \
  -v unifiedllm-data:/app/data \
  ghcr.io/denniszlei/unifiedllm:latest
```

### Using with Docker Compose

The default `docker-compose.yml` is configured to use the pre-built image:

```yaml
services:
  unifiedllm:
    image: ghcr.io/denniszlei/unifiedllm:latest
    # ... rest of configuration
```

Just run:

```bash
docker-compose up -d
```

### Using a Specific Version

To use a specific version instead of latest:

```bash
# In .env file
UNIFIEDLLM_IMAGE=ghcr.io/denniszlei/unifiedllm:v1.0.0

# Or in docker-compose.yml
services:
  unifiedllm:
    image: ghcr.io/denniszlei/unifiedllm:v1.0.0
```

## Building Images Locally

If you want to build the image yourself instead of using the pre-built one:

### Option 1: Docker Compose

Uncomment the build section in `docker-compose.yml`:

```yaml
services:
  unifiedllm:
    # image: ghcr.io/denniszlei/unifiedllm:latest
    build:
      context: .
      dockerfile: Dockerfile
```

Then build and run:

```bash
docker-compose build
docker-compose up -d
```

### Option 2: Docker CLI

Build for your current architecture:

```bash
docker build -t unifiedllm:local .
```

Build for multiple architectures (requires buildx):

```bash
# Set up buildx
docker buildx create --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t unifiedllm:local \
  --load \
  .
```

## GitHub Actions Workflow

### Automatic Builds

Images are automatically built and pushed when:

1. **Push to master branch** - Creates `latest` and `master` tags
2. **Version tag created** - Creates version-specific tags (e.g., `v1.0.0`, `1.0`, `1`)
3. **Pull request** - Creates `pr-<number>` tag (for testing, not pushed to registry)

### Manual Trigger

You can manually trigger a build from the GitHub Actions tab:

1. Go to: https://github.com/denniszlei/UnifiedLLM/actions
2. Select "Build and Push Docker Image" workflow
3. Click "Run workflow"
4. Select the branch and click "Run workflow"

## Creating a New Release

To create a new versioned release:

```bash
# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0
```

This will automatically:
1. Build multi-arch images
2. Push to ghcr.io with tags: `v1.0.0`, `1.0`, `1`, `latest`
3. Create build attestations for security

## Viewing Published Images

You can view all published images at:
https://github.com/denniszlei/UnifiedLLM/pkgs/container/unifiedllm

## Image Details

### Base Image
- `python:3.11-slim` - Minimal Python image for smaller size

### Image Size
- Approximately 200-300 MB (compressed)
- Varies by architecture

### Security
- Images are scanned for vulnerabilities
- Build provenance attestations are generated
- No secrets are included in the image

## Troubleshooting

### Cannot Pull Image

If you get permission errors:

```bash
# Make sure the package is public
# Or authenticate with GitHub:
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

### Wrong Architecture

Docker automatically pulls the correct architecture for your system. To verify:

```bash
docker image inspect ghcr.io/denniszlei/unifiedllm:latest | grep Architecture
```

### Build Failures

Check the GitHub Actions logs:
https://github.com/denniszlei/UnifiedLLM/actions

Common issues:
- Dockerfile syntax errors
- Missing dependencies
- Network timeouts during build

## Best Practices

### For Production

1. **Use specific version tags** instead of `latest`:
   ```yaml
   image: ghcr.io/denniszlei/unifiedllm:v1.0.0
   ```

2. **Pin your versions** in docker-compose.yml or .env

3. **Test new versions** in staging before production

4. **Monitor for updates** and security patches

### For Development

1. **Use `latest` tag** for quick testing:
   ```yaml
   image: ghcr.io/denniszlei/unifiedllm:latest
   ```

2. **Build locally** when making changes:
   ```yaml
   build:
     context: .
     dockerfile: Dockerfile
   ```

3. **Use PR tags** to test specific changes:
   ```yaml
   image: ghcr.io/denniszlei/unifiedllm:pr-123
   ```

## Advanced Usage

### Custom Build Arguments

If you need to customize the build:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.11 \
  -t unifiedllm:custom \
  .
```

### Multi-stage Builds

The Dockerfile uses a single-stage build for simplicity. For production, consider:
- Multi-stage builds to reduce image size
- Separate build and runtime stages
- Non-root user for security

### Health Checks

The image includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health', timeout=5.0)" || exit 1
```

Monitor health status:

```bash
docker ps
# Look for "healthy" status
```

## Support

For issues with Docker images:

1. Check the [GitHub Actions logs](https://github.com/denniszlei/UnifiedLLM/actions)
2. Review the [Dockerfile](Dockerfile)
3. Open an issue on GitHub

## References

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Multi-platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [GitHub Actions Docker Documentation](https://docs.github.com/en/actions/publishing-packages/publishing-docker-images)
