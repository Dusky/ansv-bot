// Beta Stats Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initializeStatsPage();
});

function initializeStatsPage() {
    setupModelSorting();
    setupChannelPerformanceToggle();
    setupQuickActions();
    setupAutoRefresh();
    loadRecentActivity();
}

function setupModelSorting() {
    const sortSelect = document.getElementById('modelSort');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            sortModels(this.value);
        });
    }
}

function sortModels(criteria) {
    const modelsGrid = document.querySelector('.models-grid');
    if (!modelsGrid) return;

    const modelCards = Array.from(modelsGrid.querySelectorAll('.model-card'));
    
    modelCards.sort((a, b) => {
        let aValue, bValue;
        
        switch (criteria) {
            case 'name':
                aValue = a.querySelector('.model-name').textContent.toLowerCase();
                bValue = b.querySelector('.model-name').textContent.toLowerCase();
                return aValue.localeCompare(bValue);
            
            case 'size':
                aValue = parseFloat(a.querySelector('.model-size').textContent);
                bValue = parseFloat(b.querySelector('.model-size').textContent);
                return bValue - aValue; // Descending
            
            case 'messages':
                aValue = parseInt(a.querySelector('.model-messages').textContent.replace(/,/g, ''));
                bValue = parseInt(b.querySelector('.model-messages').textContent.replace(/,/g, ''));
                return bValue - aValue; // Descending
            
            case 'updated':
                aValue = new Date(a.dataset.updated || 0);
                bValue = new Date(b.dataset.updated || 0);
                return bValue - aValue; // Most recent first
            
            default:
                return 0;
        }
    });

    // Re-append sorted cards
    modelCards.forEach(card => modelsGrid.appendChild(card));
}

function setupChannelPerformanceToggle() {
    const toggleButtons = document.querySelectorAll('[data-toggle="channel-view"]');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const view = this.dataset.view;
            toggleChannelView(view);
            
            // Update active button
            toggleButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

function toggleChannelView(view) {
    const tableView = document.querySelector('.channel-table-view');
    const gridView = document.querySelector('.channel-grid-view');
    
    if (view === 'table') {
        tableView?.classList.remove('d-none');
        gridView?.classList.add('d-none');
    } else {
        tableView?.classList.add('d-none');
        gridView?.classList.remove('d-none');
    }
}

function setupQuickActions() {
    // Rebuild all models
    const rebuildAllBtn = document.querySelector('[data-action="rebuild-all"]');
    if (rebuildAllBtn) {
        rebuildAllBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to rebuild all models? This may take several minutes.')) {
                rebuildAllModels();
            }
        });
    }

    // Export stats
    const exportBtn = document.querySelector('[data-action="export-stats"]');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportStats);
    }

    // Clear cache
    const clearCacheBtn = document.querySelector('[data-action="clear-cache"]');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear all cached data?')) {
                clearCache();
            }
        });
    }

    // Individual model rebuild buttons
    document.querySelectorAll('[data-action="rebuild-model"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const modelName = this.dataset.model;
            if (confirm(`Rebuild model for ${modelName}?`)) {
                rebuildModel(modelName);
            }
        });
    });
}

async function rebuildAllModels() {
    try {
        showToast('Starting model rebuild...', 'info');
        const response = await fetch('/api/rebuild-all-models', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showToast('All models rebuild started successfully', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            throw new Error('Failed to start rebuild');
        }
    } catch (error) {
        console.error('Error rebuilding models:', error);
        showToast('Failed to rebuild models', 'error');
    }
}

async function rebuildModel(modelName) {
    try {
        showToast(`Rebuilding ${modelName} model...`, 'info');
        const response = await fetch(`/api/rebuild-model/${modelName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showToast(`${modelName} model rebuild started`, 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            throw new Error('Failed to rebuild model');
        }
    } catch (error) {
        console.error('Error rebuilding model:', error);
        showToast(`Failed to rebuild ${modelName} model`, 'error');
    }
}

async function exportStats() {
    try {
        const response = await fetch('/api/export-stats');
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ansv-stats-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            showToast('Stats exported successfully', 'success');
        } else {
            throw new Error('Failed to export stats');
        }
    } catch (error) {
        console.error('Error exporting stats:', error);
        showToast('Failed to export stats', 'error');
    }
}

async function clearCache() {
    try {
        const response = await fetch('/api/clear-cache', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showToast('Cache cleared successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            throw new Error('Failed to clear cache');
        }
    } catch (error) {
        console.error('Error clearing cache:', error);
        showToast('Failed to clear cache', 'error');
    }
}

function setupAutoRefresh() {
    // Auto-refresh stats every 30 seconds
    setInterval(async () => {
        try {
            await updateStats();
        } catch (error) {
            console.error('Error updating stats:', error);
        }
    }, 30000);
}

async function updateStats() {
    try {
        const response = await fetch('/api/stats-data');
        if (!response.ok) return;
        
        const data = await response.json();
        
        // Update summary cards
        updateSummaryCards(data.summary);
        
        // Update recent activity if needed
        if (data.recent_activity) {
            updateRecentActivity(data.recent_activity);
        }
        
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

function updateSummaryCards(summary) {
    // Update total messages
    const totalMessagesEl = document.querySelector('[data-stat="total-messages"]');
    if (totalMessagesEl && summary.total_messages !== undefined) {
        totalMessagesEl.textContent = summary.total_messages.toLocaleString();
    }
    
    // Update total TTS
    const totalTTSEl = document.querySelector('[data-stat="total-tts"]');
    if (totalTTSEl && summary.total_tts !== undefined) {
        totalTTSEl.textContent = summary.total_tts.toLocaleString();
    }
    
    // Update active channels
    const activeChannelsEl = document.querySelector('[data-stat="active-channels"]');
    if (activeChannelsEl && summary.active_channels !== undefined) {
        activeChannelsEl.textContent = summary.active_channels;
    }
}

async function loadRecentActivity() {
    try {
        const response = await fetch('/api/recent-activity');
        if (!response.ok) return;
        
        const activities = await response.json();
        updateRecentActivity(activities);
        
    } catch (error) {
        console.error('Error loading recent activity:', error);
    }
}

function updateRecentActivity(activities) {
    const activityList = document.querySelector('.activity-list');
    if (!activityList || !activities.length) return;
    
    activityList.innerHTML = activities.map(activity => `
        <div class="activity-item">
            <div class="activity-icon">
                <i class="${getActivityIcon(activity.type)}"></i>
            </div>
            <div class="activity-content">
                <div class="activity-title">${activity.title}</div>
                <div class="activity-description">${activity.description}</div>
                <div class="activity-time">${formatTimeAgo(activity.timestamp)}</div>
            </div>
        </div>
    `).join('');
}

function getActivityIcon(type) {
    const icons = {
        'message': 'fas fa-comment',
        'tts': 'fas fa-volume-up',
        'model': 'fas fa-brain',
        'channel': 'fas fa-hashtag',
        'system': 'fas fa-cog'
    };
    return icons[type] || 'fas fa-info-circle';
}

function formatTimeAgo(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now - time) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
}