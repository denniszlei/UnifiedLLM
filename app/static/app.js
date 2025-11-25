// API Base URL
const API_BASE = '/api';

// State
let currentProviderId = null;
let currentProvider = null;
let providers = [];
let models = [];
let gptloadStatusInterval = null;

// Pending changes state
let pendingChanges = {
    renames: new Map(), // Map<modelId, normalizedName>
    deletions: new Set(), // Set<modelId>
    hasChanges: function() {
        return this.renames.size > 0 || this.deletions.size > 0;
    },
    clear: function() {
        this.renames.clear();
        this.deletions.clear();
    },
    addRename: function(modelId, normalizedName) {
        this.renames.set(modelId, normalizedName);
    },
    removeRename: function(modelId) {
        this.renames.delete(modelId);
    },
    addDeletion: function(modelId) {
        this.deletions.add(modelId);
    },
    removeDeletion: function(modelId) {
        this.deletions.delete(modelId);
    },
    isMarkedForDeletion: function(modelId) {
        return this.deletions.has(modelId);
    },
    getPendingRename: function(modelId) {
        return this.renames.get(modelId);
    }
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboard();
    startGPTLoadStatusPolling();
});

// Event Listeners
function initializeEventListeners() {
    // Dashboard
    document.getElementById('addProviderBtn').addEventListener('click', () => openProviderModal());
    
    // GPT-Load Section
    document.getElementById('showGroupsBtn').addEventListener('click', () => toggleGptloadGroups());
    document.getElementById('syncGptloadBtn').addEventListener('click', () => syncToGptload());
    
    // uni-api Section
    document.getElementById('toggleYamlBtn').addEventListener('click', () => toggleYamlPreview());
    document.getElementById('generateConfigBtn').addEventListener('click', () => generateUniapiConfig());
    document.getElementById('downloadYamlBtn').addEventListener('click', () => downloadUniapiYaml());
    
    // Provider Detail
    document.getElementById('backToListBtn').addEventListener('click', () => showDashboard());
    document.getElementById('fetchModelsBtn').addEventListener('click', () => fetchModels());
    document.getElementById('saveChangesBtn').addEventListener('click', () => showSaveConfirmation());
    
    // Modal
    const modal = document.getElementById('providerModal');
    const closeBtn = modal.querySelector('.close');
    const cancelBtn = modal.querySelector('.cancel-btn');
    
    closeBtn.addEventListener('click', () => closeProviderModal());
    cancelBtn.addEventListener('click', () => closeProviderModal());
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeProviderModal();
        }
    });
    
    // Provider Form
    document.getElementById('providerForm').addEventListener('submit', handleProviderSubmit);
    document.getElementById('testConnectionBtn').addEventListener('click', testConnection);
}

// Dashboard Functions
async function loadDashboard() {
    showView('dashboardView');
    await loadProviders();
    await loadGptloadStatus();
    await loadUniapiConfig();
}

async function loadProviders() {
    const providersList = document.getElementById('providersList');
    providersList.innerHTML = '<div class="loading">Loading providers...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/providers`);
        if (!response.ok) throw new Error('Failed to load providers');
        
        providers = await response.json();
        renderProviders(providers);
    } catch (error) {
        providersList.innerHTML = `<div class="text-danger">Error loading providers: ${error.message}</div>`;
    }
}

function renderProviders(providersList) {
    const container = document.getElementById('providersList');
    
    if (providersList.length === 0) {
        container.innerHTML = '<div class="text-muted">No providers added yet. Click "Add Provider" to get started.</div>';
        return;
    }
    
    container.innerHTML = providersList.map(provider => `
        <div class="provider-card" onclick="showProviderDetail(${provider.id})">
            <div class="provider-card-header">
                <div>
                    <div class="provider-card-title">${escapeHtml(provider.name)}</div>
                    <div class="provider-card-info">${escapeHtml(provider.base_url)}</div>
                    <div class="provider-card-info">API Key: ${escapeHtml(provider.api_key_masked)}</div>
                </div>
                <div class="provider-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-secondary" onclick="editProvider(${provider.id})">Edit</button>
                    <button class="btn btn-danger" onclick="deleteProvider(${provider.id})">Delete</button>
                </div>
            </div>
            <div class="provider-card-meta">
                <span>Models: ${provider.model_count || 0}</span>
                <span>Last Fetched: ${provider.last_fetched_at ? formatDate(provider.last_fetched_at) : 'Never'}</span>
            </div>
        </div>
    `).join('');
}

async function loadSyncStatus() {
    try {
        const response = await fetch(`${API_BASE}/config/sync/status`);
        if (!response.ok) return;
        
        const status = await response.json();
        displaySyncStatus(status);
    } catch (error) {
        console.error('Failed to load sync status:', error);
    }
}

function displaySyncStatus(status) {
    const statusDiv = document.getElementById('syncStatus');
    
    if (!status || !status.last_sync) {
        statusDiv.innerHTML = '';
        return;
    }
    
    const lastSync = status.last_sync;
    let statusClass = 'info';
    let statusText = '';
    
    if (lastSync.status === 'success') {
        statusClass = 'success';
        statusText = `✓ Last sync successful (${formatDate(lastSync.completed_at)})`;
        if (lastSync.changes_summary) {
            statusText += ` - ${lastSync.changes_summary}`;
        }
    } else if (lastSync.status === 'failed') {
        statusClass = 'error';
        statusText = `✗ Last sync failed (${formatDate(lastSync.started_at)})`;
        if (lastSync.error_message) {
            statusText += ` - ${lastSync.error_message}`;
        }
    } else if (lastSync.status === 'in_progress') {
        statusClass = 'info';
        statusText = '⏳ Sync in progress...';
    }
    
    statusDiv.className = `sync-status ${statusClass}`;
    statusDiv.innerHTML = statusText;
}

// State for normalized names
let normalizedNames = [];
let selectedNormalizedName = null;

// Provider Detail Functions
async function showProviderDetail(providerId) {
    currentProviderId = providerId;
    showView('providerDetailView');
    
    await loadProviderDetail(providerId);
    await loadNormalizedNames();
    await loadModels(providerId);
}

async function loadProviderDetail(providerId) {
    try {
        const response = await fetch(`${API_BASE}/providers/${providerId}`);
        if (!response.ok) throw new Error('Failed to load provider');
        
        currentProvider = await response.json();
        renderProviderDetail(currentProvider);
    } catch (error) {
        document.getElementById('providerInfo').innerHTML = 
            `<div class="text-danger">Error loading provider: ${error.message}</div>`;
    }
}

function renderProviderDetail(provider) {
    document.getElementById('providerDetailTitle').textContent = provider.name;
    
    document.getElementById('providerInfo').innerHTML = `
        <div class="provider-info-row">
            <div class="provider-info-label">Base URL:</div>
            <div class="provider-info-value">${escapeHtml(provider.base_url)}</div>
        </div>
        <div class="provider-info-row">
            <div class="provider-info-label">API Key:</div>
            <div class="provider-info-value">${escapeHtml(provider.api_key_masked)}</div>
        </div>
        <div class="provider-info-row">
            <div class="provider-info-label">Channel Type:</div>
            <div class="provider-info-value">${escapeHtml(provider.channel_type)}</div>
        </div>
        <div class="provider-info-row">
            <div class="provider-info-label">Last Fetched:</div>
            <div class="provider-info-value">${provider.last_fetched_at ? formatDate(provider.last_fetched_at) : 'Never'}</div>
        </div>
    `;
}

async function loadModels(providerId) {
    const modelsList = document.getElementById('modelsList');
    modelsList.innerHTML = '<div class="loading">Loading models...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/providers/${providerId}/models`);
        if (!response.ok) throw new Error('Failed to load models');
        
        models = await response.json();
        renderModels(models);
    } catch (error) {
        modelsList.innerHTML = `<div class="text-danger">Error loading models: ${error.message}</div>`;
    }
}

function renderModels(modelsList) {
    const container = document.getElementById('modelsList');
    
    if (modelsList.length === 0) {
        container.innerHTML = '<div class="text-muted">No models found. Click "Fetch Models" to load from provider.</div>';
        return;
    }
    
    // Detect duplicates and group models
    const normalizedGroups = {};
    modelsList.forEach(model => {
        const name = model.normalized_name || model.original_name;
        if (!normalizedGroups[name]) {
            normalizedGroups[name] = [];
        }
        normalizedGroups[name].push(model);
    });
    
    const duplicates = {};
    const nonDuplicates = [];
    
    Object.entries(normalizedGroups).forEach(([name, models]) => {
        if (models.length > 1) {
            duplicates[name] = models;
        } else {
            nonDuplicates.push(models[0]);
        }
    });
    
    const hasDuplicates = Object.keys(duplicates).length > 0;
    
    let html = '<table class="models-table"><thead><tr>';
    html += '<th>Original Name</th>';
    html += '<th>Normalized Name</th>';
    html += '<th>Actions</th>';
    html += '</tr></thead><tbody>';
    
    modelsList.forEach(model => {
        const normalizedName = model.normalized_name || model.original_name;
        const isDuplicate = normalizedGroups[normalizedName].length > 1;
        const isEdited = pendingChanges.renames.has(model.id);
        const editedValue = isEdited ? pendingChanges.getPendingRename(model.id) : normalizedName;
        const isMarkedForDeletion = pendingChanges.isMarkedForDeletion(model.id);
        
        html += `<tr${isMarkedForDeletion ? ' class="marked-for-deletion"' : ''}>`;
        html += `<td>${escapeHtml(model.original_name)}</td>`;
        html += `<td>
            <div class="autocomplete-container">
                <input type="text" 
                       class="model-name-input ${isEdited ? 'edited' : ''}" 
                       value="${escapeHtml(editedValue)}"
                       data-model-id="${model.id}"
                       id="model-input-${model.id}"
                       onchange="updateModelName(${model.id}, this.value)"
                       ${isMarkedForDeletion ? 'disabled' : ''}>
                <div class="autocomplete-dropdown" id="autocomplete-${model.id}"></div>
            </div>
            ${isDuplicate ? '<div class="duplicate-warning">⚠️ Duplicate</div>' : ''}
        </td>`;
        html += `<td class="model-actions">
            <button class="btn btn-secondary" onclick="resetModelName(${model.id})">Reset</button>
            ${isMarkedForDeletion 
                ? `<button class="btn btn-secondary" onclick="revertDeleteModel(${model.id})">🗑️ Revert</button>`
                : `<button class="btn btn-danger" onclick="deleteModel(${model.id})">Delete</button>`
            }
        </td>`;
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    
    // Show auto-split preview
    if (hasDuplicates || nonDuplicates.length > 0) {
        html += renderAutoSplitPreview(duplicates, nonDuplicates);
    }
    
    container.innerHTML = html;
    
    // Set up autocomplete for each input
    modelsList.forEach(model => {
        if (!pendingChanges.isMarkedForDeletion(model.id)) {
            setupAutocomplete(model.id);
        }
    });
    
    // Update save button visibility
    updateSaveButtonVisibility();
}

function renderAutoSplitPreview(duplicates, nonDuplicates) {
    const providerName = currentProvider ? sanitizeGroupName(currentProvider.name) : 'provider';
    let html = '<div class="auto-split-preview">';
    html += '<h4>Auto-Split Preview</h4>';
    html += '<p class="preview-description">Based on your model normalization, the following GPT-Load groups will be created:</p>';
    
    html += '<div class="split-groups">';
    
    // Standard groups for duplicates
    if (Object.keys(duplicates).length > 0) {
        html += '<div class="split-section">';
        html += '<h5>Standard Groups (Duplicate Models)</h5>';
        
        Object.entries(duplicates).forEach(([normalizedName, models], index) => {
            models.forEach((model, modelIndex) => {
                const groupName = `${providerName}-${index}-${sanitizeGroupName(normalizedName)}`;
                html += '<div class="split-group-item">';
                html += `<div class="group-name">📦 ${escapeHtml(groupName)}</div>`;
                html += `<div class="group-details">`;
                html += `<span class="group-model">Model: ${escapeHtml(normalizedName)}</span>`;
                html += `<span class="group-redirect">Redirects: ${escapeHtml(normalizedName)} → ${escapeHtml(model.original_name)}</span>`;
                html += `</div>`;
                html += '</div>';
            });
        });
        
        html += '</div>';
        
        // Aggregate groups
        html += '<div class="split-section">';
        html += '<h5>Aggregate Groups (Load Balanced)</h5>';
        
        Object.entries(duplicates).forEach(([normalizedName, models]) => {
            const aggregateName = `${sanitizeGroupName(normalizedName)}-aggregate`;
            html += '<div class="split-group-item aggregate">';
            html += `<div class="group-name">🔀 ${escapeHtml(aggregateName)}</div>`;
            html += `<div class="group-details">`;
            html += `<span class="group-model">Combines ${models.length} groups for load balancing</span>`;
            html += `</div>`;
            html += '</div>';
        });
        
        html += '</div>';
    }
    
    // Standard group for non-duplicates
    if (nonDuplicates.length > 0) {
        html += '<div class="split-section">';
        html += '<h5>Standard Group (Non-Duplicate Models)</h5>';
        
        const groupName = `${providerName}-no-aggregate_models`;
        html += '<div class="split-group-item">';
        html += `<div class="group-name">📦 ${escapeHtml(groupName)}</div>`;
        html += `<div class="group-details">`;
        html += `<span class="group-model">${nonDuplicates.length} model(s): ${nonDuplicates.slice(0, 3).map(m => escapeHtml(m.normalized_name || m.original_name)).join(', ')}${nonDuplicates.length > 3 ? '...' : ''}</span>`;
        html += `</div>`;
        html += '</div>';
        
        html += '</div>';
    }
    
    html += '</div>'; // split-groups
    
    // Summary
    const totalStandardGroups = Object.keys(duplicates).reduce((sum, key) => sum + duplicates[key].length, 0) + (nonDuplicates.length > 0 ? 1 : 0);
    const totalAggregateGroups = Object.keys(duplicates).length;
    
    html += '<div class="split-summary">';
    html += `<strong>Summary:</strong> ${totalStandardGroups} standard group(s)`;
    if (totalAggregateGroups > 0) {
        html += ` + ${totalAggregateGroups} aggregate group(s)`;
    }
    html += ' will be created in GPT-Load';
    html += '</div>';
    
    html += '</div>'; // auto-split-preview
    
    return html;
}

function sanitizeGroupName(name) {
    // Convert dots to dashes and remove special characters
    return name.replace(/\./g, '-').replace(/[^a-zA-Z0-9_-]/g, '');
}

async function fetchModels() {
    if (!currentProviderId) return;
    
    const btn = document.getElementById('fetchModelsBtn');
    btn.disabled = true;
    btn.textContent = 'Fetching...';
    
    try {
        const response = await fetch(`${API_BASE}/providers/${currentProviderId}/fetch-models`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to fetch models');
        }
        
        await loadModels(currentProviderId);
        showMessage('success', 'Models fetched successfully');
    } catch (error) {
        showMessage('error', `Failed to fetch models: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Fetch Models';
    }
}

function updateModelName(modelId, newName) {
    // Store edit in pending changes state instead of making immediate API call
    const model = models.find(m => m.id === modelId);
    if (!model) return;
    
    const originalName = model.normalized_name || model.original_name;
    
    // If the new name is the same as the original, remove from pending changes
    if (newName === originalName) {
        pendingChanges.removeRename(modelId);
    } else {
        pendingChanges.addRename(modelId, newName);
    }
    
    // Update UI to show edited state
    updateSaveButtonVisibility();
}

async function resetModelName(modelId) {
    try {
        const response = await fetch(`${API_BASE}/models/${modelId}/reset`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to reset model name');
        }
        
        await loadModels(currentProviderId);
    } catch (error) {
        showMessage('error', `Failed to reset model: ${error.message}`);
    }
}

function deleteModel(modelId) {
    // Mark model for deletion instead of immediate API call
    pendingChanges.addDeletion(modelId);
    
    // Re-render models to show marked state
    renderModels(models);
}

function revertDeleteModel(modelId) {
    // Unmark model for deletion
    pendingChanges.removeDeletion(modelId);
    
    // Re-render models to restore normal appearance
    renderModels(models);
}

// Provider Modal Functions
function openProviderModal(provider = null) {
    const modal = document.getElementById('providerModal');
    const form = document.getElementById('providerForm');
    const title = document.getElementById('modalTitle');
    const apiKeyInput = document.getElementById('providerApiKey');
    
    form.reset();
    document.getElementById('formMessage').className = 'form-message';
    document.getElementById('formMessage').textContent = '';
    
    if (provider) {
        title.textContent = 'Edit Provider';
        document.getElementById('providerName').value = provider.name;
        document.getElementById('providerBaseUrl').value = provider.base_url;
        document.getElementById('providerChannelType').value = provider.channel_type;
        
        // For editing, make API key optional (show placeholder)
        apiKeyInput.placeholder = 'Leave empty to keep current API key';
        apiKeyInput.required = false;
        
        form.dataset.providerId = provider.id;
    } else {
        title.textContent = 'Add Provider';
        
        // For adding, API key is required
        apiKeyInput.placeholder = '';
        apiKeyInput.required = true;
        
        delete form.dataset.providerId;
    }
    
    modal.classList.add('active');
}

function closeProviderModal() {
    document.getElementById('providerModal').classList.remove('active');
}

async function handleProviderSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    const providerId = form.dataset.providerId;
    
    const messageDiv = document.getElementById('formMessage');
    messageDiv.className = 'form-message';
    messageDiv.textContent = '';
    
    // Validate required fields
    if (!data.name || !data.base_url) {
        showFormMessage('error', 'Provider name and base URL are required');
        return;
    }
    
    // For new providers, API key is required
    if (!providerId && !data.api_key) {
        showFormMessage('error', 'API key is required for new providers');
        return;
    }
    
    // For editing, if API key is empty, don't send it (keep existing)
    if (providerId && !data.api_key) {
        delete data.api_key;
    }
    
    // Disable submit button during request
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    
    try {
        const url = providerId ? `${API_BASE}/providers/${providerId}` : `${API_BASE}/providers`;
        const method = providerId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save provider');
        }
        
        closeProviderModal();
        await loadProviders();
        showMessage('success', `Provider ${providerId ? 'updated' : 'added'} successfully`);
    } catch (error) {
        showFormMessage('error', error.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

async function testConnection() {
    const baseUrl = document.getElementById('providerBaseUrl').value;
    const apiKey = document.getElementById('providerApiKey').value;
    const channelType = document.getElementById('providerChannelType').value;
    
    if (!baseUrl || !apiKey) {
        showFormMessage('error', 'Please enter base URL and API key');
        return;
    }
    
    const btn = document.getElementById('testConnectionBtn');
    btn.disabled = true;
    btn.textContent = 'Testing...';
    
    try {
        const response = await fetch(`${API_BASE}/providers/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                base_url: baseUrl, 
                api_key: apiKey,
                channel_type: channelType
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Connection test failed');
        }
        
        const result = await response.json();
        if (result.success) {
            showFormMessage('success', result.message || 'Connection successful!');
        } else {
            showFormMessage('error', result.message || 'Connection test failed');
        }
    } catch (error) {
        showFormMessage('error', `Connection failed: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test Connection';
    }
}

async function editProvider(providerId) {
    try {
        const response = await fetch(`${API_BASE}/providers/${providerId}`);
        if (!response.ok) throw new Error('Failed to load provider');
        
        const provider = await response.json();
        openProviderModal(provider);
    } catch (error) {
        showMessage('error', `Failed to load provider: ${error.message}`);
    }
}

async function deleteProvider(providerId) {
    if (!confirm('Are you sure you want to delete this provider? All associated models will be removed.')) return;
    
    try {
        const response = await fetch(`${API_BASE}/providers/${providerId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete provider');
        }
        
        await loadProviders();
        showMessage('success', 'Provider deleted successfully');
    } catch (error) {
        showMessage('error', `Failed to delete provider: ${error.message}`);
    }
}

// Sync Functions
async function syncConfiguration() {
    showView('syncProgressView');
    
    const progressBar = document.getElementById('progressBarFill');
    const stepsDiv = document.getElementById('syncSteps');
    const messageDiv = document.getElementById('syncMessage');
    
    progressBar.style.width = '0%';
    stepsDiv.innerHTML = '';
    messageDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE}/config/sync`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Sync failed');
        }
        
        const result = await response.json();
        
        // Simulate progress
        progressBar.style.width = '100%';
        
        messageDiv.className = 'sync-message success';
        messageDiv.textContent = '✓ Configuration synced successfully!';
        
        if (result.summary) {
            messageDiv.textContent += ` ${result.summary}`;
        }
        
        setTimeout(async () => {
            await showDashboard();
            // Refresh uni-api config after successful sync
            await loadUniapiConfig();
        }, 2000);
    } catch (error) {
        progressBar.style.width = '100%';
        messageDiv.className = 'sync-message error';
        messageDiv.textContent = `✗ Sync failed: ${error.message}`;
        
        setTimeout(() => {
            showDashboard();
        }, 3000);
    }
}

// View Management
function showView(viewId) {
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(viewId).classList.add('active');
}

async function showDashboard() {
    await loadDashboard();
}

// Utility Functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showMessage(type, message) {
    const statusDiv = document.getElementById('syncStatus');
    statusDiv.className = `sync-status ${type}`;
    statusDiv.innerHTML = message;
    
    setTimeout(() => {
        statusDiv.className = 'sync-status';
        statusDiv.innerHTML = '';
    }, 5000);
}

function showFormMessage(type, message) {
    const messageDiv = document.getElementById('formMessage');
    messageDiv.className = `form-message ${type}`;
    messageDiv.textContent = message;
}

// GPT-Load Status Functions
async function loadGPTLoadStatus() {
    try {
        const response = await fetch(`${API_BASE}/gptload/status`);
        if (!response.ok) {
            throw new Error('Failed to load GPT-Load status');
        }
        
        const status = await response.json();
        displayGPTLoadStatus(status);
    } catch (error) {
        console.error('Failed to load GPT-Load status:', error);
        displayGPTLoadStatus({
            connected: false,
            url: 'Unknown',
            group_count: 0,
            error_message: 'Failed to check status'
        });
    }
}

function displayGPTLoadStatus(status) {
    const statusDiv = document.getElementById('gptloadStatus');
    const urlDiv = statusDiv.querySelector('.status-url');
    const infoDiv = statusDiv.querySelector('.status-info');
    
    // Update connection state class
    statusDiv.className = 'gptload-status';
    if (status.connected) {
        statusDiv.classList.add('connected');
    } else {
        statusDiv.classList.add('disconnected');
    }
    
    // Update URL display
    if (status.connected) {
        urlDiv.textContent = `GPT-Load: ${status.url}`;
    } else {
        urlDiv.textContent = `GPT-Load: Disconnected`;
    }
    
    // Update info display
    if (status.connected) {
        // Get last sync info
        fetch(`${API_BASE}/config/sync/status`)
            .then(response => response.json())
            .then(syncStatus => {
                let infoText = `${status.group_count} group(s)`;
                
                if (syncStatus.last_sync && syncStatus.last_sync.completed_at) {
                    const lastSyncDate = new Date(syncStatus.last_sync.completed_at);
                    const now = new Date();
                    const diffMinutes = Math.floor((now - lastSyncDate) / 60000);
                    
                    if (diffMinutes < 1) {
                        infoText += ' • Last sync: just now';
                    } else if (diffMinutes < 60) {
                        infoText += ` • Last sync: ${diffMinutes}m ago`;
                    } else if (diffMinutes < 1440) {
                        const hours = Math.floor(diffMinutes / 60);
                        infoText += ` • Last sync: ${hours}h ago`;
                    } else {
                        const days = Math.floor(diffMinutes / 1440);
                        infoText += ` • Last sync: ${days}d ago`;
                    }
                }
                
                infoDiv.textContent = infoText;
            })
            .catch(() => {
                infoDiv.textContent = `${status.group_count} group(s)`;
            });
    } else {
        infoDiv.textContent = status.error_message || 'Unable to connect';
    }
}

function startGPTLoadStatusPolling() {
    // Load immediately
    loadGPTLoadStatus();
    
    // Poll every 30 seconds
    if (gptloadStatusInterval) {
        clearInterval(gptloadStatusInterval);
    }
    
    gptloadStatusInterval = setInterval(() => {
        loadGPTLoadStatus();
    }, 30000); // 30 seconds
}

function stopGPTLoadStatusPolling() {
    if (gptloadStatusInterval) {
        clearInterval(gptloadStatusInterval);
        gptloadStatusInterval = null;
    }
}

function showSaveConfirmation() {
    if (!pendingChanges.hasChanges()) {
        showMessage('info', 'No changes to save');
        return;
    }
    
    const modal = document.getElementById('saveConfirmationModal');
    const summaryDiv = document.getElementById('saveConfirmationSummary');
    
    let summaryHtml = '';
    
    // Only show rename count if renames exist
    if (pendingChanges.renames.size > 0) {
        summaryHtml += `
            <div class="save-summary-item">
                <span class="save-summary-icon">✏️</span>
                <span class="save-summary-text">
                    <strong>${pendingChanges.renames.size}</strong> model name(s) will be updated
                </span>
            </div>
        `;
    }
    
    // Only show delete count if deletions exist
    if (pendingChanges.deletions.size > 0) {
        summaryHtml += `
            <div class="save-summary-item">
                <span class="save-summary-icon">🗑️</span>
                <span class="save-summary-text">
                    <strong>${pendingChanges.deletions.size}</strong> model(s) will be deleted
                </span>
            </div>
        `;
    }
    
    summaryDiv.innerHTML = summaryHtml;
    modal.classList.add('active');
}

function closeSaveConfirmation() {
    document.getElementById('saveConfirmationModal').classList.remove('active');
}

async function confirmSaveChanges() {
    closeSaveConfirmation();
    await saveChanges();
}

async function saveChanges() {
    if (!pendingChanges.hasChanges()) {
        showMessage('info', 'No changes to save');
        return;
    }
    
    try {
        // Call batch normalize API with all pending renames
        if (pendingChanges.renames.size > 0) {
            const updates = Array.from(pendingChanges.renames.entries()).map(([modelId, normalizedName]) => ({
                model_id: modelId,
                normalized_name: normalizedName
            }));
            
            const normalizeResponse = await fetch(`${API_BASE}/models/batch-normalize`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates })
            });
            
            if (!normalizeResponse.ok) {
                const error = await normalizeResponse.json();
                throw new Error(error.detail || 'Failed to save model name changes');
            }
        }
        
        // Call batch delete API with all pending deletions
        if (pendingChanges.deletions.size > 0) {
            const modelIds = Array.from(pendingChanges.deletions);
            
            const deleteResponse = await fetch(`${API_BASE}/models/batch-delete`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    model_ids: modelIds,
                    provider_id: currentProviderId
                })
            });
            
            if (!deleteResponse.ok) {
                const error = await deleteResponse.json();
                throw new Error(error.detail || 'Failed to delete models');
            }
        }
        
        // Clear pending changes state
        pendingChanges.clear();
        
        // Reload model list once after both complete
        await loadModels(currentProviderId);
        
        // Show success message with next steps
        showSaveSuccessMessage();
    } catch (error) {
        showMessage('error', `Failed to save changes: ${error.message}`);
    }
}

function showSaveSuccessMessage() {
    const modal = document.getElementById('saveSuccessModal');
    modal.classList.add('active');
}

function closeSaveSuccessModal() {
    document.getElementById('saveSuccessModal').classList.remove('active');
}

function updateSaveButtonVisibility() {
    const saveBtn = document.getElementById('saveChangesBtn');
    const changeCountSpan = document.getElementById('changeCount');
    
    if (!saveBtn || !changeCountSpan) return;
    
    const totalChanges = pendingChanges.renames.size + pendingChanges.deletions.size;
    
    if (pendingChanges.hasChanges()) {
        saveBtn.classList.remove('hidden');
        changeCountSpan.textContent = totalChanges;
    } else {
        saveBtn.classList.add('hidden');
    }
}

// uni-api Configuration Functions
async function loadUniapiConfig() {
    const contentDiv = document.getElementById('uniapiConfigContent');
    const downloadBtn = document.getElementById('downloadYamlBtn');
    
    contentDiv.innerHTML = '<div class="loading">Loading configuration...</div>';
    downloadBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/config/uni-api/yaml`);
        
        if (!response.ok) {
            if (response.status === 400) {
                // No groups exist yet
                displayEmptyUniapiState();
                return;
            }
            throw new Error('Failed to load uni-api configuration');
        }
        
        const yamlContent = await response.text();
        
        if (!yamlContent || yamlContent.trim() === '') {
            displayEmptyUniapiState();
            return;
        }
        
        displayUniapiConfig(yamlContent);
        downloadBtn.disabled = false;
        
    } catch (error) {
        console.error('Failed to load uni-api config:', error);
        contentDiv.innerHTML = `<div class="text-danger">Error loading configuration: ${error.message}</div>`;
        downloadBtn.disabled = true;
    }
}

function displayUniapiConfig(yamlContent) {
    const contentDiv = document.getElementById('uniapiConfigContent');
    
    // Count providers and groups
    const providerCount = (yamlContent.match(/- provider:/g) || []).length;
    
    let html = '';
    
    // Add metadata
    html += '<div class="config-meta">';
    html += '<div class="config-meta-item">';
    html += '<span class="config-meta-label">Providers:</span>';
    html += `<span class="config-meta-value">${providerCount}</span>`;
    html += '</div>';
    html += '<div class="config-meta-item">';
    html += '<span class="config-meta-label">Status:</span>';
    html += '<span class="config-meta-value">✓ Ready</span>';
    html += '</div>';
    html += '</div>';
    
    // Add YAML preview
    html += '<div class="yaml-preview">';
    html += escapeHtml(yamlContent);
    html += '</div>';
    
    contentDiv.innerHTML = html;
}

function displayEmptyUniapiState() {
    const contentDiv = document.getElementById('uniapiConfigContent');
    const downloadBtn = document.getElementById('downloadYamlBtn');
    
    contentDiv.className = 'uniapi-config-content empty-state';
    contentDiv.innerHTML = `
        <div class="empty-state-icon">📄</div>
        <div class="empty-state-message">No configuration available</div>
        <div class="empty-state-hint">Run "Sync Configuration" to generate the uni-api config</div>
    `;
    
    downloadBtn.disabled = true;
}

async function downloadUniapiYaml() {
    try {
        const response = await fetch(`${API_BASE}/config/uni-api/download`);
        
        if (!response.ok) {
            throw new Error('Failed to download configuration');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'api.yaml';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showMessage('success', 'Configuration downloaded successfully');
    } catch (error) {
        showMessage('error', `Failed to download configuration: ${error.message}`);
    }
}

// Normalized Names Functions
async function loadNormalizedNames() {
    const listDiv = document.getElementById('normalizedNamesList');
    listDiv.innerHTML = '<div class="loading">Loading...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/models/normalized-names`);
        if (!response.ok) throw new Error('Failed to load normalized names');
        
        normalizedNames = await response.json();
        renderNormalizedNames(normalizedNames);
        
        // Set up search functionality
        const searchInput = document.getElementById('sidebarSearch');
        searchInput.addEventListener('input', (e) => {
            filterNormalizedNames(e.target.value);
        });
    } catch (error) {
        console.error('Failed to load normalized names:', error);
        listDiv.innerHTML = `<div class="text-danger">Error loading names</div>`;
    }
}

function renderNormalizedNames(names, filter = '') {
    const listDiv = document.getElementById('normalizedNamesList');
    
    if (names.length === 0) {
        listDiv.innerHTML = '<div class="text-muted" style="padding: 10px; font-size: 13px;">No normalized names yet</div>';
        return;
    }
    
    // Filter names if search term provided
    let filteredNames = names;
    if (filter) {
        const lowerFilter = filter.toLowerCase();
        filteredNames = names.filter(n => n.name.toLowerCase().includes(lowerFilter));
    }
    
    if (filteredNames.length === 0) {
        listDiv.innerHTML = '<div class="text-muted" style="padding: 10px; font-size: 13px;">No matching names</div>';
        return;
    }
    
    listDiv.innerHTML = filteredNames.map(nameInfo => {
        const isSelected = selectedNormalizedName === nameInfo.name;
        return `
            <div class="normalized-name-item ${isSelected ? 'selected' : ''}" 
                 data-name="${escapeHtml(nameInfo.name)}"
                 onclick="selectNormalizedName('${escapeHtml(nameInfo.name)}')">
                <div class="normalized-name-text">${escapeHtml(nameInfo.name)}</div>
                <div class="normalized-name-meta">
                    <span>📦 ${nameInfo.provider_count} provider(s)</span>
                    <span>🔢 ${nameInfo.model_count} model(s)</span>
                </div>
            </div>
        `;
    }).join('');
}

function filterNormalizedNames(searchTerm) {
    renderNormalizedNames(normalizedNames, searchTerm);
    
    // Also highlight matching names in real-time
    if (searchTerm) {
        highlightMatchingNames(searchTerm);
    } else {
        clearNameHighlights();
    }
}

function highlightMatchingNames(searchTerm) {
    const lowerSearch = searchTerm.toLowerCase();
    const items = document.querySelectorAll('.normalized-name-item');
    
    items.forEach(item => {
        const name = item.dataset.name;
        if (name && name.toLowerCase().includes(lowerSearch)) {
            item.classList.add('highlighted');
        } else {
            item.classList.remove('highlighted');
        }
    });
}

function highlightMatchingNamesInSidebar(inputValue) {
    if (!inputValue || inputValue.length < 1) {
        clearNameHighlights();
        return;
    }
    
    const lowerInput = inputValue.toLowerCase();
    const items = document.querySelectorAll('.normalized-name-item');
    
    items.forEach(item => {
        const name = item.dataset.name;
        if (name && (
            name.toLowerCase().startsWith(lowerInput) ||
            name.toLowerCase().includes(lowerInput)
        )) {
            item.classList.add('highlighted');
        } else {
            item.classList.remove('highlighted');
        }
    });
}

function clearNameHighlights() {
    const items = document.querySelectorAll('.normalized-name-item');
    items.forEach(item => {
        item.classList.remove('highlighted');
        // Don't clear 'selected' class - that's for click selection
    });
}

function selectNormalizedName(name) {
    // Toggle selection
    if (selectedNormalizedName === name) {
        selectedNormalizedName = null;
        clearSuggestions();
    } else {
        selectedNormalizedName = name;
        suggestModelsForNormalization(name);
    }
    
    // Update UI
    const items = document.querySelectorAll('.normalized-name-item');
    items.forEach(item => {
        if (item.dataset.name === name && selectedNormalizedName === name) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

function suggestModelsForNormalization(normalizedName) {
    // Clear previous suggestions
    clearSuggestions();
    
    // Find models that could be normalized to this name using similarity matching
    const rows = document.querySelectorAll('.models-table tbody tr');
    
    rows.forEach(row => {
        const originalNameCell = row.querySelector('td:first-child');
        if (!originalNameCell) return;
        
        const originalName = originalNameCell.textContent.trim();
        const currentNormalizedInput = row.querySelector('.model-name-input');
        const currentNormalizedName = currentNormalizedInput ? currentNormalizedInput.value : originalName;
        
        // Suggest if the original name is similar to the normalized name
        // or if it's not already normalized to something else
        if (isSimilar(originalName, normalizedName) && currentNormalizedName !== normalizedName) {
            row.classList.add('suggested-for-normalization');
        }
    });
}

function clearSuggestions() {
    const rows = document.querySelectorAll('.models-table tbody tr');
    rows.forEach(row => row.classList.remove('suggested-for-normalization'));
}

function isSimilar(str1, str2) {
    // Simple similarity check: case-insensitive comparison with some flexibility
    const s1 = str1.toLowerCase().replace(/[^a-z0-9]/g, '');
    const s2 = str2.toLowerCase().replace(/[^a-z0-9]/g, '');
    
    // Check if one contains the other or they're very similar
    if (s1.includes(s2) || s2.includes(s1)) {
        return true;
    }
    
    // Check Levenshtein distance for close matches
    const distance = levenshteinDistance(s1, s2);
    const maxLength = Math.max(s1.length, s2.length);
    const similarity = 1 - (distance / maxLength);
    
    return similarity > 0.6; // 60% similarity threshold
}

function levenshteinDistance(str1, str2) {
    const matrix = [];
    
    for (let i = 0; i <= str2.length; i++) {
        matrix[i] = [i];
    }
    
    for (let j = 0; j <= str1.length; j++) {
        matrix[0][j] = j;
    }
    
    for (let i = 1; i <= str2.length; i++) {
        for (let j = 1; j <= str1.length; j++) {
            if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                matrix[i][j] = matrix[i - 1][j - 1];
            } else {
                matrix[i][j] = Math.min(
                    matrix[i - 1][j - 1] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j] + 1
                );
            }
        }
    }
    
    return matrix[str2.length][str1.length];
}

// Autocomplete Functions
let autocompleteState = {
    activeInput: null,
    selectedIndex: -1
};

function setupAutocomplete(modelId) {
    const input = document.getElementById(`model-input-${modelId}`);
    const dropdown = document.getElementById(`autocomplete-${modelId}`);
    
    if (!input || !dropdown) return;
    
    // Handle input events
    input.addEventListener('input', (e) => {
        handleAutocompleteInput(modelId, e.target.value);
        // Also highlight matching names in sidebar in real-time
        highlightMatchingNamesInSidebar(e.target.value);
    });
    
    // Handle focus
    input.addEventListener('focus', (e) => {
        autocompleteState.activeInput = modelId;
        if (e.target.value) {
            handleAutocompleteInput(modelId, e.target.value);
            highlightMatchingNamesInSidebar(e.target.value);
        }
    });
    
    // Handle blur (with delay to allow click on dropdown)
    input.addEventListener('blur', () => {
        setTimeout(() => {
            if (autocompleteState.activeInput === modelId) {
                hideAutocomplete(modelId);
                // Clear highlights when input loses focus
                clearNameHighlights();
            }
        }, 200);
    });
    
    // Handle keyboard navigation
    input.addEventListener('keydown', (e) => {
        handleAutocompleteKeydown(modelId, e);
    });
}

function handleAutocompleteInput(modelId, value) {
    const dropdown = document.getElementById(`autocomplete-${modelId}`);
    if (!dropdown) return;
    
    if (!value || value.length < 1) {
        hideAutocomplete(modelId);
        return;
    }
    
    // Filter normalized names by prefix match
    const lowerValue = value.toLowerCase();
    const matches = normalizedNames.filter(n => 
        n.name.toLowerCase().startsWith(lowerValue) ||
        n.name.toLowerCase().includes(lowerValue)
    ).slice(0, 5); // Top 5 matches
    
    if (matches.length === 0) {
        hideAutocomplete(modelId);
        return;
    }
    
    // Render suggestions
    dropdown.innerHTML = matches.map((nameInfo, index) => `
        <div class="autocomplete-item ${index === autocompleteState.selectedIndex ? 'selected' : ''}"
             data-index="${index}"
             data-name="${escapeHtml(nameInfo.name)}"
             onmousedown="selectAutocompleteSuggestion(${modelId}, '${escapeHtml(nameInfo.name)}')">
            <span class="autocomplete-name">${escapeHtml(nameInfo.name)}</span>
            <span class="autocomplete-count">${nameInfo.provider_count} provider(s)</span>
        </div>
    `).join('');
    
    dropdown.classList.add('active');
    autocompleteState.selectedIndex = -1;
}

function handleAutocompleteKeydown(modelId, e) {
    const dropdown = document.getElementById(`autocomplete-${modelId}`);
    if (!dropdown || !dropdown.classList.contains('active')) return;
    
    const items = dropdown.querySelectorAll('.autocomplete-item');
    if (items.length === 0) return;
    
    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            autocompleteState.selectedIndex = Math.min(
                autocompleteState.selectedIndex + 1,
                items.length - 1
            );
            updateAutocompleteSelection(dropdown, items);
            break;
            
        case 'ArrowUp':
            e.preventDefault();
            autocompleteState.selectedIndex = Math.max(
                autocompleteState.selectedIndex - 1,
                -1
            );
            updateAutocompleteSelection(dropdown, items);
            break;
            
        case 'Enter':
            e.preventDefault();
            if (autocompleteState.selectedIndex >= 0) {
                const selectedItem = items[autocompleteState.selectedIndex];
                const name = selectedItem.dataset.name;
                selectAutocompleteSuggestion(modelId, name);
            }
            break;
            
        case 'Escape':
            e.preventDefault();
            hideAutocomplete(modelId);
            break;
    }
}

function updateAutocompleteSelection(dropdown, items) {
    items.forEach((item, index) => {
        if (index === autocompleteState.selectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

function selectAutocompleteSuggestion(modelId, name) {
    const input = document.getElementById(`model-input-${modelId}`);
    if (!input) return;
    
    input.value = name;
    updateModelName(modelId, name);
    hideAutocomplete(modelId);
    
    // Trigger change event
    input.dispatchEvent(new Event('change'));
}

function hideAutocomplete(modelId) {
    const dropdown = document.getElementById(`autocomplete-${modelId}`);
    if (dropdown) {
        dropdown.classList.remove('active');
        dropdown.innerHTML = '';
    }
    autocompleteState.selectedIndex = -1;
    if (autocompleteState.activeInput === modelId) {
        autocompleteState.activeInput = null;
    }
}

// Clean up on page unload
window.addEventListener('beforeunload', (e) => {
    stopGPTLoadStatusPolling();
    
    // Show warning when navigating away with pending changes
    if (pendingChanges.hasChanges()) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        return e.returnValue;
    }
});


// GPT-Load Functions
async function loadGptloadStatus() {
    const statusDiv = document.getElementById('gptloadConnectionStatus');
    const indicator = statusDiv.querySelector('.status-indicator');
    const urlDiv = statusDiv.querySelector('.status-url');
    const infoDiv = statusDiv.querySelector('.status-info');
    const groupCountSpan = document.getElementById('groupCount');
    
    try {
        const response = await fetch(`${API_BASE}/gptload/status`);
        if (!response.ok) throw new Error('Failed to fetch status');
        
        const status = await response.json();
        
        if (status.connected) {
            indicator.classList.add('connected');
            indicator.classList.remove('disconnected');
            urlDiv.textContent = status.url || 'Connected';
            infoDiv.textContent = `${status.group_count || 0} groups | Last sync: ${formatDate(status.last_sync) || 'Never'}`;
            groupCountSpan.textContent = status.group_count || 0;
        } else {
            indicator.classList.add('disconnected');
            indicator.classList.remove('connected');
            urlDiv.textContent = 'Disconnected';
            infoDiv.textContent = status.error || 'Unable to connect';
            groupCountSpan.textContent = '0';
        }
    } catch (error) {
        indicator.classList.add('disconnected');
        indicator.classList.remove('connected');
        urlDiv.textContent = 'Error';
        infoDiv.textContent = error.message;
        groupCountSpan.textContent = '0';
    }
}

async function toggleGptloadGroups() {
    const groupsList = document.getElementById('gptloadGroupsList');
    const btn = document.getElementById('showGroupsBtn');
    
    if (groupsList.classList.contains('hidden')) {
        // Show groups
        groupsList.classList.remove('hidden');
        btn.innerHTML = '<span class="btn-icon">📋</span> Hide Groups';
        await loadGptloadGroups();
    } else {
        // Hide groups
        groupsList.classList.add('hidden');
        const groupCount = document.getElementById('groupCount').textContent;
        btn.innerHTML = `<span class="btn-icon">📋</span> Show Groups (${groupCount})`;
    }
}

async function loadGptloadGroups() {
    const groupsList = document.getElementById('gptloadGroupsList');
    groupsList.innerHTML = '<div class="loading">Loading groups...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/gptload/groups`);
        if (!response.ok) throw new Error('Failed to load groups');
        
        const groups = await response.json();
        
        if (groups.length === 0) {
            groupsList.innerHTML = '<div class="text-muted">No groups found. Sync to GPT-Load to create groups.</div>';
            return;
        }
        
        let html = '';
        groups.forEach(group => {
            html += `
                <div class="group-item">
                    <div>
                        <div class="group-name">${group.name}</div>
                        ${group.provider_name ? `<div class="text-muted" style="font-size: 12px;">Provider: ${group.provider_name}</div>` : ''}
                    </div>
                    <span class="group-type ${group.group_type}">${group.group_type}</span>
                </div>
            `;
        });
        
        groupsList.innerHTML = html;
    } catch (error) {
        groupsList.innerHTML = `<div class="text-danger">Error loading groups: ${error.message}</div>`;
    }
}

async function syncToGptload() {
    const btn = document.getElementById('syncGptloadBtn');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Syncing...';
    
    try {
        const response = await fetch(`${API_BASE}/config/sync-gptload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Sync failed');
        }
        
        const result = await response.json();
        
        // Show success message
        showNotification('GPT-Load sync successful!', 'success');
        
        // Reload status and groups
        await loadGptloadStatus();
        
        // If groups are visible, reload them
        const groupsList = document.getElementById('gptloadGroupsList');
        if (!groupsList.classList.contains('hidden')) {
            await loadGptloadGroups();
        }
        
    } catch (error) {
        showNotification(`Sync failed: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// uni-api Functions
async function toggleYamlPreview() {
    const content = document.getElementById('uniapiConfigContent');
    const btn = document.getElementById('toggleYamlBtn');
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        btn.innerHTML = '<span class="btn-icon">👁️</span> Hide YAML Preview';
        await loadUniapiConfig();
    } else {
        content.classList.add('hidden');
        btn.innerHTML = '<span class="btn-icon">👁️</span> Show YAML Preview';
    }
}

async function generateUniapiConfig() {
    const btn = document.getElementById('generateConfigBtn');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';
    
    try {
        const response = await fetch(`${API_BASE}/config/sync-uniapi`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Generation failed');
        }
        
        const result = await response.json();
        
        // Show success message
        showNotification('uni-api configuration generated successfully!', 'success');
        
        // Update status
        await updateUniapiStatus();
        
        // If preview is visible, reload it
        const content = document.getElementById('uniapiConfigContent');
        if (!content.classList.contains('hidden')) {
            await loadUniapiConfig();
        }
        
        // Enable download button
        document.getElementById('downloadYamlBtn').disabled = false;
        
    } catch (error) {
        showNotification(`Generation failed: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function updateUniapiStatus() {
    try {
        const response = await fetch(`${API_BASE}/config/uni-api/yaml`);
        if (!response.ok) return;
        
        const yaml = await response.text();
        const lines = yaml.split('\n');
        const providerLines = lines.filter(line => line.trim().startsWith('- provider:'));
        
        document.getElementById('uniapiProviderCount').textContent = providerLines.length;
        
        const statusBadge = document.getElementById('uniapiConfigStatus');
        statusBadge.textContent = '✓ Ready';
        statusBadge.classList.add('ready');
        
    } catch (error) {
        console.error('Failed to update uni-api status:', error);
    }
}

// Notification Helper
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Update the polling function
function startGPTLoadStatusPolling() {
    // Initial load
    loadGptloadStatus();
    
    // Poll every 30 seconds
    gptloadStatusInterval = setInterval(loadGptloadStatus, 30000);
}
