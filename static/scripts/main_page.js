// Helper function to safely show toast notifications
function safeShowToast(message, type = 'info') {
  // Function to safely display toast notifications using the notification system
  try {
    // Try using the namespaced version first
    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
      window.notificationSystem.showToast(message, type);
    }
    // Fall back to global version
    else if (typeof window.showToast === 'function') {
      window.showToast(message, type);
    }
    // Last resort - log to console
    else {
      console.log(`Toast (${type}): ${message}`);
      if (type === 'error') {
        alert(message);
      }
    }
  } catch (e) {
    console.error("Error showing toast:", e);
  }
}

// Main page functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize functions
    // checkBotStatus(); // Removed: Handled by bot_status.js
    if (window.BotStatus) { // Ensure BotStatus is available
        window.BotStatus.checkStatus(); // Initial explicit check if needed, or rely on its internal init
    }
    loadChannels();
    
    try {
        loadTTSStats();
    } catch (e) {
        console.error('Error initializing TTS stats:', e);
    }
    
    try {
        loadRecentTTS();
    } catch (e) {
        console.error('Error initializing recent TTS:', e);
    }
    
    try {
        loadSystemInfo();
    } catch (e) {
        console.error('Error initializing system info:', e);
    }
    
    // Set up refresh intervals, but NOT on settings page
    if (!window.location.pathname.includes('settings')) {
        console.log("Setting up main page refresh intervals");
        // setInterval(checkBotStatus, 30000); // Removed: Handled by bot_status.js
        setInterval(loadRecentTTS, 60000);  // Every minute
    } else {
        console.log("On settings page - skipping refresh intervals");
    }
    
    // Set up event listeners - with null check
    const refreshRecentBtn = document.getElementById('refreshRecentBtn');
    if (refreshRecentBtn) {
        refreshRecentBtn.addEventListener('click', function() {
            this.disabled = true;
            loadRecentTTS();
            setTimeout(() => { this.disabled = false; }, 2000);
        });
    }
});

// Enhanced bot status check function - REMOVED as bot_status.js handles this.
/*
function checkBotStatus() {
    const statusSpinner = document.getElementById('statusSpinner');
    const statusText = document.getElementById('botStatusText');
    const lastUpdated = document.getElementById('statusLastUpdated');
    const uptimeDisplay = document.getElementById('botUptime');
    
    // Look for buttons in both bot_control and main dashboard
    const startBotBtn = document.getElementById('startBotBtn') || document.getElementById('quickStartBtn');
    const stopBotBtn = document.getElementById('stopBotBtn') || document.getElementById('quickStopBtn');
    
    if (statusSpinner) statusSpinner.style.display = 'inline-block';
    
    fetch('/api/bot-status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (statusSpinner) statusSpinner.style.display = 'none';
            
            // Process is running but might not be connected
            if (data.running) {
                if (data.connected) {
                    if (statusText) {
                        statusText.textContent = 'Running & Connected';
                        statusText.className = 'mb-0 text-success';
                    }
                } else {
                    if (statusText) {
                        statusText.textContent = 'Running (Not Connected)';
                        statusText.className = 'mb-0 text-warning';
                    }
                }
                
                // Update bot control buttons if they exist
                if (startBotBtn) startBotBtn.disabled = true;
                if (stopBotBtn) stopBotBtn.disabled = false;
                
                // Show uptime if available
                if (uptimeDisplay && data.uptime) {
                    uptimeDisplay.textContent = data.uptime;
                }
            } else {
                if (statusText) {
                    statusText.textContent = 'Stopped';
                    statusText.className = 'mb-0 text-danger';
                }
                
                // Update bot control buttons if they exist
                if (startBotBtn) startBotBtn.disabled = false;
                if (stopBotBtn) stopBotBtn.disabled = true;
                
                if (uptimeDisplay) {
                    uptimeDisplay.textContent = 'Not running';
                }
            }
            
            // Show when status was last checked
            if (lastUpdated) {
                lastUpdated.textContent = 'Last updated: ' + new Date().toLocaleTimeString();
            }
            
            // If there's an error message, display it
            if (data.error) {
                console.warn('Bot status check warning:', data.error);
                showToast('Bot status check warning: ' + data.error, 'warning');
            }
        })
        .catch(error => {
            console.error('Error checking bot status:', error);
            if (statusSpinner) statusSpinner.style.display = 'none';
            
            if (statusText) {
                statusText.textContent = 'Unknown';
                statusText.className = 'mb-0 text-warning';
            }
            
            // Don't show toast for common errors
            if (error.message !== "Cannot read properties of null (reading 'disabled')") {
                showToast('Failed to check bot status: ' + error.message, 'error');
            }
        });
}
*/

// Enhanced channel display function
function loadChannels() {
    const channelsList = document.getElementById('channelsList');
    const spinner = document.getElementById('channelLoadingSpinner');
    const channelCountElement = document.getElementById('channelCount');
    
    // Setup refresh channels button if it exists
    const refreshChannelsBtn = document.getElementById('refreshChannelsBtn');
    if (refreshChannelsBtn) {
        refreshChannelsBtn.addEventListener('click', function() {
            this.disabled = true;
            loadChannels();
            setTimeout(() => { this.disabled = false; }, 1000);
        });
    }
    
    if (!channelsList && !channelCountElement) return;
    
    if (spinner) spinner.style.display = 'block';
    
    fetch('/api/channels')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (spinner) spinner.style.display = 'none';
            
            // Log the raw data received for channels
            console.log("Data received for /api/channels:", JSON.parse(JSON.stringify(data)));

            // Count connected channels - update even if the list doesn't exist
            const connectedCount = data.filter(channel => channel.currently_connected).length;
            if (channelCountElement) {
                channelCountElement.textContent = connectedCount.toString();
            }
            
            // Update channels list if it exists
            if (channelsList) {
                if (data.length === 0) {
                    channelsList.innerHTML = '<div class="text-center text-muted">No channels configured</div>';
                    return;
                }
                
                channelsList.innerHTML = '';
                
                // Sort channels: connected first, then alphabetically
                data.sort((a, b) => {
                    if (a.currently_connected !== b.currently_connected) {
                        // True (connected) should come before false (not connected)
                        return (b.currently_connected ? 1 : 0) - (a.currently_connected ? 1 : 0);
                    }
                    // Ensure names exist before comparing
                    const nameA = a.name || '';
                    const nameB = b.name || '';
                    return nameA.localeCompare(nameB);
                });
                
                data.forEach(channel => {
                    const item = document.createElement('div');
                    item.className = 'list-group-item d-flex justify-content-between align-items-center';
                    
                    const statusIndicator = document.createElement('span');
                    statusIndicator.className = `status-indicator status-${channel.currently_connected ? 'online' : 'offline'}`;
                    
                    const channelName = document.createElement('span');
                    channelName.textContent = channel.name;
                    
                    const statusContainer = document.createElement('div');
                    statusContainer.appendChild(statusIndicator);
                    statusContainer.appendChild(channelName);
                    
                    const badges = document.createElement('div');
                    
                    if (channel.tts_enabled) {
                        const ttsBadge = document.createElement('span');
                        ttsBadge.className = 'badge bg-info rounded-pill ms-1';
                        ttsBadge.innerHTML = '<i class="fas fa-volume-up" title="TTS Enabled"></i>';
                        badges.appendChild(ttsBadge);
                    }
                    
                    if (!channel.configured_to_join) {
                        const notJoinBadge = document.createElement('span');
                        notJoinBadge.className = 'badge bg-warning rounded-pill ms-1';
                        notJoinBadge.innerHTML = '<i class="fas fa-exclamation-triangle" title="Not configured to join"></i>';
                        badges.appendChild(notJoinBadge);
                    }
                    
                    item.appendChild(statusContainer);
                    item.appendChild(badges);
                    channelsList.appendChild(item);
                });
            }
        })
        .catch(error => {
            console.error('Error loading channels:', error);
            if (spinner) spinner.style.display = 'none';
            
            if (channelsList) {
                channelsList.innerHTML = '<div class="text-center text-danger">Error loading channels</div>';
            }
        });
}

// Updated loadTTSStats with better error handling
function loadTTSStats() {
    // Check if elements exist first
    const ttsTodayCount = document.getElementById('ttsTodayCount');
    const ttsWeekCount = document.getElementById('ttsWeekCount');
    const ttsTotalCount = document.getElementById('ttsTotalCount');
    
    if (!ttsTodayCount || !ttsWeekCount || !ttsTotalCount) {
        console.log('TTS stats elements not found, skipping update');
        return;
    }
    
    fetch('/api/tts-stats')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            ttsTodayCount.textContent = data.today || '0';
            ttsWeekCount.textContent = data.week || '0';
            ttsTotalCount.textContent = data.total || '0';
        })
        .catch(error => {
            console.error('Error loading TTS stats:', error);
            // Don't update the UI on error
        });
}

// Load recent TTS messages
function loadRecentTTS() {
    const ttsTableBody = document.getElementById('recentTTSBody');
    const ttsTable = document.getElementById('recentTTSTable');
    const noTTSDataMessage = document.getElementById('noTTSData');
    const spinner = document.getElementById('ttsLoadingSpinner'); // Spinner for the whole TTS panel

    if (!ttsTableBody || !ttsTable || !noTTSDataMessage) {
        console.warn('Recent TTS table elements not found, skipping update.');
        return;
    }

    if (spinner) spinner.style.display = 'block';
    if (ttsTable) ttsTable.style.display = 'none';
    if (noTTSDataMessage) noTTSDataMessage.style.display = 'none';

    fetch('/api/recent-tts')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (spinner) spinner.style.display = 'none';
            ttsTableBody.innerHTML = ''; // Clear previous entries

            if (data.error || data.length === 0) {
                if (noTTSDataMessage) noTTSDataMessage.style.display = 'block';
                if (ttsTable) ttsTable.style.display = 'none';
                if (data.error) console.error('Error in TTS data:', data.error);
                return;
            }
            
            if (ttsTable) ttsTable.style.display = 'table'; // Or 'block' if it's not a table element
            if (noTTSDataMessage) noTTSDataMessage.style.display = 'none';

            data.forEach((item, index) => {
                console.log(`[loadRecentTTS] Processing item ${index + 1}/${data.length}:`, JSON.parse(JSON.stringify(item)));
                const row = ttsTableBody.insertRow();

                const cellChannel = row.insertCell();
                cellChannel.className = 'text-center';
                cellChannel.textContent = item.channel;

                const cellMessage = row.insertCell();
                cellMessage.textContent = item.message.length > 70 ? 
                    item.message.substring(0, 70) + '...' : 
                    item.message;
                cellMessage.title = item.message;


                const cellTime = row.insertCell();
                try {
                    cellTime.textContent = new Date(item.timestamp).toLocaleString();
                } catch (e) {
                    cellTime.textContent = item.timestamp; // Fallback if date parsing fails
                    console.warn("Could not parse timestamp:", item.timestamp, e);
                }


                const cellVoice = row.insertCell();
                cellVoice.textContent = item.voice_preset || 'N/A';

                const cellActions = row.insertCell();
                cellActions.className = 'text-center';

                const playBtn = document.createElement('button');
                playBtn.className = 'btn btn-sm btn-primary me-1 action-btn';
                playBtn.innerHTML = '<i class="fas fa-play"></i>';
                playBtn.title = 'Play TTS';
                playBtn.onclick = () => {
                    const audioSrc = `/static/${item.file_path}`;
                    if (typeof window.playAudioIfExists === 'function') {
                        window.playAudioIfExists(audioSrc);
                    } else {
                        console.warn('playAudioIfExists function is not defined on window.');
                        alert('Playback functionality is not available.');
                    }
                };
                
                const downloadBtn = document.createElement('a');
                downloadBtn.className = 'btn btn-sm btn-secondary action-btn';
                downloadBtn.innerHTML = '<i class="fas fa-download"></i>';
                downloadBtn.title = 'Download TTS';
                // Use item.file_path which should be like 'outputs/channel/filename.wav'
                // The link should be relative to the domain, pointing to the static serve path
                downloadBtn.href = `/static/${item.file_path}`; 
                downloadBtn.download = item.file_path.split('/').pop(); // Suggests filename for download

                cellActions.appendChild(playBtn);
                cellActions.appendChild(downloadBtn);
            });
        })
        .catch(error => {
            console.error('Error loading recent TTS:', error);
            if (spinner) spinner.style.display = 'none';
            if (noTTSDataMessage) {
                noTTSDataMessage.style.display = 'block';
                noTTSDataMessage.innerHTML = '<div class="empty-state-content"><i class="fas fa-exclamation-circle empty-state-icon text-danger"></i><h4>Error Loading TTS</h4><p class="text-muted">Could not fetch recent TTS messages.</p></div>';
            }
            if (ttsTable) ttsTable.style.display = 'none';
        });
}

// Updated loadSystemInfo with better error handling
function loadSystemInfo() {
    // Check if elements exist first
    const botUptime = document.getElementById('botUptime');
    const messageCount = document.getElementById('messageCount');
    
    if (!botUptime && !messageCount) {
        console.log('System info elements not found, skipping update');
        return;
    }
    
    // Get the total model stats (including lines processed)
    fetch('/get-stats')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Update message count using the brain stats
            if (messageCount) {
                let totalLines = 0;
                data.forEach(channel => {
                    if (channel.line_count) {
                        totalLines += parseInt(channel.line_count);
                    }
                });
                messageCount.textContent = totalLines.toLocaleString();
            }
            
            // Get additional bot info for uptime
            fetch('/api/bot-status')
                .then(response => response.json())
                .then(botData => {
                    if (botUptime && botData.uptime) {
                        botUptime.textContent = botData.uptime;
                    } else if (botUptime) {
                        botUptime.textContent = 'Not running';
                    }
                })
                .catch(error => {
                    console.error('Error loading bot status:', error);
                });
        })
        .catch(error => {
            console.error('Error loading model stats:', error);
        });
}

// Add this function to handle reconnect requests
function reconnectBot() {
    const reconnectBtn = document.getElementById('reconnectBtn');
    
    if (reconnectBtn) {
        reconnectBtn.disabled = true;
        reconnectBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Reconnecting...';
    }
    
    showToast('Attempting to reconnect bot...', 'info');
    
    fetch('/api/reconnect-bot', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Reconnect command sent', 'success');
        } else {
            showToast(data.message || 'Failed to reconnect', 'error');
        }
    })
    .catch(error => {
        console.error('Error reconnecting bot:', error);
        showToast('Error requesting reconnect', 'error');
    })
    .finally(() => {
        if (reconnectBtn) {
            reconnectBtn.disabled = false;
            reconnectBtn.innerHTML = '<i class="fas fa-plug me-1"></i>Force Reconnect';
            
            // Check status again after a delay
            setTimeout(() => {
                checkBotStatus();
                loadChannels();
            }, 3000);
        }
    });
}

// Bot control function - Start bot
function startBot() {
    // Get button elements with null check - support both bot control page and dashboard
    const startBotBtn = document.getElementById('startBotBtn') || document.getElementById('quickStartBtn');
    const stopBotBtn = document.getElementById('stopBotBtn') || document.getElementById('quickStopBtn');
    
    // Disable buttons if they exist
    if (startBotBtn) startBotBtn.disabled = true;
    if (stopBotBtn) stopBotBtn.disabled = true;
    
    showToast('Starting bot...', 'info');
    
    // Use the correct API endpoint from the existing application
    fetch('/start_bot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Bot started successfully', 'success');
        } else {
            showToast(`Failed to start bot: ${data.message || 'Unknown error'}`, 'error');
        }
        
        checkBotStatus();
    })
    .catch(error => {
        console.error('Error starting bot:', error);
        showToast('Error starting bot', 'error');
        
        // Re-check status which will properly handle button states
        checkBotStatus();
    });
}

// Bot control function - Stop bot
function stopBot() {
    // Get button elements with null check - support both bot control page and dashboard
    const startBotBtn = document.getElementById('startBotBtn') || document.getElementById('quickStartBtn');
    const stopBotBtn = document.getElementById('stopBotBtn') || document.getElementById('quickStopBtn');
    
    // Disable buttons if they exist
    if (startBotBtn) startBotBtn.disabled = true;
    if (stopBotBtn) stopBotBtn.disabled = true;
    
    showToast('Stopping bot...', 'info');
    
    // Use the correct API endpoint from the existing application
    fetch('/stop_bot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Bot stopped successfully', 'success');
        } else {
            showToast(`Failed to stop bot: ${data.message || 'Unknown error'}`, 'error');
        }
        
        checkBotStatus();
    })
    .catch(error => {
        console.error('Error stopping bot:', error);
        showToast('Error stopping bot', 'error');
        
        // Re-check status which will properly handle button states
        checkBotStatus();
    });
} 
