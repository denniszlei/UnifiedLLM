# Implementation Plan

- [x] 1. Set up project structure and dependencies
  - Create Python project with FastAPI backend
  - Set up SQLite database with SQLAlchemy ORM
  - Configure project dependencies (FastAPI, SQLAlchemy, httpx, PyYAML, cryptography)
  - Create basic project structure (services, models, api, database folders)
  - _Requirements: 8.1, 8.4_

- [x] 2. Implement encryption service
  - Create EncryptionService class with Fernet encryption
  - Implement encrypt() and decrypt() methods
  - Add encryption key initialization from environment variable
  - Add validation to prevent service startup without encryption key
  - _Requirements: 10.1, 10.2, 10.4_

- [x] 3. Implement database models and schema
  - Create Provider model with encrypted API key field
  - Create Model model with original and normalized name fields
  - Create GPTLoadGroup model for tracking created groups
  - Create SyncRecord model for sync history
  - Implement database initialization and migration logic
  - _Requirements: 1.2, 2.4, 5.1_
- [x] 4. Implement provider service
- [x] 4.1 Create provider CRUD operations
  - Implement add_provider() with credential validation
  - Implement list_providers() with masked API keys
  - Implement delete_provider() with cascade deletion
  - Implement update_provider()
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [x] 4.2 Implement model fetching from providers
  - Create HTTP client for provider API calls
  - Implement fetch_models() to query provider model list endpoint
  - Store fetched models with timestamps
  - Handle empty model lists and errors
  - _Requirements: 2.1, 2.2, 2.4, 2.5_

- [x] 5. Implement model service
- [x] 5.1 Create model normalization logic
  - Implement normalize_model() to update model mappings
  - Implement duplicate detection within provider
  - Prevent duplicate normalized names within same provider
  - Preserve original model names for API calls
  - Implement reset functionality for model names
  - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [x] 5.2 Implement provider splitting algorithm
  - Group models by normalized name
  - Identify duplicates and non-duplicates
  - Generate split provider configurations
  - Create naming scheme for split groups (provider-{index}-{normalized_name})
  - Sanitize group names (convert dots to dashes)
  - _Requirements: 3.3_

- [x] 5.3 Implement model deletion
  - Implement delete_model() to mark models as inactive
  - Implement bulk delete with atomicity
  - Add warning for deleting all models from provider
  - _Requirements: 4.1, 4.3, 4.5_

- [x] 6. Implement GPT-Load client
- [x] 6.1 Create GPT-Load API client

  - Implement HTTP client for GPT-Load REST API
  - Add authentication with GPT-Load auth key
  - Implement error handling and retry logic
  - _Requirements: 5.5_

- [x] 6.2 Implement standard group creation
  - Implement create_standard_group() method
  - Set model_redirect_strict to true
  - Populate model_redirect_rules with normalized mappings
  - Use base URL only (no path suffix)
  - _Requirements: 5.1, 5.2_

- [x] 6.3 Implement API key addition to groups
  - Implement add_keys_to_group() using /api/keys/add-multiple
  - Add provider API keys to each standard group
  - Handle errors during key addition
  - _Requirements: 5.1_

- [x] 6.4 Implement aggregate group creation
  - Implement create_aggregate_group() method
  - Implement add_sub_groups() to link standard groups
  - Set equal weights for sub-groups
  - Implement cleanup of empty aggregate groups
  - _Requirements: 5.3, 5.4, 5.7_

- [x] 6.5 Implement group deletion
  - Implement delete_group() method
  - Handle cascade deletion of related groups
  - Update affected aggregate groups when standard groups are deleted
  - _Requirements: 5.6_

- [x] 7. Implement configuration generator
- [x] 7.1 Create GPT-Load configuration generation
  - Implement logic to generate standard group configs for each provider split
  - Implement logic to identify duplicate models across providers
  - Implement logic to generate aggregate group configs
  - Coordinate group creation sequence (standard → keys → aggregate → sub-groups)
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 7.2 Create uni-api YAML generation
  - Implement YAML generation with PyYAML
  - Create provider entries for aggregate groups
  - Create provider entries for standard groups with non-duplicate models
  - Use GPT-Load proxy endpoints (base URL only, no path suffix)
  - Leave model lists empty for auto-discovery
  - Add default api_keys and preferences sections
  - Validate YAML structure before export
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7_

- [x] 7.3 Implement configuration file export
  - Implement download endpoint for uni-api YAML
  - Write YAML to shared volume for uni-api container
  - _Requirements: 6.6_


- [x] 8. Implement sync service
- [x] 8.1 Create sync orchestration
  - Implement sync_configuration() to coordinate full sync
  - Call configuration generator to create GPT-Load groups
  - Generate uni-api YAML after GPT-Load sync
  - Track sync progress and status
  - _Requirements: 5.1, 6.1, 7.5_

- [x] 8.2 Implement sync status and history
  - Implement get_sync_status() for current operation
  - Implement get_sync_history() for past syncs
  - Store sync records with timestamps and status
  - Prevent concurrent sync operations
  - _Requirements: 11.1, 11.2, 11.4, 11.5_

- [x] 8.3 Implement error handling and retry
  - Log sync errors with details
  - Allow manual retry of failed syncs
  - Display error messages to user
  - _Requirements: 11.3_

- [x] 9. Implement REST API endpoints
- [x] 9.1 Create provider management endpoints
  - POST /api/providers - Add provider
  - GET /api/providers - List providers
  - GET /api/providers/{id} - Get provider details
  - PUT /api/providers/{id} - Update provider
  - DELETE /api/providers/{id} - Delete provider
  - POST /api/providers/{id}/fetch-models - Fetch models
  - POST /api/providers/{id}/test - Test connectivity
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 12.1_

- [x] 9.2 Create model management endpoints
  - GET /api/providers/{id}/models - List models
  - PUT /api/models/{id}/normalize - Normalize model name
  - DELETE /api/models/{id} - Delete model
  - POST /api/models/bulk-delete - Bulk delete
  - POST /api/models/{id}/reset - Reset model name
  - _Requirements: 3.1, 3.5, 4.1, 4.5_

- [x] 9.3 Create configuration endpoints
  - POST /api/config/sync - Trigger sync
  - GET /api/config/sync/status - Get sync status
  - GET /api/config/sync/history - Get sync history
  - GET /api/config/uni-api/download - Download YAML
  - _Requirements: 11.1, 11.2, 11.4, 6.6_

- [x] 9.4 Create system endpoints
  - GET /api/health - Health check
  - GET /api/stats - System statistics
  - _Requirements: 8.5_

- [x] 10. Implement web UI




- [x] 10.1 Create dashboard view
  - Display list of providers with model counts
  - Show masked API keys
  - Add buttons for add, edit, delete providers
  - Display sync status
  - _Requirements: 9.1, 9.5_


- [x] 10.2 Create provider detail view
  - Display provider information
  - Show model list in table format
  - Implement inline editing for model normalization
  - Highlight duplicate models with warnings
  - Show auto-split preview
  - Add fetch models button
  - _Requirements: 9.2, 9.3, 9.4_

- [x] 10.3 Create add/edit provider dialog

  - Form for provider name, base URL, API key, channel type
  - Test connection button
  - Validation and error display
  - _Requirements: 1.1, 1.3, 12.1_

- [x] 10.4 Create sync progress view

  - Display sync progress with steps
  - Show progress bar
  - Display success/error messages
  - _Requirements: 11.1, 11.2, 11.3_

- [ ]* 11. Implement configuration import
- [ ]* 11.1 Create GPT-Load import
  - Fetch existing groups from GPT-Load API
  - Parse group configurations
  - Extract provider and model information
  - _Requirements: 7.1_

- [ ]* 11.2 Create uni-api import
  - Parse existing api.yaml file
  - Extract provider configurations
  - Map back to internal structure
  - _Requirements: 7.2_

- [ ]* 11.3 Implement configuration merge
  - Merge imported configs with new provider inputs
  - Detect and display conflicts
  - Allow user to resolve conflicts
  - _Requirements: 7.3, 7.4, 7.5_

- [x] 12. Create Docker deployment





- [x] 12.1 Create Dockerfile for LLM Provider Manager


  - Use Python base image
  - Install dependencies
  - Set up application
  - Configure environment variables
  - _Requirements: 8.1_

- [x] 12.2 Create docker-compose.yml


  - Define all three services (llm-provider-manager, gptload, uni-api)
  - Configure network connectivity
  - Set up volumes for data persistence
  - Configure port mappings
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 12.3 Create environment configuration


  - Create .env.example file
  - Document required environment variables
  - Add encryption key generation instructions
  - _Requirements: 10.4_

- [ ]* 12.4 Create deployment documentation
  - Write README with setup instructions
  - Document deployment steps
  - Add troubleshooting guide
  - _Requirements: 8.5_

- [ ]* 13. Testing and validation
- [ ]* 13.1 Test provider management
  - Test adding providers with various configurations
  - Test fetching models from real providers
  - Test provider deletion with cascade
  - _Requirements: 1.1, 1.2, 1.5, 2.1_

- [ ]* 13.2 Test model normalization and splitting
  - Test model renaming
  - Test duplicate detection
  - Test provider splitting algorithm with various scenarios
  - Verify group names are properly sanitized
  - _Requirements: 3.1, 3.2, 3.3_

- [ ]* 13.3 Test GPT-Load integration
  - Test standard group creation
  - Test API key addition to groups
  - Test aggregate group creation
  - Test sub-group relationships
  - Verify model_redirect_rules are correct
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 13.4 Test uni-api configuration generation
  - Generate YAML with various provider setups
  - Validate YAML structure
  - Verify base URLs are correct (no path suffix)
  - Verify model lists are empty
  - Test uni-api can read generated config
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 13.5 Test end-to-end flow
  - Add multiple providers
  - Fetch and normalize models
  - Trigger sync
  - Verify GPT-Load groups created correctly
  - Verify uni-api config generated correctly
  - Test actual API calls through uni-api → GPT-Load → providers
  - _Requirements: 7.5_

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement GPT-Load connection status display




- [x] 15.1 Create GPT-Load status endpoint


  - Implement GET /api/gptload/status endpoint
  - Check GPT-Load connectivity and return status
  - Include GPT-Load URL and group count
  - _Requirements: 13.1, 13.2, 13.3, 13.5_

- [x] 15.2 Add connection status to UI header


  - Display GPT-Load URL and connection indicator
  - Show last sync timestamp and group count
  - Add polling to check status every 30 seconds
  - Style connected (green) and disconnected (red) states
  - _Requirements: 13.1, 13.2, 13.3, 13.5_

- [x] 15.3 Add sync button tooltip


  - Implement tooltip on sync button hover
  - Display explanation of what sync does
  - _Requirements: 13.4_
- [x] 16. Implement batch model editing with pending changes







- [x] 16.1 Create pending changes state management



  - Add JavaScript state object to track renames and deletions
  - Implement functions to add/remove pending changes
  - Add hasChanges flag to track if any changes exist
  - _Requirements: 15.1, 15.2_

- [x] 16.2 Update model name edit to use local state



  - Remove immediate API call on model name change
  - Store edit in pending changes state
  - Update UI to show edited state
  - _Requirements: 15.1, 15.2_

- [x] 16.3 Create batch normalize API endpoint



  - Implement PUT /api/models/batch-normalize endpoint
  - Accept list of model ID and normalized name pairs
  - Update all models in a single transaction
  - _Requirements: 15.3_

- [x] 16.4 Create batch delete API endpoint



  - Implement DELETE /api/models/batch-delete endpoint
  - Accept list of model IDs
  - Delete all models in a single transaction
  - _Requirements: 14.5, 15.3_

- [x] 16.5 Implement save changes functionality



  - Call batch normalize API with all pending renames
  - Call batch delete API with all pending deletions
  - Reload model list once after both complete
  - Clear pending changes state
  - _Requirements: 15.3, 15.4_

- [x] 16.6 Add unsaved changes warning



  - Implement beforeunload event handler
  - Show warning when navigating away with pending changes
  - _Requirements: 15.5_
-

- [x] 17. Implement visual delete marking





- [x] 17.1 Update delete button behavior


  - Change delete click to mark model for deletion
  - Add model ID to pending deletions set
  - Update UI to show marked state
  - Remove confirmation dialog
  - _Requirements: 14.1_

- [x] 17.2 Add visual styling for marked models


  - Apply strikethrough and gray styling to marked rows
  - Disable model name input for marked models
  - Add CSS classes for marked-for-deletion state
  - _Requirements: 14.2_

- [x] 17.3 Implement delete/revert button toggle


  - Change "Delete" button to "Revert" when model is marked
  - Add trash icon indicator for marked models
  - Implement revert functionality to unmark model
  - Restore normal appearance when reverted
  - _Requirements: 14.3, 14.4_
-

- [x] 18. Implement save changes button and workflow




- [x] 18.1 Add save changes button


  - Create prominent "Save Changes" button
  - Show button only when pending changes exist
  - Display change count in button text
  - Add subtle pulse animation
  - _Requirements: 16.1, 16.2_

- [x] 18.2 Create save confirmation dialog


  - Show confirmation dialog on save button click
  - Display summary of changes (rename count, delete count)
  - Show "Cancel" and "Confirm" buttons
  - _Requirements: 16.3, 16.4_

- [x] 18.3 Add success message with next steps


  - Display success message after save completes
  - Include guidance to click "Sync Configuration"
  - Explain that sync generates GPT-Load and uni-api configs
  - _Requirements: 16.5_

- [x] 18.4 Update save confirmation to exclude empty sections

  - Only show rename count if renames exist
  - Only show delete count if deletions exist
  - _Requirements: 14.6_

- [ ] 19. Final checkpoint - Test UX improvements
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19.1 Move Save Changes button to bottom of model list





  - Relocate button from top to bottom of models table
  - Ensure button remains visible and accessible
  - Add CSS for sticky footer positioning if needed
  - _Requirements: 18.1_

- [x] 20. Implement incremental sync for GPT-Load configuration





  - Implement smart diff-based updates instead of full recreation
  - Handle all modification scenarios
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10, 17.11, 17.12_

- [x] 20.1 Implement configuration state comparison


  - Create get_existing_config() to fetch current GPT-Load groups and sub-groups
  - Parse existing group configurations (model_redirect_rules, sub-groups)
  - Build desired configuration from local database
  - _Requirements: 17.7_

- [x] 20.2 Implement diff computation logic


  - Enhance diff_configs() to identify groups to CREATE, UPDATE, DELETE
  - Detect changes in model_redirect_rules for standard groups
  - Detect changes in aggregate sub-group membership
  - Identify orphaned aggregates (only 1 sub-group remaining)
  - _Requirements: 17.7_

- [x] 20.3 Implement standard group update operations


  - Add update_group() method using PUT /api/groups/{id}
  - Handle adding models to model_redirect_rules (Scenario A)
  - Handle removing models from model_redirect_rules (Scenario B)
  - Handle changing normalized names in model_redirect_rules (Scenario C)
  - _Requirements: 17.1, 17.2, 17.3, 17.9_

- [x] 20.4 Implement aggregate group management


  - Implement delete_aggregate_group() using DELETE /api/groups/{id}
  - Implement remove_sub_group() using DELETE /api/groups/{id}/sub-groups/{sub_id}
  - Handle removing provider from aggregate when model deleted
  - Handle removing provider from aggregate when normalization changes
  - Handle cleanup: Delete aggregate if only 1 sub-group remains
  - _Requirements: 17.2, 17.3, 17.4, 17.6, 17.10_

- [x] 20.5 Implement new provider with duplicate handling


  - Handle creating new standard group for new provider (Scenario D)
  - Add API keys to new group using POST /api/keys/add-async
  - Create or update aggregate group for duplicate models
  - Add new provider as sub-group to existing aggregate
  - _Requirements: 17.5_

- [x] 20.6 Implement sync operation sequencing


  - Update sync_configuration() to use incremental approach
  - Step 1: Delete aggregates that need recreation
  - Step 2: Update existing standard groups (model_redirect_rules changes)
  - Step 3: Create new standard groups
  - Step 4: Delete obsolete standard groups
  - Step 5: Create/recreate aggregate groups with correct sub-groups
  - Handle partial failures with detailed error reporting
  - _Requirements: 17.8, 17.11_

- [x] 20.7 Add database tracking for sync state


  - Add last_sync_timestamp to gptload_groups table
  - Add config_hash column to detect changes
  - Update sync_records with detailed change summary
  - Track which groups were created/updated/deleted per sync
  - _Requirements: 17.12_

- [ ]* 20.8 Write manual test scenarios documentation
  - Document Scenario A: Add models to existing provider
  - Document Scenario B: Remove models and aggregate cleanup
  - Document Scenario C: Normalization changes affecting aggregates
  - Document Scenario D: New provider with duplicate models
  - Document expected outcomes for Docker testing
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 21. Final checkpoint - Manual Docker testing
  - Test all scenarios on remote Docker deployment
  - Verify GPT-Load groups are updated correctly
  - Ask user if issues arise

- [x] 22. Implement uni-api configuration display section





  - Add uni-api config section to dashboard view
  - Display generated YAML with download button
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

- [x] 22.1 Create uni-api config section in dashboard


  - Add new section below providers list in dashboard view
  - Create collapsible/expandable section for uni-api config
  - Add section header with title "uni-api Configuration"
  - _Requirements: 19.1_

- [x] 22.2 Implement YAML preview display


  - Fetch uni-api YAML from GET /api/config/uni-api/yaml endpoint
  - Display YAML content in a code block with monospace font
  - Add syntax highlighting or preserve formatting
  - Show loading state while fetching
  - Handle empty state when no groups exist
  - _Requirements: 19.2, 19.4, 19.5_

- [x] 22.3 Add download button for uni-api config

  - Create "Download api.yaml" button in uni-api section
  - Implement download functionality using /api/config/uni-api/download endpoint
  - Trigger browser download with correct filename (api.yaml)
  - Disable button when no config is available
  - _Requirements: 19.3_

- [x] 22.4 Add auto-refresh on sync completion


  - Refresh uni-api config display after successful sync
  - Update config section when returning to dashboard
  - Show updated timestamp or indicator
  - _Requirements: 19.2_

- [x] 23. Implement normalized model name reference display




  - Add sidebar panel showing existing normalized model names
  - Implement autocomplete for model name inputs
  - Add click-to-filter functionality
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

- [x] 23.1 Create API endpoint for normalized names


  - Implement GET /api/models/normalized-names endpoint
  - Query database for unique normalized names with counts
  - Return list with name, provider_count, and model_count
  - Order by provider_count DESC, then name ASC
  - _Requirements: 20.1, 20.4_

- [x] 23.2 Add normalized names sidebar to provider detail view


  - Create sidebar panel component in provider detail page
  - Display list of normalized model names with provider counts
  - Add search/filter input for the list
  - Style with fixed position or scrollable container
  - Load data from /api/models/normalized-names on page load
  - _Requirements: 20.1, 20.4_

- [x] 23.3 Implement autocomplete for model name inputs


  - Add autocomplete functionality to normalized name input fields
  - Filter suggestions based on user input (prefix matching)
  - Display top 5 matching suggestions with provider counts
  - Allow keyboard navigation (arrow keys, enter to select)
  - Update input value when suggestion is selected
  - _Requirements: 20.3_

- [x] 23.4 Add highlighting for matching names


  - Highlight normalized names in sidebar that match current input
  - Update highlights in real-time as user types
  - Use distinct visual style (background color, border)
  - _Requirements: 20.2_

- [x] 23.5 Implement click-to-filter functionality

  - Add click handler to normalized name items in sidebar
  - When clicked, highlight models in current provider that could use that name
  - Use similarity matching to suggest which models should be normalized
  - Add visual indicator (border, background) to suggested model rows
  - Clear highlights when another name is clicked or search is cleared
  - _Requirements: 20.5_

- [ ] 24. Final checkpoint - Test normalized name reference feature
  - Ensure all tests pass, ask the user if questions arise.

- [x] 25. Update uni-api YAML generation to use correct base_url format




  - Implement channel-type-aware base_url generation
  - Support OpenAI format: /v1/chat/completions
  - Support Anthropic format: /v1/messages
  - Support Gemini format: /v1beta
  - Default to OpenAI format for unknown channel types
  - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

- [x] 25.1 Update build_base_url function


  - Query provider channel_type from database
  - Build path suffix based on channel type
  - Construct full base_url with GPT-Load proxy path
  - _Requirements: 23.1, 23.2, 23.3, 23.4_

- [x] 25.2 Update generate_uniapi_yaml to use new base_url logic


  - Call build_base_url for each provider entry
  - Ensure aggregate groups use appropriate channel type
  - Test with multiple channel types
  - _Requirements: 23.1, 23.2, 23.3_

- [x] 26. Implement intelligent YAML file merging





  - Read existing api.yaml file if it exists
  - Remove dummy provider entries
  - Preserve existing api_keys and preferences
  - Merge generated providers with existing configuration
  - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5_

- [x] 26.1 Implement existing file reading and parsing


  - Check if /app/uni-api-config/api.yaml exists
  - Parse existing YAML using PyYAML
  - Handle malformed YAML with error logging
  - _Requirements: 22.1, 22.5_

- [x] 26.2 Implement dummy provider removal


  - Filter out providers with name "provider_name"
  - Preserve all other existing providers
  - Log removal action
  - _Requirements: 22.2_

- [x] 26.3 Implement configuration section preservation


  - Extract api_keys section from existing config
  - Extract preferences section from existing config
  - Use extracted sections in merged configuration
  - Fall back to defaults if sections don't exist
  - _Requirements: 22.3, 22.4_



- [x] 26.4 Implement configuration merging logic

  - Combine generated providers with preserved sections
  - Ensure proper YAML structure
  - Validate merged configuration
  - _Requirements: 22.3, 22.4_

- [x] 27. Ensure automatic YAML export on sync





  - Verify sync service always exports YAML to disk
  - Use default path if not specified
  - Create directory if it doesn't exist
  - Handle file write errors gracefully
  - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

- [x] 27.1 Verify default export path is set


  - Check that sync_configuration_incremental sets default path
  - Check that sync_configuration sets default path
  - Ensure path is /app/uni-api-config/api.yaml
  - _Requirements: 21.2_

- [x] 27.2 Implement directory creation


  - Add os.makedirs() call in export_uniapi_yaml_to_file
  - Use exist_ok=True to avoid errors if directory exists
  - Log directory creation action
  - _Requirements: 21.3_

- [x] 27.3 Implement file permission handling


  - Set appropriate file permissions after write
  - Ensure uni-api container can read the file
  - Log permission setting action
  - _Requirements: 21.4_

- [x] 27.4 Add error handling for file operations


  - Catch IOError and OSError exceptions
  - Log detailed error messages
  - Include error in sync result
  - Don't fail entire sync if file write fails
  - _Requirements: 21.5_

- [ ] 28. Test uni-api YAML generation with real scenarios
  - Test with OpenAI providers
  - Test with Anthropic providers
  - Test with Gemini providers
  - Test with mixed provider types
  - Test appending to existing minimal config
  - Test dummy provider removal
  - Verify file is written to disk
  - Verify uni-api container can read the file
  - _Requirements: 21.1, 22.1, 22.2, 23.1, 23.2, 23.3_

- [ ] 29. Final checkpoint - Verify uni-api integration
  - Ensure all tests pass, ask the user if questions arise.
