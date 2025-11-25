# UnifiedLLM

[![Build and Push Docker Image](https://github.com/denniszlei/UnifiedLLM/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/denniszlei/UnifiedLLM/actions/workflows/docker-publish.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/denniszlei/UnifiedLLM/pkgs/container/unifiedllm)

Configuration orchestrator for GPT-Load and uni-api. This service provides a unified interface for managing multiple LLM API providers, normalizing model names, and automatically generating configurations for downstream services.

## Features

- 🔐 Secure API key storage with Fernet encryption
- 🔄 Manage multiple LLM API providers (OpenAI, OpenRouter, etc.)
- 🏷️ Model normalization and duplicate detection
- ⚖️ Automatic GPT-Load configuration via REST API
- 🔌 uni-api YAML configuration generation
- 🐳 Complete Docker deployment with all services
- 🎯 Web-based UI for easy management

## Architecture

The system consists of three services working together:

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  UnifiedLLM (port 8000)                              │  │
│  │  - Web UI                                            │  │
│  │  - REST API                                          │  │
│  │  - Configuration Generator                           │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                    │
│         │ (HTTP API calls)                                  │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GPT-Load (port 3001)                                │  │
│  │  - Load Balancing                                    │  │
│  │  - Group Management                                  │  │
│  │  - Model Routing                                     │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                    │
│         │ (Proxy requests)                                  │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  uni-api (port 8001)                                 │  │
│  │  - Unified API Gateway                               │  │
│  │  - Request Routing                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          ▼
    External LLM Providers
    (OpenAI, Anthropic, etc.)
```

## Docker Images

Pre-built multi-architecture Docker images are available on GitHub Container Registry:

```bash
# Pull the latest image
docker pull ghcr.io/denniszlei/unifiedllm:latest

# Pull a specific version
docker pull ghcr.io/denniszlei/unifiedllm:v1.0.0
```

**Supported Architectures:**
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64/Apple Silicon)

Images are automatically built and published on every push to the master branch and on version tags.

## Quick Start with Docker (Recommended)

Get up and running in 5 minutes with Docker!

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM available
- 1GB disk space

### Setup Steps

1. **Clone the repository:**
```bash
git clone <repository-url>
cd unifiedllm
```

2. **Create environment file:**
```bash
cp .env.example .env
```

3. **Generate encryption key:**

Choose one of the following methods:

**Method 1: Using Python (if installed):**

Linux/macOS:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Windows (PowerShell):
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Method 2: Using OpenSSL (if Python not available):**

Linux/macOS/Windows (Git Bash):
```bash
openssl rand -base64 32
```

**Method 3: Using Docker (no local installation needed):**

```bash
docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Method 4: Online Generator:**

Visit: https://generate-random.org/encryption-key-generator?count=1&bytes=32&cipher=aes-256-cbc&string=&password=

Select "Base64" format and generate a 32-byte key.

Copy the output (looks like: `gAAAAABk...` or a base64 string)

4. **Edit `.env` file:**

Open `.env` and set:
```env
ENCRYPTION_KEY=<paste-your-generated-key-here>
GPTLOAD_AUTH_KEY=your-secure-password-here
```

**IMPORTANT:** Keep your encryption key secure! If lost, encrypted API keys cannot be recovered.

5. **Start all services:**
```bash
docker-compose up -d
```

This will:
- Build the UnifiedLLM image
- Pull GPT-Load and uni-api images
- Create volumes for data persistence
- Start all services with health checks

6. **Verify deployment:**
```bash
docker-compose ps
```

All services should show "Up (healthy)".

7. **Access the web UI:**

Open your browser: **http://localhost:8000**

### Common Docker Commands

```bash
# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f unifiedllm

# Restart services
docker-compose restart

# Stop services
docker-compose stop

# Start services
docker-compose start

# Rebuild and restart
docker-compose up -d --build

# Remove everything (WARNING: deletes all data)
docker-compose down -v
```

## Usage Workflow

### 1. Add Providers

1. Open the web UI at http://localhost:8000
2. Click "Add Provider"
3. Enter provider details:
   - Name (e.g., "OpenAI")
   - Base URL (e.g., "https://api.openai.com")
   - API Key
   - Channel Type (e.g., "openai")
4. Click "Test Connection" to verify
5. Click "Add Provider"

### 2. Fetch Models

1. Select a provider from the dashboard
2. Click "Fetch Models"
3. Wait for the model list to load

### 3. Normalize Model Names

1. View the model list for a provider
2. Click "Edit" next to a model
3. Enter a normalized name (e.g., rename "gpt-4-turbo-preview" to "gpt-4-turbo")
4. Save changes

The system will automatically detect duplicates and suggest provider splitting.

### 4. Sync Configuration

1. Click "Sync" in the dashboard
2. Wait for the sync process to complete
3. The system will:
   - Create GPT-Load groups via API
   - Generate uni-api configuration
   - Update both services

### 5. Use the Unified API

After syncing, make API calls through uni-api:

```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-user-key" \
  -d '{
    "model": "gpt-4-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Docker Configuration

### Environment Variables

Edit `.env` to customize your deployment:

#### Required Variables

- `ENCRYPTION_KEY` - Fernet encryption key for API key storage (REQUIRED)
- `GPTLOAD_AUTH_KEY` - Authentication key for GPT-Load API (REQUIRED)

#### Optional Variables

- `UNIFIEDLLM_PORT` - Port for UnifiedLLM UI (default: 8000)
- `GPTLOAD_PORT` - Port for GPT-Load API (default: 3001)
- `UNI_API_PORT` - Port for uni-api (default: 8001)
- `GPTLOAD_IMAGE` - GPT-Load Docker image (default: ghcr.io/gptload/gptload:latest)
- `UNI_API_IMAGE` - uni-api Docker image (default: yym68686/uni-api:latest)

### Port Mappings

By default, services are exposed on:

- **UnifiedLLM**: http://localhost:8000
- **GPT-Load**: http://localhost:3001
- **uni-api**: http://localhost:8001

To change ports, edit the corresponding variables in `.env`.

### Data Persistence

Data is persisted using Docker volumes:

- `unifiedllm-data` - UnifiedLLM database
- `gptload-data` - GPT-Load database and configuration
- `uni-api-config` - Shared uni-api configuration file

#### Backup Data

```bash
# Backup UnifiedLLM database
docker run --rm -v unifiedllm_unifiedllm-data:/data -v $(pwd):/backup alpine tar czf /backup/unifiedllm-backup.tar.gz -C /data .

# Backup GPT-Load data
docker run --rm -v unifiedllm_gptload-data:/data -v $(pwd):/backup alpine tar czf /backup/gptload-backup.tar.gz -C /data .
```

## Troubleshooting

### Service Won't Start

Check the logs:
```bash
docker-compose logs <service-name>
```

Common issues:
1. **Missing encryption key**: Ensure `ENCRYPTION_KEY` is set in `.env`
2. **Port already in use**: Change port mappings in `.env`
3. **Insufficient resources**: Ensure Docker has enough memory allocated

### Cannot Connect to GPT-Load

1. Verify GPT-Load is running: `docker-compose ps gptload`
2. Check GPT-Load logs: `docker-compose logs gptload`
3. Verify `GPTLOAD_AUTH_KEY` matches in both services
4. Ensure services are on the same network

### Database Errors

Reset the database:
```bash
docker-compose stop
docker volume rm unifiedllm_unifiedllm-data
docker-compose up -d
```

**WARNING:** This deletes all data!

### Health Check Failures

Check service health:
```bash
docker-compose ps
docker inspect --format='{{json .State.Health}}' unifiedllm | jq
```

### Port Already in Use

Edit `.env` and change the port:
```env
UNIFIEDLLM_PORT=8080
```

Then restart:
```bash
docker-compose up -d
```

## Local Development (Without Docker)

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd unifiedllm
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file:**
```bash
cp .env.example .env
```

5. **Generate encryption key:**

Choose one of these methods:
```bash
# Method 1: Python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Method 2: OpenSSL
openssl rand -base64 32

# Method 3: Docker
docker run --rm python:3.11-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

6. **Update `.env` file:**
   - Set `ENCRYPTION_KEY` to the generated key
   - Set `GPTLOAD_URL` to `http://localhost:3001`
   - Set `GPTLOAD_AUTH_KEY` for GPT-Load integration

### Running the Application

```bash
python run.py
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

### Development Tools

**Install development dependencies:**
```bash
pip install -r requirements-dev.txt
```

**Run tests:**
```bash
pytest
```

**Code formatting:**
```bash
black app/
ruff check app/
```

## Project Structure

```
unifiedllm/
├── app/
│   ├── api/              # API endpoints
│   │   ├── config.py     # Configuration sync endpoints
│   │   ├── models.py     # Model management endpoints
│   │   └── providers.py  # Provider management endpoints
│   ├── database/         # Database configuration
│   ├── models/           # SQLAlchemy models
│   │   ├── provider.py   # Provider model
│   │   ├── model.py      # Model model
│   │   ├── gptload_group.py  # GPT-Load group tracking
│   │   └── sync_record.py    # Sync history
│   ├── services/         # Business logic services
│   │   ├── provider_service.py      # Provider CRUD
│   │   ├── model_service.py         # Model normalization
│   │   ├── gptload_client.py        # GPT-Load API client
│   │   ├── config_generator.py      # Configuration generation
│   │   ├── sync_service.py          # Sync orchestration
│   │   └── encryption_service.py    # API key encryption
│   ├── static/           # Web UI files
│   ├── config.py         # Application configuration
│   └── main.py           # FastAPI application
├── data/                 # SQLite database (created at runtime)
├── tests/                # Test files
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Multi-service orchestration
├── pyproject.toml        # Project metadata
├── requirements.txt      # Python dependencies
├── run.py                # Application runner
└── .env.example          # Environment variables template
```

## API Endpoints

### Health & Stats
- `GET /api/health` - Check service health
- `GET /api/stats` - Get system statistics

### Provider Management
- `POST /api/providers` - Add new provider
- `GET /api/providers` - List all providers
- `GET /api/providers/{id}` - Get provider details
- `PUT /api/providers/{id}` - Update provider
- `DELETE /api/providers/{id}` - Delete provider
- `POST /api/providers/{id}/fetch-models` - Fetch models from provider
- `POST /api/providers/{id}/test` - Test provider connectivity

### Model Management
- `GET /api/providers/{id}/models` - List models for provider
- `PUT /api/models/{id}/normalize` - Normalize model name
- `DELETE /api/models/{id}` - Delete model
- `POST /api/models/bulk-delete` - Bulk delete models
- `POST /api/models/{id}/reset` - Reset model name

### Configuration
- `POST /api/config/sync` - Trigger configuration sync
- `GET /api/config/sync/status` - Get sync status
- `GET /api/config/sync/history` - Get sync history
- `GET /api/config/uni-api/download` - Download uni-api YAML

## Security Considerations

1. **Encryption Key**: Keep your `ENCRYPTION_KEY` secure and never commit it to version control
2. **GPT-Load Auth Key**: Use a strong, unique authentication key
3. **Network Exposure**: By default, all services are exposed on localhost. For production:
   - Use a reverse proxy (nginx, Traefik)
   - Enable HTTPS/TLS
   - Restrict network access
4. **API Keys**: All provider API keys are encrypted at rest using Fernet encryption
5. **Backups**: Regularly backup your data volumes

## Production Deployment

For production use, consider:

1. **Use a reverse proxy with HTTPS**
2. **Set resource limits** in docker-compose.yml
3. **Use external database** (PostgreSQL instead of SQLite)
4. **Enable monitoring** (Prometheus, Grafana)
5. **Implement backup strategy** (automated daily backups)
6. **Use secrets management** (Docker secrets, Vault)

Example resource limits:
```yaml
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 1G
```

## Updating

### Using Pre-built Images (Recommended)

To update to the latest version:

```bash
# Pull the latest image
docker-compose pull

# Restart with new image
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Building from Source

To update when building locally:

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d

# Check logs
docker-compose logs -f
```

## Support

For issues and questions:

- Check the logs: `docker-compose logs`
- Review the API documentation: http://localhost:8000/docs
- Open an issue on GitHub

## License

MIT
