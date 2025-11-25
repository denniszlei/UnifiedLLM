# Requirements Document

## Introduction

The LLM Provider Manager is a service that unifies multiple LLM API providers (OpenAI, OpenRouter, third-party services, etc.) into a single management interface. The system addresses the challenge of providers offering the same models under different names by providing model normalization, duplicate detection, and automatic configuration generation for both GPT-Load (load balancing) and uni-api (unified API gateway). The service enables users to manage provider credentials, fetch and normalize model lists, and generate deployment-ready configurations for downstream services.

## Glossary

- **Provider**: An LLM API service provider (e.g., OpenAI, OpenRouter, third-party services)
- **Model**: A specific AI model offered by a provider (e.g., gpt-4o, deepseek-v3.1)
- **Normalized Model Name**: A standardized model name after user modification to eliminate duplicates
- **GPT-Load**: A load balancing API gateway service that distributes requests across multiple providers
- **uni-api**: A unified API gateway that integrates different provider services
- **Provider Group**: A logical grouping in GPT-Load representing a single provider endpoint
- **Base URL**: The API endpoint URL for a provider's service
- **API Key**: Authentication credential for accessing a provider's API
- **Model Mapping**: The relationship between original provider model names and normalized names
- **Configuration Sync**: The process of updating GPT-Load and uni-api configurations based on provider changes
- **Docker Deployment**: Containerized deployment of all services (GPT-Load, uni-api, LLM Provider Manager)

## Requirements

### Requirement 1

**User Story:** As a user, I want to add multiple LLM API providers with their credentials, so that I can manage all my provider accounts in one place.

#### Acceptance Criteria

1. WHEN a user submits a provider with base URL and API key THEN the System SHALL validate the credentials by making a test request to the provider
2. WHEN a user adds a provider THEN the System SHALL store the provider name, base URL, and API key securely
3. WHEN credential validation fails THEN the System SHALL display the error message and prevent the provider from being added
4. WHEN a user views the provider list THEN the System SHALL display all added providers with masked API keys
5. WHEN a user deletes a provider THEN the System SHALL remove the provider and all associated model configurations

### Requirement 2

**User Story:** As a user, I want to fetch the latest model list from each provider, so that I can see what models are currently available.

#### Acceptance Criteria

1. WHEN a user requests to fetch models for a provider THEN the System SHALL query the provider's model list endpoint
2. WHEN the model list is retrieved THEN the System SHALL display all models with their original names from the provider
3. WHEN the fetch operation fails THEN the System SHALL display an error message with the failure reason
4. WHEN models are fetched THEN the System SHALL store the original model names with timestamps
5. WHEN a provider returns an empty model list THEN the System SHALL notify the user and allow manual model entry

### Requirement 3

**User Story:** As a user, I want to rename models to standardized names, so that I can eliminate confusion from duplicate or inconsistent naming.

#### Acceptance Criteria

1. WHEN a user renames a model THEN the System SHALL update the model mapping with the new normalized name
2. WHEN a user attempts to create a duplicate normalized name within the same provider THEN the System SHALL prevent the operation and display a warning
3. WHEN duplicate normalized names exist within a provider THEN the System SHALL automatically split the provider into separate logical groups
4. WHEN a model is renamed THEN the System SHALL preserve the original provider model name for API calls
5. WHEN a user resets a model name THEN the System SHALL restore the original provider model name

### Requirement 4

**User Story:** As a user, I want to delete unwanted models from my configuration, so that I only expose the models I intend to use.

#### Acceptance Criteria

1. WHEN a user deletes a model THEN the System SHALL remove it from the active model list
2. WHEN a model is deleted THEN the System SHALL update the generated configurations to exclude the deleted model
3. WHEN all models are deleted from a provider THEN the System SHALL warn the user before proceeding
4. WHEN a deleted model is needed again THEN the System SHALL allow the user to re-fetch models from the provider
5. WHEN a user performs bulk delete operations THEN the System SHALL process all deletions and update configurations atomically

### Requirement 5

**User Story:** As a user, I want the system to automatically generate GPT-Load configuration via API calls, so that my load balancing setup stays synchronized with my provider changes.

#### Acceptance Criteria

1. WHEN a user saves provider configurations THEN the System SHALL create GPT-Load standard groups for each provider with upstream base URL, API keys, and model redirect rules
2. WHEN creating standard groups THEN the System SHALL set model_redirect_strict to true and populate model_redirect_rules with normalized model mappings
3. WHEN multiple providers offer the same normalized model name THEN the System SHALL create a GPT-Load aggregate group for that model
4. WHEN creating aggregate groups THEN the System SHALL add the corresponding standard groups as sub-groups with appropriate weights
5. WHEN GPT-Load API calls fail THEN the System SHALL log the error and notify the user with retry options
6. WHEN a provider is deleted THEN the System SHALL remove the corresponding GPT-Load standard groups and update affected aggregate groups via API calls
7. WHEN all sub-groups are removed from an aggregate group THEN the System SHALL delete the empty aggregate group

### Requirement 6

**User Story:** As a user, I want the system to generate uni-api configuration as a YAML file, so that I can deploy the unified API gateway with my provider setup.

#### Acceptance Criteria

1. WHEN a user requests uni-api configuration generation THEN the System SHALL create a valid api.yaml file following uni-api specifications
2. WHEN generating provider entries THEN the System SHALL create one entry for each GPT-Load aggregate group pointing to its proxy endpoint
3. WHEN generating provider entries THEN the System SHALL create one entry for each GPT-Load standard group whose name ends with "-no-aggregate-models" pointing to its proxy endpoint
4. WHEN generating provider entries THEN the System SHALL NOT include standard groups that are sub-groups of aggregate groups to prevent bypassing load balancing
5. WHEN generating provider entries THEN the System SHALL configure each entry with GPT-Load's base URL, authentication key, and the appropriate group proxy path
6. WHEN generating provider entries THEN the System SHALL leave the model list empty to allow uni-api to automatically fetch available models from GPT-Load
7. WHEN the api.yaml file is generated THEN the System SHALL make it available for download or direct deployment
8. WHEN configuration generation fails THEN the System SHALL display validation errors and prevent invalid configuration export

### Requirement 7

**User Story:** As a user, I want to load existing configurations from GPT-Load and uni-api, so that I can manage and update my current setup without starting from scratch.

#### Acceptance Criteria

1. WHEN a user imports existing GPT-Load configuration THEN the System SHALL fetch groups and keys via the GPT-Load management API
2. WHEN a user imports existing uni-api configuration THEN the System SHALL parse the api.yaml file and extract provider information
3. WHEN existing configurations are loaded THEN the System SHALL merge them with any new provider inputs
4. WHEN conflicts exist between imported and new configurations THEN the System SHALL prompt the user to resolve conflicts
5. WHEN configurations are synchronized THEN the System SHALL update both GPT-Load and uni-api with the merged configuration

### Requirement 8

**User Story:** As a user, I want to deploy all services (GPT-Load, uni-api, and LLM Provider Manager) using Docker, so that I can easily set up and manage the entire system.

#### Acceptance Criteria

1. WHEN a user runs the Docker deployment THEN the System SHALL start all three services in containers
2. WHEN services start THEN the System SHALL configure network connectivity between LLM Provider Manager, GPT-Load, and uni-api
3. WHEN Docker containers are running THEN the System SHALL expose the LLM Provider Manager UI on a configured port
4. WHEN services are deployed THEN the System SHALL persist configuration data using Docker volumes
5. WHEN a service fails to start THEN the System SHALL log the error and provide troubleshooting information

### Requirement 9

**User Story:** As a user, I want a web-based UI to manage providers and models, so that I can easily visualize and modify my configuration.

#### Acceptance Criteria

1. WHEN a user accesses the UI THEN the System SHALL display a dashboard with all providers and their model counts
2. WHEN a user views a provider THEN the System SHALL display the provider details and associated models in a table format
3. WHEN a user modifies model names THEN the System SHALL provide inline editing with real-time duplicate detection
4. WHEN duplicate models are detected THEN the System SHALL highlight them visually and show the auto-split suggestion
5. WHEN a user saves changes THEN the System SHALL show a confirmation with the configuration changes that will be applied

### Requirement 10

**User Story:** As a system administrator, I want API keys to be stored securely with encryption, so that sensitive credentials are protected.

#### Acceptance Criteria

1. WHEN an API key is stored THEN the System SHALL encrypt it using a secure encryption algorithm
2. WHEN an API key is retrieved for use THEN the System SHALL decrypt it only in memory
3. WHEN API keys are displayed in the UI THEN the System SHALL show only masked versions
4. WHEN the encryption key is not configured THEN the System SHALL prevent the service from starting and display an error
5. WHEN API keys are exported THEN the System SHALL require additional authentication before exposing unmasked keys

### Requirement 11

**User Story:** As a user, I want to see the status of configuration synchronization, so that I know when my changes have been applied to GPT-Load and uni-api.

#### Acceptance Criteria

1. WHEN configuration sync is in progress THEN the System SHALL display a progress indicator with the current operation
2. WHEN sync completes successfully THEN the System SHALL display a success message with a summary of changes
3. WHEN sync fails THEN the System SHALL display detailed error information and allow retry
4. WHEN viewing sync history THEN the System SHALL show timestamps and status of previous sync operations
5. WHEN a sync operation is queued THEN the System SHALL prevent concurrent sync operations and notify the user

### Requirement 12

**User Story:** As a user, I want to test provider connectivity and model availability, so that I can verify my configuration before deploying.

#### Acceptance Criteria

1. WHEN a user tests a provider THEN the System SHALL make a test API call to verify connectivity
2. WHEN testing a specific model THEN the System SHALL send a minimal request to validate the model is accessible
3. WHEN tests complete THEN the System SHALL display results showing success or failure for each tested item
4. WHEN a test fails THEN the System SHALL display the error message returned by the provider
5. WHEN batch testing multiple providers THEN the System SHALL execute tests in parallel and aggregate results

### Requirement 13

**User Story:** As a user, I want clear visibility of GPT-Load connection status and sync target, so that I understand what the "Sync Configuration" button does and where my configuration will be sent.

#### Acceptance Criteria

1. WHEN the UI loads THEN the System SHALL display GPT-Load connection status with the configured GPT-Load URL
2. WHEN GPT-Load is reachable THEN the System SHALL display a connected indicator with the GPT-Load version or status
3. WHEN GPT-Load is unreachable THEN the System SHALL display a disconnected indicator with an error message
4. WHEN a user hovers over the sync button THEN the System SHALL display a tooltip explaining that sync sends normalized models to GPT-Load and generates uni-api configuration
5. WHEN viewing the dashboard THEN the System SHALL display the last sync timestamp and the number of groups currently in GPT-Load

### Requirement 14

**User Story:** As a user, I want to delete multiple models efficiently without repeated confirmation dialogs, so that I can quickly clean up large model lists.

#### Acceptance Criteria

1. WHEN a user clicks delete on a model THEN the System SHALL mark the model visually as pending deletion without showing a confirmation dialog
2. WHEN a model is marked for deletion THEN the System SHALL apply a strikethrough style and gray out the model row
3. WHEN a model is marked for deletion THEN the System SHALL change the delete button to a "Revert" button for that model
4. WHEN a user clicks the revert button on a marked model THEN the System SHALL unmark the model and restore its normal appearance with the delete button
5. WHEN a user saves changes THEN the System SHALL delete all marked models in a single batch operation
6. WHEN no models are marked for deletion THEN the System SHALL not show deletion-related UI elements in the save confirmation

### Requirement 15

**User Story:** As a user, I want to edit multiple model names without triggering a reload after each change, so that I can efficiently normalize many models at once.

#### Acceptance Criteria

1. WHEN a user edits a model name THEN the System SHALL update the local state without making an API call
2. WHEN a user edits multiple model names THEN the System SHALL track all pending changes in memory
3. WHEN a user clicks a save button THEN the System SHALL send all pending model name changes to the API in a batch operation
4. WHEN the batch save completes THEN the System SHALL reload the model list once to reflect the final state
5. WHEN a user navigates away with unsaved changes THEN the System SHALL warn the user about losing pending edits

### Requirement 16

**User Story:** As a user, I want a clear "Save Changes" button and workflow indication, so that I understand when to save my edits and how to proceed to configuration generation.

#### Acceptance Criteria

1. WHEN a user makes any edit to model names or marks models for deletion THEN the System SHALL display a prominent "Save Changes" button
2. WHEN no changes are pending THEN the System SHALL hide or disable the "Save Changes" button
3. WHEN a user clicks "Save Changes" THEN the System SHALL display a confirmation dialog summarizing the changes to be applied
4. WHEN the save confirmation is displayed THEN the System SHALL show the count of models to be renamed and the count of models to be deleted
5. WHEN all changes are saved successfully THEN the System SHALL display a message indicating the next step is to click "Sync Configuration" to generate GPT-Load and uni-api configs

### Requirement 17

**User Story:** As a user, I want the system to intelligently update GPT-Load configuration when I modify providers or models, so that only necessary changes are applied without recreating everything from scratch.

#### Acceptance Criteria

1. WHEN a user adds models to an existing provider THEN the System SHALL update the provider's standard group by adding the new models to model_redirect_rules without recreating the group
2. WHEN a user removes models from an existing provider THEN the System SHALL update the provider's standard group by removing the models from model_redirect_rules and remove the provider from any affected aggregate groups
3. WHEN a user changes a model's normalized name THEN the System SHALL update the affected standard group's model_redirect_rules and adjust aggregate group membership accordingly
4. WHEN a model normalization change causes a provider to leave an aggregate group AND the aggregate has only one remaining sub-group THEN the System SHALL delete the aggregate group and retain the single standard group
5. WHEN a user adds a new provider with models that match existing normalized names THEN the System SHALL create a new standard group for the provider and add it as a sub-group to existing aggregate groups or create new aggregates
6. WHEN a user deletes all models with a specific normalized name from a provider THEN the System SHALL remove that provider from the corresponding aggregate group and delete the aggregate if it becomes empty
7. WHEN configuration sync executes THEN the System SHALL fetch the current GPT-Load configuration, compare it with the desired state, and apply only the minimal set of changes required
8. WHEN sync applies changes THEN the System SHALL execute operations in the correct sequence: delete obsolete aggregates, update standard groups, create new standard groups, delete obsolete standard groups, create new aggregate groups
9. WHEN a standard group's model_redirect_rules are updated THEN the System SHALL use the PUT /api/groups/{id} endpoint to modify the existing group without recreating it
10. WHEN an aggregate group's sub-group membership changes THEN the System SHALL delete and recreate the aggregate group due to GPT-Load API limitations
11. WHEN sync operations fail partially THEN the System SHALL log detailed error information, continue with remaining operations where possible, and report which changes succeeded and which failed
12. WHEN viewing sync history THEN the System SHALL display a detailed summary of changes including groups created, updated, and deleted

### Requirement 18

**User Story:** As a user, I want the "Save Changes" button to be easily accessible when I have a long list of models, so that I don't have to scroll back to the top to save my changes.

#### Acceptance Criteria

1. WHEN the model list exceeds one screen height THEN the System SHALL display the "Save Changes" button at the bottom of the model list for easy access
2. WHEN pending changes exist THEN the System SHALL display the "Save Changes" button at the bottom of the model list
3. WHEN a user clicks the "Save Changes" button THEN the System SHALL execute the save operation

### Requirement 19

**User Story:** As a user, I want to view and download the generated uni-api configuration, so that I can verify the configuration and deploy it to my uni-api instance.

#### Acceptance Criteria

1. WHEN a user accesses the dashboard THEN the System SHALL display a section showing the uni-api configuration status
2. WHEN GPT-Load groups exist THEN the System SHALL display a preview of the generated uni-api YAML configuration
3. WHEN a user clicks a download button THEN the System SHALL download the uni-api YAML file as api.yaml
4. WHEN no GPT-Load groups exist THEN the System SHALL display a message indicating that sync must be run first
5. WHEN the uni-api YAML is displayed THEN the System SHALL show it in a readable format with syntax highlighting or monospace font

### Requirement 20

**User Story:** As a user, I want to see a list of all existing normalized model names when editing models, so that I can maintain consistency and avoid creating duplicate normalized names with slight variations.

#### Acceptance Criteria

1. WHEN a user views the provider detail page THEN the System SHALL display a sidebar or panel showing all existing normalized model names across all providers
2. WHEN a user edits a model name THEN the System SHALL highlight matching normalized names in the reference list to help identify existing standards
3. WHEN a user types in the model name input field THEN the System SHALL provide autocomplete suggestions from the existing normalized model names
4. WHEN the normalized model list is displayed THEN the System SHALL show each unique normalized name with a count of how many providers use it
5. WHEN a user clicks on a normalized name in the reference list THEN the System SHALL filter or highlight models in the current provider that could be normalized to that name

### Requirement 21

**User Story:** As a user, I want the uni-api configuration file to be automatically written to disk during sync operations, so that the uni-api container can access the configuration without manual intervention.

#### Acceptance Criteria

1. WHEN a sync operation completes THEN the System SHALL automatically write the generated uni-api YAML to the configured file path
2. WHEN no export path is specified THEN the System SHALL use the default path /app/uni-api-config/api.yaml
3. WHEN the uni-api configuration directory does not exist THEN the System SHALL create it before writing the file
4. WHEN writing the configuration file THEN the System SHALL ensure proper file permissions for the uni-api container to read
5. WHEN the file write operation fails THEN the System SHALL log the error and include it in the sync result

### Requirement 22

**User Story:** As a user, I want the uni-api configuration to be appended to an existing minimal configuration file, so that the uni-api container can start successfully with required base configuration.

#### Acceptance Criteria

1. WHEN generating uni-api configuration THEN the System SHALL read the existing api.yaml file if it exists
2. WHEN an existing api.yaml contains a dummy provider named "provider_name" THEN the System SHALL remove it before adding generated providers
3. WHEN appending provider configurations THEN the System SHALL preserve existing api_keys and preferences sections from the original file
4. WHEN the existing file does not exist THEN the System SHALL create a new file with generated providers and default api_keys and preferences sections
5. WHEN the existing file is malformed THEN the System SHALL log a warning and create a new file with generated configuration

### Requirement 23

**User Story:** As a user, I want the uni-api provider entries to use the correct base_url format according to uni-api specifications, so that the uni-api gateway can properly route requests to GPT-Load.

#### Acceptance Criteria

1. WHEN generating provider entries for OpenAI-compatible providers THEN the System SHALL use base_url format: http://gptload:3001/proxy/{group_name}/v1/chat/completions
2. WHEN generating provider entries for Anthropic-compatible providers THEN the System SHALL use base_url format: http://gptload:3001/proxy/{group_name}/v1/messages
3. WHEN generating provider entries for Gemini-compatible providers THEN the System SHALL use base_url format: http://gptload:3001/proxy/{group_name}/v1beta
4. WHEN the provider channel type is unknown THEN the System SHALL default to OpenAI format with /v1/chat/completions path
5. WHEN generating provider entries THEN the System SHALL use the GPT-Load URL from environment configuration or settings
