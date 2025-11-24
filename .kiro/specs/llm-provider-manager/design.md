# Design Document

## Overview

The LLM Provider Manager is a web-based service that acts as a configuration orchestrator between users and two downstream services: GPT-Load (load balancing gateway) and uni-api (unified API gateway). The system provides a user-friendly interface for managing multiple LLM API providers, normalizing model names, detecting duplicates, and automatically generating configurations for both GPT-Load (via REST API) and uni-api (via YAML file generation).

### Architecture Flow

```
User → LLM Provider Manager UI
         ↓
    [Provider Management]
         ↓
    [Model Normalization & Duplicate Detection]
         ↓
    [Configuration Generation]
         ↓
    ├─→ GPT-Load (via REST API)
    │    ├─→ Standard Groups (per provider)
    │    └─→ Aggregate Groups (for duplicate models)
    │
    └─→ uni-api (via api.yaml file)
         └─→ Points to GPT-Load endpoints
```

### Service Integration

- **LLM Provider Manager** manages provider credentials and model mappings
- **GPT-Load** handles load balancing and proxying to actual LLM providers
- **uni-api** provides a unified interface to end users, routing through GPT-Load

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Provider Manager                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Web UI     │  │   REST API   │  │   Database   │     │
│  │  (Frontend)  │◄─┤   (Backend)  │◄─┤   (SQLite)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                                │
│         │                  ├─────────────────┐             │
│         │                  │                 │             │
│         ▼                  ▼                 ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Provider   │  │Configuration │  │    Sync      │     │
│  │   Service    │  │  Generator   │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
         │                  │                 │
         │                  │                 │
         ▼                  ▼                 ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  LLM Providers  │  │    GPT-Load     │  │     uni-api     │
│  (OpenAI, etc)  │  │  (REST API)     │  │  (api.yaml)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Technology Stack

- **Backend**: Python with FastAPI framework
- **Frontend**: HTML/CSS/JavaScript (vanilla or lightweight framework)
- **Database**: SQLite for simplicity and portability
- **Encryption**: Python cryptography library (Fernet symmetric encryption)
- **HTTP Client**: httpx for async HTTP requests
- **YAML Processing**: PyYAML for uni-api configuration generation
- **Deployment**: Docker with docker-compose for multi-service orchestration

## Components and Interfaces

### 1. Provider Service

**Responsibilities:**
- Manage provider CRUD operations
- Validate provider credentials
- Fetch model lists from providers
- Encrypt/decrypt API keys

**Key Methods:**
```python
class ProviderService:
    async def add_provider(name: str, base_url: str, api_key: str) -> Provider
    async def validate_provider(base_url: str, api_key: str) -> bool
    async def fetch_models(provider_id: int) -> List[Model]
    async def delete_provider(provider_id: int) -> None
    async def list_providers() -> List[Provider]
```

### 2. Model Service

**Responsibilities:**
- Manage model normalization
- Detect duplicate normalized names
- Handle model deletion and restoration
- Track original vs normalized names

**Key Methods:**
```python
class ModelService:
    async def normalize_model(model_id: int, normalized_name: str) -> Model
    async def detect_duplicates(provider_id: int) -> Dict[str, List[Model]]
    async def delete_model(model_id: int) -> None
    async def get_models_by_provider(provider_id: int) -> List[Model]
```

### 3. Configuration Generator

**Responsibilities:**
- Generate GPT-Load group configurations
- Generate uni-api YAML configuration
- Handle provider splitting logic for duplicates
- Manage aggregate group creation

**Key Methods:**
```python
class ConfigurationGenerator:
    async def generate_gptload_config(providers: List[Provider]) -> GPTLoadConfig
    async def generate_uniapi_config(gptload_groups: List[Group]) -> str
    async def split_provider_by_duplicates(provider: Provider) -> List[ProviderSplit]
    async def create_aggregate_groups(normalized_models: Dict[str, List[Group]]) -> List[AggregateGroup]
```

### 4. GPT-Load Client

**Responsibilities:**
- Communicate with GPT-Load REST API
- Create/update/delete standard groups
- Create/update/delete aggregate groups
- Manage sub-group relationships

**Key Methods:**
```python
class GPTLoadClient:
    async def create_standard_group(group_config: StandardGroupConfig) -> Group
    async def add_keys_to_group(group_id: int, api_keys: List[str]) -> None
    async def create_aggregate_group(group_config: AggregateGroupConfig) -> Group
    async def add_sub_groups(aggregate_id: int, sub_groups: List[SubGroup]) -> None
    async def delete_group(group_id: int) -> None
    async def update_group(group_id: int, config: GroupConfig) -> Group
```

### 5. Sync Service

**Responsibilities:**
- Orchestrate configuration synchronization
- Track sync status and history
- Handle errors and retries
- Prevent concurrent syncs

**Key Methods:**
```python
class SyncService:
    async def sync_configuration() -> SyncResult
    async def get_sync_status() -> SyncStatus
    async def get_sync_history() -> List[SyncRecord]
    async def retry_failed_sync(sync_id: int) -> SyncResult
```

### 6. Encryption Service

**Responsibilities:**
- Encrypt API keys before storage
- Decrypt API keys for use
- Manage encryption key lifecycle

**Key Methods:**
```python
class EncryptionService:
    def encrypt(plaintext: str) -> str
    def decrypt(ciphertext: str) -> str
    def initialize_key() -> None
    def validate_key() -> bool
```

## Data Models

### Provider
```python
class Provider(BaseModel):
    id: int
    name: str
    base_url: str
    api_key_encrypted: str  # Encrypted
    channel_type: str  # openai, anthropic, etc.
    created_at: datetime
    updated_at: datetime
    last_fetched_at: Optional[datetime]
```

### Model
```python
class Model(BaseModel):
    id: int
    provider_id: int
    original_name: str
    normalized_name: Optional[str]
    is_active: bool  # False if deleted
    created_at: datetime
    updated_at: datetime
```

### GPTLoadGroup
```python
class GPTLoadGroup(BaseModel):
    id: int
    gptload_group_id: int  # ID from GPT-Load
    name: str
    group_type: str  # standard or aggregate
    provider_id: Optional[int]  # For standard groups
    normalized_model: Optional[str]  # For aggregate groups
    created_at: datetime
```

### SyncRecord
```python
class SyncRecord(BaseModel):
    id: int
    status: str  # pending, in_progress, success, failed
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    changes_summary: Optional[str]
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property Reflection

After analyzing all acceptance criteria, I've identified the following key properties that provide unique validation value without redundancy:

**Provider Management Properties:**
- Property 1 covers provider storage with encryption (subsumes individual encryption checks)
- Property 2 covers cascade deletion (subsumes model deletion checks)
- Property 3 covers API key masking in all contexts

**Model Management Properties:**
- Property 4 covers model normalization and original name preservation
- Property 5 covers duplicate detection and provider splitting (the core algorithm)
- Property 6 covers model name reset as a round-trip property

**Configuration Generation Properties:**
- Property 7 covers GPT-Load standard group creation with correct settings
- Property 8 covers aggregate group creation and sub-group relationships
- Property 9 covers uni-api YAML generation with correct structure
- Property 10 covers configuration consistency after model deletion

**Encryption Properties:**
- Property 11 covers encryption/decryption round-trip

**Sync Properties:**
- Property 12 covers sync operation atomicity and concurrency prevention

### Core Correctness Properties

Property 1: Provider storage with encryption
*For any* provider with name, base URL, and API key, when stored in the system, the retrieved provider should have the same name and base URL, and the API key should be encrypted in storage but decrypt to the original value
**Validates: Requirements 1.2, 10.1, 10.2**

Property 2: Cascade deletion
*For any* provider with associated models, when the provider is deleted, querying for that provider or its models should return empty results
**Validates: Requirements 1.5, 4.1**

Property 3: API key masking
*For any* provider displayed in the UI or API response, the API key field should contain only masked characters and not the actual key value
**Validates: Requirements 1.4, 10.3**

Property 4: Model normalization preserves original
*For any* model that is renamed to a normalized name, the system should preserve the original provider model name and use it for upstream API calls
**Validates: Requirements 3.1, 3.4**

Property 5: Duplicate detection triggers provider splitting
*For any* provider where multiple models are normalized to the same name, the system should automatically split the provider into separate logical groups, one per duplicate normalized name plus one for non-duplicate models
**Validates: Requirements 3.3**


Property 6: Model name reset round-trip
*For any* model that is renamed and then reset, the final name should equal the original provider model name
**Validates: Requirements 3.5**

Property 7: GPT-Load standard group configuration
*For any* provider configuration saved, the created GPT-Load standard group should have model_redirect_strict set to true and model_redirect_rules populated with all normalized model mappings from that provider
**Validates: Requirements 5.1, 5.2**

Property 8: Aggregate group creation for duplicates
*For any* normalized model name that appears in multiple providers, the system should create exactly one GPT-Load aggregate group containing all standard groups that offer that model as sub-groups
**Validates: Requirements 5.3, 5.4**

Property 9: uni-api YAML structure
*For any* generated uni-api configuration, the YAML should contain one provider entry per GPT-Load aggregate group plus one entry per standard group with non-duplicate models, each with empty model lists and correct GPT-Load proxy endpoints
**Validates: Requirements 6.2, 6.3, 6.4, 6.5**

Property 10: Configuration consistency after deletion
*For any* model that is deleted, the generated GPT-Load and uni-api configurations should not include that model in any group or provider entry
**Validates: Requirements 4.2**

Property 11: Encryption round-trip
*For any* API key string, encrypting then decrypting should produce the original string
**Validates: Requirements 10.1, 10.2**

Property 12: Sync operation atomicity
*For any* sync operation in progress, attempting to start another sync should be prevented and the system should notify that a sync is already running
**Validates: Requirements 11.5**

Property 13: Model fetch preserves names
*For any* provider model list fetched from the upstream API, all model names stored in the system should exactly match the names returned by the provider
**Validates: Requirements 2.2, 2.4**

Property 14: Bulk deletion atomicity
*For any* set of models deleted in a bulk operation, either all models should be deleted and configurations updated, or none should be deleted if an error occurs
**Validates: Requirements 4.5**


Property 15: Empty aggregate group cleanup
*For any* aggregate group where all sub-groups are removed, the aggregate group itself should be deleted from GPT-Load
**Validates: Requirements 5.7**

Property 16: Configuration import round-trip
*For any* uni-api configuration generated by the system, importing that configuration should reconstruct the same provider and model structure
**Validates: Requirements 7.2**

Property 17: Sync history persistence
*For any* completed sync operation, querying the sync history should return a record with the correct timestamp and status
**Validates: Requirements 11.4**

Property 18: Provider validation
*For any* provider credentials submitted, the validation should succeed if and only if a test API call to the provider succeeds
**Validates: Requirements 1.1**

Property 19: Duplicate prevention within provider
*For any* attempt to normalize two different models to the same name within a provider, the second normalization should be rejected
**Validates: Requirements 3.2**

Property 20: Test result accuracy
*For any* provider or model tested, the test result should accurately reflect whether the API call succeeded or failed
**Validates: Requirements 12.1, 12.2, 12.3**

Property 21: GPT-Load connection status display
*For any* GPT-Load connection state (reachable or unreachable), the UI should display the appropriate indicator (connected or disconnected) matching the actual connection state
**Validates: Requirements 13.2, 13.3**

Property 22: Delete marking without API calls
*For any* model marked for deletion, no API call should be made until the save button is clicked
**Validates: Requirements 14.1**

Property 23: Delete button state transition
*For any* model, when marked for deletion the delete button should change to a revert button, and when reverted the revert button should change back to a delete button
**Validates: Requirements 14.3, 14.4**

Property 24: Mark-unmark round trip
*For any* model that is marked for deletion then unmarked, the final visual state should match the original state before marking
**Validates: Requirements 14.4**

Property 25: Batch deletion atomicity
*For any* set of models marked for deletion, clicking save should result in a single batch API call containing all marked model IDs
**Validates: Requirements 14.5**

Property 26: Model name edit without API calls
*For any* model name edit, no API call should be made until the save button is clicked
**Validates: Requirements 15.1**

Property 27: Pending changes tracking
*For any* sequence of model name edits, all changes should be stored in the pending changes state until save is clicked
**Validates: Requirements 15.2**

Property 28: Batch save single reload
*For any* save operation with pending changes, the model list should reload exactly once after all batch API calls complete
**Validates: Requirements 15.4**

Property 29: Unsaved changes warning
*For any* navigation attempt with pending changes, the beforeunload warning should be triggered
**Validates: Requirements 15.5**

Property 30: Save button visibility
*For any* UI state, the save button should be visible if and only if there are pending changes (renames or deletions)
**Validates: Requirements 16.1, 16.2**

Property 31: Save confirmation summary accuracy
*For any* save confirmation dialog, the displayed counts for renames and deletions should match the actual number of pending changes
**Validates: Requirements 16.4**

## Error Handling

### Provider Validation Errors
- **Invalid Credentials**: Return HTTP 400 with error message from provider
- **Network Timeout**: Return HTTP 504 with timeout message
- **Invalid Base URL**: Return HTTP 400 with URL format error

### Model Fetch Errors
- **Provider Not Found**: Return HTTP 404
- **API Call Failed**: Return HTTP 502 with provider error message
- **Empty Model List**: Return HTTP 200 with warning flag

### Configuration Sync Errors
- **GPT-Load API Failure**: Log error, mark sync as failed, allow retry
- **Concurrent Sync Attempt**: Return HTTP 409 with message about ongoing sync
- **Invalid Configuration**: Return HTTP 400 with validation errors


### Encryption Errors
- **Missing Encryption Key**: Prevent service startup, log fatal error
- **Decryption Failure**: Return HTTP 500, log error with key ID
- **Invalid Key Format**: Return HTTP 400 during key storage

### Database Errors
- **Connection Failure**: Return HTTP 503, retry with exponential backoff
- **Constraint Violation**: Return HTTP 409 with conflict details
- **Transaction Failure**: Rollback and return HTTP 500

## Testing Strategy

### Unit Testing
The system will use pytest for minimal unit testing focused on core functionality:

**Core Tests:**
- Provider CRUD operations
- Model normalization and duplicate detection
- Provider splitting algorithm
- GPT-Load configuration generation
- uni-api YAML generation
- Encryption/decryption round-trip


### Property-Based Testing (Optional)
For personal use, property-based testing is optional. If implemented, focus on core algorithms:

**Key Properties to Test:**
- Provider splitting with duplicates
- GPT-Load configuration correctness
- uni-api YAML structure
- Encryption round-trip

### Integration Testing (Manual)
- Manually test end-to-end flow from provider addition to configuration sync
- Verify Docker deployment works with all three services
- Test actual GPT-Load API integration
- Verify uni-api can read generated configuration

## Provider Splitting Algorithm

The provider splitting algorithm is a core component that handles duplicate normalized model names within a single provider.

### Algorithm Steps

1. **Group models by normalized name**:
   ```python
   normalized_groups = {}
   for model in provider.models:
       name = model.normalized_name or model.original_name
       if name not in normalized_groups:
           normalized_groups[name] = []
       normalized_groups[name].append(model)
   ```

2. **Identify duplicates and non-duplicates**:
   ```python
   duplicates = {name: models for name, models in normalized_groups.items() if len(models) > 1}
   non_duplicates = [models[0] for name, models in normalized_groups.items() if len(models) == 1]
   ```

3. **Create standard groups**:
   - For each duplicate normalized name, create a separate standard group:
     - Name: `{provider_name}-{index}-{normalized_name}`
     - Contains: Single model with that normalized name
     - model_redirect_rules: `{original_name: normalized_name}`
   
   - If non-duplicates exist, create one standard group:
     - Name: `{provider_name}-no-aggregate_models`
     - Contains: All non-duplicate models
     - model_redirect_rules: Map all original names to normalized names

4. **Create aggregate groups**:
   - For each duplicate normalized name across ALL providers:
     - Name: `{normalized_name}-aggregate`
     - Type: aggregate
     - Sub-groups: All standard groups offering that model
     - Weights: Equal distribution or user-configured

### Example

**Input:**
- ProviderA: `deepseek-v3.1-preview`, `Deepseek-V3.1-preview`, `gpt-4o`
- User normalizes: `deepseek-v3.1-preview` → `deepseek-v3.1`, `Deepseek-V3.1-preview` → `deepseek-v3.1`

**Output:**
- Standard Groups:
  - `providerA-0-deepseek-v3-1` (model_redirect_rules: `{"deepseek-v3.1": "deepseek-v3.1-preview"}`)
  - `providerA-1-deepseek-v3-1` (model_redirect_rules: `{"deepseek-v3.1": "Deepseek-V3.1-preview"}`)
  - `providerA-no-aggregate_models` (contains: `gpt-4o`, no redirect needed)
- Aggregate Groups:
  - `deepseek-v3-1-aggregate` (sub-groups: providerA-0, providerA-1)

**Note**: Group names sanitize dots to dashes, but model names in model_redirect_rules preserve original characters


## GPT-Load Configuration Generation

### Standard Group Configuration

For each provider (or provider split), create a standard group:

```json
{
  "name": "providerA-0-deepseek-v3-1",
  "display_name": "Provider A - deepseek-v3.1",
  "group_type": "standard",
  "channel_type": "openai",
  "upstreams": [
    {
      "url": "https://api.providerA.com",
      "weight": 10
    }
  ],
  "test_model": "deepseek-v3.1",
  "validation_endpoint": "/v1/chat/completions",
  "model_redirect_rules": {
    "deepseek-v3.1": "deepseek-v3.1-preview"
  },
  "model_redirect_strict": true
}
```

**Note**: 
- `upstreams.url` contains only the base URL without path
- `model_redirect_rules` maps normalized name (key) to original provider name (value)
- Group names must use only alphanumeric, underscore, and dash characters (dots converted to dashes)
- Model names can contain dots and special characters

### Aggregate Group Configuration

For each duplicate normalized model across providers:

```json
{
  "name": "deepseek-v3-1-aggregate",
  "display_name": "deepseek-v3-1 (Load Balanced)",
  "group_type": "aggregate",
  "channel_type": "openai",
  "test_model": "-"
}
```

Then add sub-groups:
```json
{
  "sub_groups": [
    {
      "group_id": 2,
      "weight": 10
    },
    {
      "group_id": 3,
      "weight": 10
    }
  ]
}
```

### API Calls Sequence

1. Create all standard groups via `POST /api/groups`
2. Store returned group IDs
3. Add API keys to each standard group via `POST /api/keys/add-multiple`:
   ```json
   {
     "group_id": 1,
     "keys_text": "sk-provider-key-1\nsk-provider-key-2"
   }
   ```
4. Identify which standard groups share normalized models
5. Create aggregate groups via `POST /api/groups`
6. Add sub-groups via `POST /api/groups/{id}/sub-groups`


## uni-api Configuration Generation

### YAML Structure

```yaml
providers:
  # Aggregate groups (for duplicate models)
  - provider: "deepseek-v3-1-aggregate"
    base_url: "http://gptload:3001/proxy/deepseek-v3-1-aggregate"
    api: "gptload-auth-key"
    model: []  # Empty to auto-fetch from GPT-Load
    
  # Standard groups (for non-duplicate models)
  - provider: "providerA-no-aggregate"
    base_url: "http://gptload:3001/proxy/providerA-no-aggregate_models"
    api: "gptload-auth-key"
    model: []  # Empty to auto-fetch from GPT-Load

api_keys:
  - api: "sk-user-key"
    role: "user"
    model:
      - "all"

preferences:
  rate_limit: "999999/min"
```

**Note**: base_url contains only the proxy path without `/v1/chat/completions` suffix

### Generation Logic

1. Query all GPT-Load groups from local database
2. For each aggregate group:
   - Create provider entry with aggregate group proxy endpoint
   - Leave model list empty
3. For each standard group with non-duplicate models:
   - Create provider entry with standard group proxy endpoint
   - Leave model list empty
4. Add default api_keys and preferences sections
5. Validate YAML structure
6. Write to file or return as string

## UI Design (ASCII Mockup)

### Dashboard View
```
╔════════════════════════════════════════════════════════════════╗
║  LLM Provider Manager                          [Sync] [Import] ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Providers                                      [+ Add Provider]║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Provider A                    Models: 15    [Edit] [Del] │ ║
║  │ https://api.providerA.com                                │ ║
║  │ API Key: sk-***************                              │ ║
║  │ Last Fetched: 2024-01-15 10:30                           │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Provider B                    Models: 8     [Edit] [Del] │ ║
║  │ https://api.providerB.com                                │ ║
║  │ API Key: sk-***************                              │ ║
║  │ Last Fetched: 2024-01-15 09:15                           │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  Sync Status: ✓ Last sync successful (2024-01-15 10:35)       ║
║  GPT-Load: 12 groups | uni-api: config ready                   ║
║                                                                 ║
╚════════════════════════════════════════════════════════════════╝
```


### Provider Detail View
```
╔════════════════════════════════════════════════════════════════╗
║  Provider A                                    [Fetch Models]  ║
╠════════════════════════════════════════════════════════════════╣
║  Base URL: https://api.providerA.com/v1/chat/completions      ║
║  API Key: sk-*************** [Show] [Edit]                     ║
║  Channel Type: openai                                          ║
║  Last Fetched: 2024-01-15 10:30                                ║
║                                                                 ║
║  Models (15)                                    [Bulk Actions ▼]║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Original Name        │ Normalized Name    │ Actions       │ ║
║  ├──────────────────────┼────────────────────┼───────────────┤ ║
║  │ deepseek-v3.1        │ deepseek-v3-1      │ [Edit] [Del]  │ ║
║  │ Deepseek-V3.1        │ deepseek-v3-1 ⚠️   │ [Edit] [Del]  │ ║
║  │ deepseek-v3.1-latest │ deepseek-v3-1 ⚠️   │ [Edit] [Del]  │ ║
║  │ gpt-4o               │ gpt-4o             │ [Edit] [Del]  │ ║
║  │ gpt-4o-mini          │ gpt-4o-mini        │ [Edit] [Del]  │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  ⚠️ Duplicate detected: 3 models normalized to "deepseek-v3-1" ║
║  → Will create 3 separate groups + 1 aggregate group           ║
║                                                                 ║
║  [Save Changes] [Cancel]                                       ║
╚════════════════════════════════════════════════════════════════╝
```

### Sync Progress View
```
╔════════════════════════════════════════════════════════════════╗
║  Configuration Sync                                            ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Syncing configuration to GPT-Load and uni-api...              ║
║                                                                 ║
║  ✓ Analyzing provider configurations                           ║
║  ✓ Creating standard groups (5/5)                              ║
║  ⏳ Creating aggregate groups (2/3)                            ║
║  ⏹ Generating uni-api configuration                            ║
║                                                                 ║
║  Progress: ████████████░░░░░░░░ 65%                            ║
║                                                                 ║
║  [Cancel]                                                      ║
╚════════════════════════════════════════════════════════════════╝
```


### Add Provider Dialog
```
╔════════════════════════════════════════════════════════════════╗
║  Add New Provider                                              ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Provider Name:                                                ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Provider A                                                │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  Base URL:                                                     ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ https://api.providerA.com/v1/chat/completions            │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  API Key:                                                      ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ sk-proj-••••••••••••••••••••••••••••                     │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  Channel Type:                                                 ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ openai                                              ▼     │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  [Test Connection] [Add Provider] [Cancel]                     ║
╚════════════════════════════════════════════════════════════════╝
```

## Docker Deployment

### docker-compose.yml Structure

```yaml
version: '3.8'

services:
  llm-provider-manager:
    build: ./llm-provider-manager
    ports:
      - "8000:8000"
    environment:
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - GPTLOAD_URL=http://gptload:3001
      - GPTLOAD_AUTH_KEY=${GPTLOAD_AUTH_KEY}
      - DATABASE_URL=sqlite:///data/llm_manager.db
    volumes:
      - llm-manager-data:/app/data
      - ./uni-api-config:/app/uni-api-config
    depends_on:
      - gptload
    networks:
      - llm-network

  gptload:
    image: gptload:latest
    ports:
      - "3001:3001"
    environment:
      - AUTH_KEY=${GPTLOAD_AUTH_KEY}
    volumes:
      - gptload-data:/app/data
    networks:
      - llm-network

  uni-api:
    image: uni-api:latest
    ports:
      - "8001:8001"
    volumes:
      - ./uni-api-config/api.yaml:/app/api.yaml
    depends_on:
      - gptload
    networks:
      - llm-network

volumes:
  llm-manager-data:
  gptload-data:

networks:
  llm-network:
    driver: bridge
```


### Environment Variables

```env
# LLM Provider Manager
ENCRYPTION_KEY=<generate-with-fernet>
GPTLOAD_URL=http://gptload:3001
GPTLOAD_AUTH_KEY=<your-gptload-auth-key>
DATABASE_URL=sqlite:///data/llm_manager.db

# GPT-Load
GPTLOAD_AUTH_KEY=<your-gptload-auth-key>

# Ports
LLM_MANAGER_PORT=8000
GPTLOAD_PORT=3001
UNI_API_PORT=8001
```

### Deployment Steps

1. Clone repository and navigate to project directory
2. Create `.env` file with required environment variables
3. Generate encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. Run `docker-compose up -d`
5. Access LLM Provider Manager UI at `http://localhost:8000`
6. Add providers and configure models
7. Click "Sync" to generate configurations
8. uni-api will automatically use the generated `api.yaml`

## API Endpoints

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
- `POST /api/models/{id}/reset` - Reset model name to original

### Configuration

- `POST /api/config/sync` - Sync configuration to GPT-Load and uni-api
- `GET /api/config/sync/status` - Get sync status
- `GET /api/config/sync/history` - Get sync history
- `GET /api/config/uni-api/download` - Download uni-api YAML
- `POST /api/config/import` - Import existing configuration

### System

- `GET /api/health` - Health check
- `GET /api/stats` - System statistics


## Database Schema

### providers table
```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_fetched_at TIMESTAMP
);
```

### models table
```sql
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    normalized_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, original_name)
);
```

### gptload_groups table
```sql
CREATE TABLE gptload_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gptload_group_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    group_type TEXT NOT NULL CHECK(group_type IN ('standard', 'aggregate')),
    provider_id INTEGER,
    normalized_model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
);
```

### sync_records table
```sql
CREATE TABLE sync_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'in_progress', 'success', 'failed')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    changes_summary TEXT
);
```

## Security Considerations

### API Key Encryption
- Use Fernet symmetric encryption (AES 128-bit)
- Store encryption key in environment variable
- Decrypt keys only in memory, never log decrypted values

### Basic Security
- Validate all input data
- Use parameterized queries for database operations
- Store sensitive data in environment variables


## Performance Considerations

### Database Optimization
- Index frequently queried columns (provider_id, normalized_name)
- Use connection pooling for database access
- Implement caching for provider and model lists
- Use batch operations for bulk updates

### API Performance
- Implement async/await for I/O operations
- Use connection pooling for HTTP clients
- Cache GPT-Load group listings
- Implement request timeout and retry logic

### UI Performance
- Lazy load model lists for providers with many models
- Debounce inline editing operations
- Show loading indicators for long operations
- Implement pagination for large datasets

## Monitoring and Logging

### Logging Strategy
- Log all API requests and responses
- Log configuration sync operations
- Log encryption/decryption operations (without sensitive data)
- Log errors with stack traces
- Use structured logging (JSON format)

### Metrics to Track
- Number of providers configured
- Number of models managed
- Sync operation success/failure rate
- API response times
- Database query performance
- GPT-Load API call latency

### Health Checks
- Database connectivity
- GPT-Load API availability
- Encryption key validity
- Disk space for database and logs

## UX Improvements for Model Management

### GPT-Load Connection Status Display

The UI will display GPT-Load connection information prominently to help users understand the sync target:

**Dashboard Header Enhancement:**
```
┌────────────────────────────────────────────────────────────┐
│ LLM Provider Manager                                       │
│                                                            │
│ GPT-Load: ✓ Connected (http://gptload:3001)              │
│ Last Sync: 2024-01-15 10:35 | 12 groups                  │
│                                                            │
│ [Sync Configuration ⓘ]                                    │
└────────────────────────────────────────────────────────────┘
```

**Connection Status Indicators:**
- **Connected**: Green checkmark with GPT-Load URL
- **Disconnected**: Red X with error message
- **Unknown**: Yellow warning with "Checking..."

**Sync Button Tooltip:**
"Sync Configuration sends your normalized model mappings to GPT-Load (creates groups) and generates uni-api YAML configuration file"

**Implementation:**
- Add `/api/gptload/status` endpoint that checks GPT-Load connectivity
- Poll status every 30 seconds when dashboard is visible
- Display last sync info from sync_records table
- Show group count from gptload_groups table

### Batch Model Editing with Pending Changes

The UI will track all model edits locally and save them in a single batch operation:

**State Management:**
```javascript
// Track pending changes
const pendingChanges = {
  renames: new Map(),      // modelId -> newName
  deletions: new Set(),    // modelId
  hasChanges: false
};

// Update on edit
function handleModelNameEdit(modelId, newName) {
  pendingChanges.renames.set(modelId, newName);
  pendingChanges.hasChanges = true;
  updateUI();
}

// Update on delete mark
function handleDeleteMark(modelId) {
  if (pendingChanges.deletions.has(modelId)) {
    pendingChanges.deletions.delete(modelId);
  } else {
    pendingChanges.deletions.add(modelId);
  }
  pendingChanges.hasChanges = true;
  updateUI();
}
```

**Save Changes Flow:**
1. User clicks "Save Changes" button
2. Show confirmation dialog with summary:
   - "Rename X models"
   - "Delete Y models"
3. On confirm, make batch API calls:
   - `PUT /api/models/batch-normalize` with all renames
   - `DELETE /api/models/batch-delete` with all deletions
4. Reload model list once after both complete
5. Clear pending changes state

**API Endpoints:**
```python
@router.put("/models/batch-normalize")
async def batch_normalize_models(updates: List[ModelNormalization]):
    # Update multiple models in a transaction
    pass

@router.delete("/models/batch-delete")
async def batch_delete_models(model_ids: List[int]):
    # Delete multiple models in a transaction
    pass
```

### Visual Delete Marking

Models marked for deletion will be visually indicated without confirmation dialogs:

**UI States:**
```
Normal State:
┌────────────────────────────────────────────────────────┐
│ deepseek-v3.1  │ deepseek-v3-1  │ [Edit] [Delete]    │
└────────────────────────────────────────────────────────┘

Marked for Deletion:
┌────────────────────────────────────────────────────────┐
│ deepseek-v3.1  │ deepseek-v3-1  │ [Edit] [Revert] 🗑️ │
│ (grayed out with strikethrough)                        │
└────────────────────────────────────────────────────────┘
```

**CSS Styling:**
```css
.model-row.marked-for-deletion {
  opacity: 0.5;
  text-decoration: line-through;
  background-color: #fee;
}

.model-row.marked-for-deletion .model-name-input {
  pointer-events: none;
}
```

**Button State:**
- Normal: "Delete" button (red)
- Marked: "Revert" button (gray) + trash icon indicator

### Save Changes Button and Workflow

A prominent "Save Changes" button will appear when edits are pending:

**Button Visibility:**
```javascript
function updateSaveButton() {
  const saveBtn = document.getElementById('saveChangesBtn');
  const hasChanges = pendingChanges.hasChanges;
  
  if (hasChanges) {
    saveBtn.style.display = 'block';
    saveBtn.classList.add('pulse'); // Subtle animation
    
    // Update badge with change count
    const changeCount = pendingChanges.renames.size + 
                       pendingChanges.deletions.size;
    saveBtn.textContent = `Save Changes (${changeCount})`;
  } else {
    saveBtn.style.display = 'none';
  }
}
```

**Confirmation Dialog:**
```
╔════════════════════════════════════════════════════════╗
║  Confirm Changes                                       ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  You are about to:                                     ║
║  • Rename 5 models                                     ║
║  • Delete 3 models                                     ║
║                                                        ║
║  These changes will be saved to the database.          ║
║                                                        ║
║  [Cancel] [Confirm]                                    ║
╚════════════════════════════════════════════════════════╝
```

**Success Message:**
```
✓ Changes saved successfully!
→ Next step: Click "Sync Configuration" to send your 
  normalized models to GPT-Load and generate uni-api config
```

**Unsaved Changes Warning:**
```javascript
window.addEventListener('beforeunload', (e) => {
  if (pendingChanges.hasChanges) {
    e.preventDefault();
    e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
  }
});
```

### Updated Provider Detail View Mockup

```
╔════════════════════════════════════════════════════════════════╗
║  Provider A                                    [Fetch Models]  ║
║                                                                 ║
║  GPT-Load: ✓ Connected (http://gptload:3001)                  ║
╠════════════════════════════════════════════════════════════════╣
║  Base URL: https://api.providerA.com/v1/chat/completions      ║
║  API Key: sk-*************** [Show] [Edit]                     ║
║  Channel Type: openai                                          ║
║  Last Fetched: 2024-01-15 10:30                                ║
║                                                                 ║
║  Models (15)                          [Save Changes (8)] ⚠️    ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Original Name        │ Normalized Name    │ Actions       │ ║
║  ├──────────────────────┼────────────────────┼───────────────┤ ║
║  │ deepseek-v3.1        │ deepseek-v3-1      │ [Edit][Delete]│ ║
║  │ Deepseek-V3.1        │ deepseek-v3-1 ⚠️   │ [Edit][Delete]│ ║
║  │ deepseek-v3.1-latest │ [edited]           │ [Edit][Delete]│ ║
║  │ ̶o̶l̶d̶-̶m̶o̶d̶e̶l̶          │ ̶o̶l̶d̶-̶m̶o̶d̶e̶l̶        │ [Edit][Revert]🗑️│ ║
║  │ gpt-4o               │ gpt-4o             │ [Edit][Delete]│ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                 ║
║  ⚠️ You have unsaved changes (5 renames, 3 deletions)         ║
║                                                                 ║
║  [Auto-Split Preview...]                                       ║
║                                                                 ║
║  [← Back] [Save Changes (8)]                                   ║
╚════════════════════════════════════════════════════════════════╝
```

## Future Enhancements

### Phase 2 Features
- Multi-user support with role-based access control
- Provider templates for common configurations
- Automated model discovery and normalization suggestions
- Configuration versioning and rollback
- Webhook notifications for sync events
- Advanced load balancing strategies (cost-based, latency-based)

### Phase 3 Features
- Real-time monitoring dashboard
- Cost tracking and budgeting
- A/B testing for model routing
- Machine learning for optimal provider selection
- Integration with additional gateway services
- API usage analytics and reporting

