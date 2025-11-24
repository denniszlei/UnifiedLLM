# GPT-Load API Documentation

## Table of Contents
1. [Authentication](#authentication)
2. [Group Management](#group-management)
3. [Key Management](#key-management)
4. [Dashboard](#dashboard)
5. [Logs](#logs)
6. [Settings](#settings)
7. [System](#system)
8. [Proxy](#proxy)

## Authentication

### Login
- **Endpoint**: `POST /api/auth/login`
- **Description**: Authenticate and get access to protected API endpoints
- **Request**:
  ```json
  {
    "auth_key": "your-auth-key"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Authentication successful"
  }
  ```

## Group Management

### Create Group
- **Endpoint**: `POST /api/groups`
- **Description**: Create a new group (standard or aggregate)
- **Request**:
  ```json
  {
    "name": "my-group",
    "display_name": "My Group",
    "description": "A sample group",
    "group_type": "standard",  // "standard" or "aggregate"
    "channel_type": "openai",  // "openai", "gemini", "anthropic", etc.
    "upstreams": [
      {
        "url": "https://api.openai.com",
        "weight": 10
      }
    ],
    "test_model": "gpt-4.1-mini",
    "validation_endpoint": "/v1/chat/completions",
    "param_overrides": {
      "temperature": 0.7
    },
    "model_redirect_rules": {
      "gpt-4": "gpt-4.1-mini"
    },
    "model_redirect_strict": false,
    "config": {
      "request_timeout": 600,
      "max_retries": 3
    },
    "header_rules": [
      {
        "key": "X-Custom-Header",
        "value": "custom-value",
        "action": "set"
      }
    ],
    "proxy_keys": "proxy-key-1,proxy-key-2"
  }
  ```
- **Response**: Group object with all properties

### List Groups
- **Endpoint**: `GET /api/groups`
- **Description**: Get all groups
- **Response**:
  ```json
  [
    {
      "id": 1,
      "name": "my-group",
      "display_name": "My Group",
      "endpoint": "http://localhost:3001/proxy/my-group",
      "group_type": "standard",
      "channel_type": "openai",
      "test_model": "gpt-4.1-mini",
      "upstreams": [
        {
          "url": "https://api.openai.com",
          "weight": 10
        }
      ],
      "param_overrides": {},
      "model_redirect_rules": {},
      "model_redirect_strict": false,
      "config": {},
      "header_rules": [],
      "proxy_keys": "",
      "last_validated_at": null,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
  ```

### Get Group List (Lightweight)
- **Endpoint**: `GET /api/groups/list`
- **Description**: Get a lightweight list of groups with only ID, name, and display name
- **Response**:
  ```json
  [
    {
      "id": 1,
      "name": "my-group",
      "display_name": "My Group"
    }
  ]
  ```

### Get Group Config Options
- **Endpoint**: `GET /api/groups/config-options`
- **Description**: Get available configuration options for groups
- **Response**:
  ```json
  [
    {
      "key": "request_timeout",
      "name": "Request Timeout",
      "description": "Request timeout in seconds",
      "default_value": 600
    }
  ]
  ```

### Update Group
- **Endpoint**: `PUT /api/groups/{id}`
- **Description**: Update an existing group
- **Request**:
  ```json
  {
    "name": "updated-group",
    "display_name": "Updated Group",
    "upstreams": [
      {
        "url": "https://api.openai.com",
        "weight": 20
      }
    ],
    "model_redirect_rules": {
      "gpt-4": "gpt-4.1-mini",
      "gpt-3.5": "gpt-3.5-turbo"
    }
  }
  ```
- **Response**: Updated group object

### Delete Group
- **Endpoint**: `DELETE /api/groups/{id}`
- **Description**: Delete a group and all its keys
- **Response**: Success message

### Get Group Stats
- **Endpoint**: `GET /api/groups/{id}/stats`
- **Description**: Get statistics for a specific group
- **Response**:
  ```json
  {
    "key_stats": {
      "total_keys": 10,
      "active_keys": 8,
      "invalid_keys": 2
    },
    "stats_24_hour": {
      "total_requests": 100,
      "failed_requests": 5,
      "failure_rate": 0.05
    },
    "stats_7_day": {
      "total_requests": 500,
      "failed_requests": 20,
      "failure_rate": 0.04
    },
    "stats_30_day": {
      "total_requests": 2000,
      "failed_requests": 80,
      "failure_rate": 0.04
    }
  }
  ```

### Copy Group
- **Endpoint**: `POST /api/groups/{id}/copy`
- **Description**: Copy a group with optional key copying
- **Request**:
  ```json
  {
    "copy_keys": "all"  // "none", "valid_only", "all"
  }
  ```
- **Response**: New group object

### Get Sub Groups (for Aggregate Groups)
- **Endpoint**: `GET /api/groups/{id}/sub-groups`
- **Description**: Get sub-groups of an aggregate group
- **Response**:
  ```json
  [
    {
      "group": {
        "id": 2,
        "name": "sub-group-1",
        "display_name": "Sub Group 1",
        // ... other group properties
      },
      "weight": 10,
      "total_keys": 5,
      "active_keys": 4,
      "invalid_keys": 1
    }
  ]
  ```

### Add Sub Groups (for Aggregate Groups)
- **Endpoint**: `POST /api/groups/{id}/sub-groups`
- **Description**: Add sub-groups to an aggregate group
- **Request**:
  ```json
  {
    "sub_groups": [
      {
        "group_id": 2,
        "weight": 10
      },
      {
        "group_id": 3,
        "weight": 20
      }
    ]
  }
  ```
- **Response**: Success message

### Update Sub Group Weight
- **Endpoint**: `PUT /api/groups/{id}/sub-groups/{subGroupId}/weight`
- **Description**: Update the weight of a sub-group
- **Request**:
  ```json
  {
    "weight": 15
  }
  ```
- **Response**: Success message

### Delete Sub Group
- **Endpoint**: `DELETE /api/groups/{id}/sub-groups/{subGroupId}`
- **Description**: Remove a sub-group from an aggregate group
- **Response**: Success message

### Get Parent Aggregate Groups
- **Endpoint**: `GET /api/groups/{id}/parent-aggregate-groups`
- **Description**: Get aggregate groups that include this group as a sub-group
- **Response**:
  ```json
  [
    {
      "group_id": 1,
      "name": "aggregate-group",
      "display_name": "Aggregate Group",
      "weight": 10
    }
  ]
  ```

## Key Management

### List Keys in Group
- **Endpoint**: `GET /api/keys?group_id={groupId}&status={status}&key_value={search}`
- **Description**: Get all keys in a specific group
- **Parameters**:
  - `group_id`: Required group ID
  - `status`: Optional filter by status ("active", "invalid", or omit for all)
  - `key_value`: Optional search by key value
- **Response**:
  ```json
  {
    "items": [
      {
        "id": 1,
        "key_value": "sk-xxx-xxx",
        "status": "active",
        "notes": "My OpenAI key",
        "request_count": 100,
        "failure_count": 2,
        "last_used_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 10,
    "pages": 1
  }
  ```

### Export Keys
- **Endpoint**: `GET /api/keys/export?group_id={groupId}&status={status}`
- **Description**: Export keys to a text file
- **Parameters**:
  - `group_id`: Required group ID
  - `status`: Optional status filter ("all", "active", "invalid")

### Add Multiple Keys
- **Endpoint**: `POST /api/keys/add-multiple`
- **Description**: Add multiple keys to a group
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**: Result with added count

### Add Multiple Keys (Async)
- **Endpoint**: `POST /api/keys/add-async`
- **Description**: Add multiple keys asynchronously
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**: Task status

### Delete Multiple Keys
- **Endpoint**: `POST /api/keys/delete-multiple`
- **Description**: Delete multiple keys from a group
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**: Result with deleted count

### Delete Multiple Keys (Async)
- **Endpoint**: `POST /api/keys/delete-async`
- **Description**: Delete multiple keys asynchronously
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**: Task status

### Restore Multiple Keys
- **Endpoint**: `POST /api/keys/restore-multiple`
- **Description**: Restore multiple invalid keys
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**: Result with restored count

### Restore All Invalid Keys
- **Endpoint**: `POST /api/keys/restore-all-invalid`
- **Description**: Restore all invalid keys in a group
- **Request**:
  ```json
  {
    "group_id": 1
  }
  ```
- **Response**: Success message with count

### Clear All Invalid Keys
- **Endpoint**: `POST /api/keys/clear-all-invalid`
- **Description**: Delete all invalid keys in a group
- **Request**:
  ```json
  {
    "group_id": 1
  }
  ```
- **Response**: Success message with count

### Clear All Keys
- **Endpoint**: `POST /api/keys/clear-all`
- **Description**: Delete all keys in a group
- **Request**:
  ```json
  {
    "group_id": 1
  }
  ```
- **Response**: Success message with count

### Validate Group Keys
- **Endpoint**: `POST /api/keys/validate-group`
- **Description**: Start validation for all keys in a group
- **Request**:
  ```json
  {
    "group_id": 1,
    "status": "active"  // Optional: "active", "invalid", or omit for all
  }
  ```
- **Response**: Task status

### Test Multiple Keys
- **Endpoint**: `POST /api/keys/test-multiple`
- **Description**: Test multiple keys without changing their status
- **Request**:
  ```json
  {
    "group_id": 1,
    "keys_text": "sk-key1\nsk-key2\nsk-key3"
  }
  ```
- **Response**:
  ```json
  {
    "results": [
      {
        "key": "sk-key1",
        "valid": true,
        "error": null
      }
    ],
    "total_duration": 1500
  }
  ```

### Update Key Notes
- **Endpoint**: `PUT /api/keys/{id}/notes`
- **Description**: Update notes for a specific key
- **Request**:
  ```json
  {
    "notes": "Updated notes for this key"
  }
  ```
- **Response**: Success message

## Dashboard

### Get Dashboard Stats
- **Endpoint**: `GET /api/dashboard/stats`
- **Description**: Get dashboard statistics
- **Response**:
  ```json
  {
    "key_count": {
      "value": 100.0,
      "sub_value": 10,
      "sub_value_tip": "Invalid Keys",
      "trend": 0.0,
      "trend_is_growth": true
    },
    "rpm": {
      "value": 5.0,
      "trend": 10.0,
      "trend_is_growth": true
    },
    "request_count": {
      "value": 1000.0,
      "trend": 5.0,
      "trend_is_growth": true
    },
    "error_rate": {
      "value": 2.5,
      "trend": -1.0,
      "trend_is_growth": false
    },
    "security_warnings": [
      {
        "type": "AUTH_KEY",
        "message": "Auth key is too short",
        "severity": "high",
        "suggestion": "Use a stronger auth key"
      }
    ]
  }
  ```

### Get Dashboard Chart
- **Endpoint**: `GET /api/dashboard/chart?groupId={groupId}`
- **Description**: Get chart data for dashboard
- **Parameters**:
  - `groupId`: Optional group ID to filter by group
- **Response**:
  ```json
  {
    "labels": [
      "2024-01-01T00:00:00Z",
      "2024-01-01T01:00:00Z"
    ],
    "datasets": [
      {
        "label": "Success Requests",
        "data": [10, 15],
        "color": "rgba(10, 200, 110, 1)"
      },
      {
        "label": "Failed Requests",
        "data": [1, 0],
        "color": "rgba(255, 70, 70, 1)"
      }
    ]
  }
  ```

### Get Encryption Status
- **Endpoint**: `GET /api/dashboard/encryption-status`
- **Description**: Check encryption configuration status
- **Response**:
  ```json
  {
    "has_mismatch": false,
    "scenario_type": "",
    "message": "",
    "suggestion": ""
  }
  ```

## Logs

### Get Request Logs
- **Endpoint**: `GET /api/logs?group_id={groupId}&status={status}&model={model}&start_date={date}&end_date={date}&page={page}&size={size}`
- **Description**: Get request logs with filtering
- **Parameters**:
  - `group_id`: Optional group ID filter
  - `status`: Optional status filter ("success", "failure")
  - `model`: Optional model filter
  - `start_date`: Optional start date filter
  - `end_date`: Optional end date filter
  - `page`: Page number (default: 1)
  - `size`: Page size (default: 20)
- **Response**:
  ```json
  {
    "items": [
      {
        "id": "log-id",
        "timestamp": "2024-01-01T00:00:00Z",
        "group_id": 1,
        "group_name": "my-group",
        "parent_group_id": 2,
        "parent_group_name": "aggregate-group",
        "key_hash": "hash-value",
        "model": "gpt-4.1-mini",
        "is_success": true,
        "source_ip": "127.0.0.1",
        "status_code": 200,
        "request_path": "/v1/chat/completions",
        "duration": 1500,
        "error_message": null,
        "user_agent": "user-agent",
        "request_type": "final",
        "upstream_addr": "https://api.openai.com",
        "is_stream": false,
        "request_body": "{\"model\": \"gpt-4.1-mini\", ...}"
      }
    ],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
  }
  ```

### Export Logs
- **Endpoint**: `GET /api/logs/export?group_id={groupId}&status={status}&model={model}&start_date={date}&end_date={date}`
- **Description**: Export request logs as CSV

## Settings

### Get Settings
- **Endpoint**: `GET /api/settings`
- **Description**: Get all system settings grouped by category
- **Response**:
  ```json
  [
    {
      "category_name": "Basic Settings",
      "settings": [
        {
          "key": "app_url",
          "name": "Project URL",
          "description": "Project base URL",
          "value": "http://localhost:3001",
          "default_value": "http://localhost:3001",
          "type": "string",
          "category": "Basic Settings",
          "required": false
        }
      ]
    }
  ]
  ```

### Update Settings
- **Endpoint**: `PUT /api/settings`
- **Description**: Update system settings
- **Request**:
  ```json
  {
    "app_url": "https://my-app.com",
    "proxy_keys": "new-proxy-key"
  }
  ```
- **Response**: Success message

## System

### Get Channel Types
- **Endpoint**: `GET /api/channel-types`
- **Description**: Get available channel types
- **Response**:
  ```json
  ["openai", "gemini", "anthropic"]
  ```

### Get Task Status
- **Endpoint**: `GET /api/tasks/status`
- **Description**: Get status of background tasks
- **Response**:
  ```json
  {
    "status": "idle",
    "message": "No active tasks"
  }
  ```

### Health Check
- **Endpoint**: `GET /health`
- **Description**: Health check endpoint
- **Response**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2024-01-01T00:00:00Z",
    "uptime": "1h2m3s"
  }
  ```

## Proxy

### Proxy Request
- **Endpoint**: `ANY /proxy/{group_name}/*path`
- **Description**: Proxy requests to upstream services through a specific group
- **Usage**:
  ```
  # Original OpenAI request:
  curl -X POST https://api.openai.com/v1/chat/completions \
    -H "Authorization: Bearer sk-original-key" \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "Hello"}]}'
  
  # GPT-Load proxy request:
  curl -X POST http://localhost:3001/proxy/my-group/v1/chat/completions \
    -H "Authorization: Bearer proxy-key" \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "Hello"}]}'
  ```

## Special Features

### Model Redirect Rules
Model redirect rules allow mapping requests from one model name to another. This is useful for:
- Using newer models transparently
- Redirecting to specific model versions
- Load balancing across different models

**Configuration**:
```json
{
  "model_redirect_rules": {
    "gpt-4": "gpt-4.1-mini",
    "gpt-3.5": "gpt-3.5-turbo"
  },
  "model_redirect_strict": false
}
```

**When `model_redirect_strict` is true**: Only models in the redirect rules are allowed.
**When `model_redirect_strict` is false**: Models not in the rules are passed through unchanged.

### Group Types

#### Standard Groups
Standard groups represent individual AI service endpoints with their own upstream servers and keys.

**Request Body**:
```json
{
  "name": "openai-standard",
  "group_type": "standard",
  "channel_type": "openai",
  "upstreams": [
    {
      "url": "https://api.openai.com",
      "weight": 10
    }
  ],
  "test_model": "gpt-4.1-mini",
  "validation_endpoint": "/v1/chat/completions"
}
```

#### Aggregate Groups
Aggregate groups combine multiple standard groups and distribute requests between them based on weights.

**Request Body**:
```json
{
  "name": "openai-aggregate",
  "group_type": "aggregate",
  "channel_type": "openai",
  "test_model": "-",  // Always "-" for aggregate groups
  "model_redirect_rules": {}  // Not allowed for aggregate groups
}
```

**Adding sub-groups to aggregate group**:
```json
{
  "sub_groups": [
    {
      "group_id": 2,
      "weight": 30
    },
    {
      "group_id": 3,
      "weight": 70
    }
  ]
}
```

### Header Rules
Header rules allow adding or removing headers in requests:

**Request Body**:
```json
{
  "header_rules": [
    {
      "key": "X-Custom-Header",
      "value": "custom-value",
      "action": "set"
    },
    {
      "key": "X-Remove-Header",
      "value": "",
      "action": "remove"
    }
  ]
}
```

## Response Format

Successful responses follow this format:
```json
{
  "code": 0,
  "message": "Success message",
  "data": { ... }
}
```

Error responses follow this format:
```json
{
  "code": "ERROR_CODE",
  "message": "Error message"
}
```

Common error codes:
- `VALIDATION_ERROR`: Invalid input parameters
- `DATABASE_ERROR`: Database operation failed
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `NO_KEYS_AVAILABLE`: No valid keys available for the request
- `INTERNAL_SERVER_ERROR`: Internal server error
- `TASK_IN_PROGRESS`: Background task already running