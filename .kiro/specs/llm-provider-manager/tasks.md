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
