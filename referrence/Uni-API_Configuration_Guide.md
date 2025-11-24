# uni-api API Configuration Guide

## Overview

`api.yaml` is the core configuration file for the uni-api project, used to define AI service providers, API keys, and various preference settings. Through this configuration file, you can configure multiple AI service providers and assign different access permissions to different users.

## Configuration Structure

```yaml
providers:          # Service provider configuration list
  - provider:       # Service provider identifier
    base_url:       # API base URL
    api:            # API key
    model:          # Supported model list
    preferences:    # Service provider specific preferences

api_keys:           # User API key configuration list
  - api:            # User API key
    role:           # User role
    model:          # Accessible models
    preferences:    # User specific preferences

preferences:        # Global preferences
```

## providers Configuration Items

### provider
- **Type**: String
- **Description**: Unique identifier for the service provider
- **Example**: `openai`, `anthropic`, `google`

### base_url
- **Type**: String
- **Description**: Base URL for the service provider's API. For OpenAI format providers, the base_url must be filled completely and must end with `/v1/chat/completions`. For some special providers (like Gemini), base_url supports v1beta/v1 format, for use with Gemini models only.
- **Examples**:
  - OpenAI: `https://api.openai.com/v1/chat/completions`
  - Anthropic: `https://api.anthropic.com/v1/messages`
  - Google: `https://generativelanguage.googleapis.com/v1beta`
  - Azure: `https://your-endpoint.openai.azure.com`

### api
- **Type**: String or List of Strings
- **Description**: API key(s) for the service provider, can be a single key or a list of multiple keys
- **Examples**:
  ```yaml
  api: "sk-your-api-key"  # Single key
  # Or
  api:                    # Multiple keys
    - "sk-first-api-key"
    - "sk-second-api-key"
    - "sk-third-api-key"
  ```

### model
- **Type**: List of Strings or List of Dictionaries
- **Description**: List of models supported by this provider, supports model name mapping
- **Examples**:
  ```yaml
  model:
    - "gpt-4o"                    # Directly specify model
    - "gpt-4o": "custom-gpt-4o"   # Model name mapping, maps requested gpt-4o to custom-gpt-4o
    - "claude-3-5-sonnet-20241022"
  ```

### tools
- **Type**: Boolean
- **Description**: Whether to enable tool calling support, defaults to `true`

### preferences
Provider-specific preference settings, containing the following sub-items:

#### proxy
- **Type**: String
- **Description**: Proxy server address
- **Examples**: 
  - HTTP proxy: `http://proxy.example.com:8080`
  - SOCKS5 proxy: `socks5://127.0.0.1:1080`

#### headers
- **Type**: Object
- **Description**: Additional request headers
- **Example**:
  ```yaml
  headers:
    Custom-Header: "value"
    X-Custom-Auth: "token"
  ```

#### api_key_rate_limit
- **Type**: Object
- **Description**: API key rate limiting
- **Format**: `"count/time_unit"`, supports `s` (seconds), `m` (minutes), `h` (hours), `d` (days)
- **Example**:
  ```yaml
  api_key_rate_limit:
    default: "100/min"  # Default 100 requests per minute
    "gpt-4*": "50/min"  # Rate limit for specific models
  ```

#### api_key_schedule_algorithm
- **Type**: String
- **Description**: Scheduling algorithm for multiple API keys
- **Options**:
  - `round_robin`: Round-robin scheduling (default)
  - `random`: Random scheduling
  - `fixed_priority`: Fixed priority scheduling
  - `smart_round_robin`: Smart round-robin scheduling (sorted by success rate)

#### cooldown_period
- **Type**: Integer
- **Description**: Channel cooldown time in seconds, puts channel in cooldown state when errors occur

#### model_timeout
- **Type**: Object
- **Description**: Model timeout settings
- **Example**:
  ```yaml
  model_timeout:
    default: 120     # Default 120 seconds timeout
    "gpt-4*": 180    # gpt-4 series models 180 seconds timeout
  ```

#### model_price
- **Type**: Object
- **Description**: Model price settings (cost per million tokens)
- **Format**: `"prompt_price,completion_price"`
- **Example**:
  ```yaml
  model_price:
    default: "0.3,1"   # Default price: 0.3 USD/million tokens for input, 1 USD/million tokens for output
    "gpt-4*": "1.5,5"  # gpt-4 series model prices
  ```

#### post_body_parameter_overrides
- **Type**: Object
- **Description**: Request body parameter overrides
- **Example**:
  ```yaml
  post_body_parameter_overrides:
    stream: true       # Force enable streaming response
    temperature: 0.7   # Override temperature parameter
  ```

## api_keys Configuration Items

### api
- **Type**: String
- **Description**: User's API key, recommended to start with `sk-`
- **Example**: `sk-user-api-key`

### role
- **Type**: String
- **Description**: User role
- **Options**:
  - `user`: Regular user (default)
  - `admin`: Administrator user (can access management APIs)

### model
- **Type**: List of Strings
- **Description**: Models that this user can access, supports multiple formats
- **Formats**:
  - `"all"`: Access all models
  - `"provider/model_name"`: Access specific model from specific provider
  - `"provider/*"`: Access all models from specific provider
  - `"model_name"`: Access matching models (without specifying provider)
  - `"<provider/model_name>"`: Treat the entire string as the model name, rather than looking for the model under a specific provider
- **Examples**:
  ```yaml
  model:
    - "all"                          # Access all models
    - "openai/gpt-4o"               # Access openai's gpt-4o model
    - "anthropic/*"                 # Access all anthropic models
    - "gpt-4*"                       # Access all models matching gpt-4* pattern
    - "<anthropic/claude-3-5-sonnet>" # Treat the entire anthropic/claude-3-5-sonnet as the model name
  ```

### preferences
User-specific preference settings, containing the following sub-items:

#### SCHEDULING_ALGORITHM
- **Type**: String
- **Description**: Model scheduling algorithm
- **Options**:
  - `fixed_priority`: Fixed priority (default)
  - `random`: Random scheduling
  - `weighted_round_robin`: Weighted round-robin scheduling
  - `lottery`: Lottery scheduling

#### AUTO_RETRY
- **Type**: Boolean
- **Description**: Whether to automatically retry failed requests, defaults to `true`

#### ENABLE_MODERATION
- **Type**: Boolean
- **Description**: Whether to enable content moderation, defaults to `false`

#### credits
- **Type**: Number
- **Description**: User credit limit (in USD), -1 means unlimited, defaults to -1

#### rate_limit
- **Type**: String
- **Description**: User API key rate limiting
- **Example**: `"1000/min"` (1000 requests per minute)

#### model_timeout
- **Type**: Object
- **Description**: User-specific model timeout settings
- **Example**:
  ```yaml
  model_timeout:
    default: 120
    "gpt-4*": 180
  ```

#### model_price
- **Type**: Object
- **Description**: User-specific model price settings
- **Example**:
  ```yaml
  model_price:
    default: "0.3,1"
    "gpt-4*": "1.5,5"
  ```

## preferences (Global) Configuration Items

### proxy
- **Type**: String
- **Description**: Global proxy setting, all requests will go through this proxy

### rate_limit
- **Type**: String
- **Description**: Global rate limiting
- **Example**: `"999999/min"` (999999 requests per minute)

### cooldown_period
- **Type**: Integer
- **Description**: Global cooldown time in seconds, defaults to 300 seconds

### model_timeout
- **Type**: Object
- **Description**: Global model timeout settings

### model_price
- **Type**: Object
- **Description**: Global model price settings

### error_triggers
- **Type**: List of Strings
- **Description**: Error trigger word list, when response contains these words it will be treated as an error
- **Example**:
  ```yaml
  error_triggers:
    - "Internal Server Error"
    - "Rate limit"
    - "exceeded"
  ```

### headers
- **Type**: Object
- **Description**: Global request header settings

## Weight Configuration (weights)

When configuring weights in `api_keys`, you can set priorities for different providers/models:

```yaml
api_keys:
  - api: "sk-user-api-key"
    model:
      - "openai/gpt-4o"
      - "anthropic/claude-3-5-sonnet-20241022"
    weights:
      "openai/gpt-4o": 3      # openai's gpt-4o weight is 3
      "anthropic/claude-3-5-sonnet-20241022": 1  # anthropic's claude weight is 1
```

Higher weight means higher probability of being selected.

## Advanced Configuration Examples

### Configure Multiple API Keys for Load Balancing

```yaml
providers:
  - provider: "openai"
    base_url: "https://api.openai.com/v1/chat/completions"
    api:  # Use multiple API keys
      - "sk-first-api-key"
      - "sk-second-api-key"
      - "sk-third-api-key"
    model:
      - "gpt-4o"
    preferences:
      api_key_rate_limit:
        default: "100/min"
      api_key_schedule_algorithm: "round_robin"  # Round-robin use of multiple keys
```

### Configure Model Name Mapping

```yaml
providers:
  - provider: "custom-provider"
    base_url: "https://api.custom-ai.com/v1/chat/completions"
    api: "your-api-key"
    model:
      - "gpt-4o": "custom-gpt-4o"  # Map requested gpt-4o to custom-gpt-4o
      - "claude-3-5-sonnet-20241022": "custom-claude"
```

### Configure Different Prices for Different Models

```yaml
preferences:
  model_price:
    default: "0.3,1"        # Default price
    "gpt-4*": "1.5,5"      # gpt-4 series model prices
    "claude-3*": "0.5,1.5" # Claude 3 series model prices
    "gemini*": "0.1,0.5"   # Gemini series model prices
```

## Important Notes

1. **Security**: Ensure that the `api.yaml` file access permissions are protected, do not expose API keys in publicly accessible locations.

2. **Format**: YAML files are sensitive to indentation, please use spaces instead of tabs for indentation.

3. **Service Restart**: After modifying the `api.yaml` file, you need to restart the uni-api service for the configuration to take effect.

4. **Validate Configuration**: Before deployment, verify the correctness of the YAML file format.

5. **API Key Management**: Regularly rotate API keys to ensure security.

## Troubleshooting

- **Configuration not taking effect**: Check if YAML format is correct, confirm if file path is correct.
- **API calls failing**: Check if API keys are correct, confirm if service provider's base_url is accurate.
- **Model access denied**: Check if the `model` configuration in `api_keys` allows access to specific models.

## API Key Prefix Notes

- API keys starting with `sk-` have special meaning in the system and can be used to inherit other API key functionality.
- Administrator API keys typically have permissions to access management APIs.