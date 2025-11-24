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
    document.getElementById('syncBtn').addEventListener('click', () => syncConfiguration());
    
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
    await loadSyncStatus();
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

// Provider Detail Functions
async function showProviderDetail(providerId) {
    currentProviderId = providerId;
    showView('providerDetailView');
    
    await loadProviderDetail(providerId);
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
            <input type="text" 
                   class="model-name-input ${isEdited ? 'edited' : ''}" 
                   value="${escapeHtml(editedValue)}"
                   data-model-id="${model.id}"
                   onchange="updateModelName(${model.id}, this.value)"
                   ${isMarkedForDeletion ? 'disabled' : ''}>
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
        
        setTimeout(() => {
            showDashboard();
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

function showDashboard() {
    loadDashboard();
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
