/**
 * bot_control.js - Centralized bot control system
 * 
 * This file provides functionality for starting, stopping and managing the bot.
 * It works with bot_status.js to provide a complete bot management solution.
 */

// Create a global namespace for bot control
window.BotController = window.BotController || {
    // Initialize the bot controller
    init: function() {
        console.log("BotController initializing");
        
        // Setup event listeners for control buttons
        this.setupEventListeners();
        
        // Check for existing bot instances
        this.checkForExistingBotInstance();
        
        // Load channels if the channel table exists
        const channelList = document.getElementById('channelsTableBody');
        if (channelList) {
            this.loadChannels();
        }
        
        console.log("BotController initialized");
        return this;
    },
    
    // Set up event listeners for control buttons
    setupEventListeners: function() {
        // Get button elements
        const startBtn = document.getElementById('startBotBtn');
        const stopBtn = document.getElementById('stopBotBtn');
        
        // Setup start button
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startBot());
        }
        
        // Setup stop button
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopBot());
        }
    },
    
    // Check for existing bot instances
    checkForExistingBotInstance: function() {
        fetch('/check_existing_instance')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Found existing bot instance:', data);
                    
                    // Show notification using notification system
                    this.showNotification(`Bot is already running (PID: ${data.pid})`, 'info');
                    
                    // Trigger status check to update buttons
                    if (window.BotStatus) {
                        window.BotStatus.checkStatus();
                    }
                }
            })
            .catch(error => {
                console.error('Error checking for existing instances:', error);
            });
    },
    
    // Start the bot with optional TTS support
    startBot: function() {
        // Disable buttons during operation
        document.getElementById('startBotBtn').disabled = true;
        document.getElementById('stopBotBtn').disabled = true;
        
        // Update UI to show starting state
        const startBtn = document.getElementById('startBotBtn');
        startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Starting...';
        
        // Show a loading notification
        this.showNotification('Starting bot...', 'info');
        
        // Get TTS status with better validation
        const ttsElement = document.getElementById('enable_tts');
        let enableTTS = false;
        
        if (ttsElement) {
            console.log('TTS checkbox element found, checked state:', ttsElement.checked);
            enableTTS = ttsElement.checked;
        } else {
            console.warn('TTS checkbox element not found');
        }
        
        console.log('Starting bot with TTS enabled:', enableTTS);
        
        // Clear any previous error messages
        const errorDisplay = document.getElementById('botStartError');
        if (errorDisplay) {
            errorDisplay.textContent = '';
            errorDisplay.style.display = 'none';
        }
        
        // Send request to start bot
        fetch('/start_bot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enable_tts: enableTTS })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Bot start response:', data);
            
            if (data.success) {
                this.showNotification('Bot started successfully', 'success');
                
                // Reset the button text immediately for successful start
                startBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Bot';
            } else {
                this.showNotification(`Failed to start bot: ${data.message || 'Unknown error'}`, 'error');
                
                // Show detailed error information
                if (errorDisplay) {
                    // Format the log output for better readability
                    let errorContent = data.message || 'Unknown error';
                    if (data.log) {
                        errorContent += '\n\nLog output:\n' + data.log;
                    }
                    
                    errorDisplay.textContent = errorContent;
                    errorDisplay.style.display = 'block';
                }
                
                console.error('Bot start failed:', data.log || data.message);
                
                // Reset the button state for failed start
                startBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Bot';
                document.getElementById('startBotBtn').disabled = false;
                document.getElementById('stopBotBtn').disabled = false;
            }
        })
        .catch(error => {
            console.error('Error starting bot:', error);
            this.showNotification(`Error starting bot: ${error.message}`, 'error');
            
            // Show the error in the UI
            if (errorDisplay) {
                errorDisplay.textContent = error.message;
                errorDisplay.style.display = 'block';
            }
            
            // Reset the button state on error
            startBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Bot';
            document.getElementById('startBotBtn').disabled = false;
            document.getElementById('stopBotBtn').disabled = false;
        })
        .finally(() => {
            // Refresh status after a short delay
            setTimeout(() => {
                if (window.BotStatus) {
                    window.BotStatus.checkStatus();
                }
            }, 3000);
        });
    },
    
    // Stop the bot
    stopBot: function() {
        if (confirm('Are you sure you want to stop the bot?')) {
            // Disable buttons during operation
            document.getElementById('startBotBtn').disabled = true;
            document.getElementById('stopBotBtn').disabled = true;
            
            // Show a loading notification
            this.showNotification('Stopping bot...', 'info');
            
            fetch('/stop_bot', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showNotification('Bot stopped successfully', 'success');
                } else {
                    this.showNotification(`Failed to stop bot: ${data.message}`, 'error');
                }
                
                // Update status immediately
                if (window.BotStatus) {
                    window.BotStatus.checkStatus();
                }
            })
            .catch(error => {
                console.error('Error stopping bot:', error);
                this.showNotification('Error stopping bot', 'error');
                
                // Restore button states based on last known status
                document.getElementById('startBotBtn').disabled = false;
                document.getElementById('stopBotBtn').disabled = false;
            });
        }
    },
    
    // Load channels 
    loadChannels: function() {
        console.log('Loading channels...');
        
        // If ChannelManager exists, use it instead
        if (window.ChannelManager && typeof window.ChannelManager.loadChannels === 'function') {
            window.ChannelManager.loadChannels(channels => {
                this.populateChannelTable(channels);
            });
            return;
        }
        
        // Fallback to direct implementation if ChannelManager is not available
        
        // Clear existing channel list
        const channelList = document.getElementById('channelsTableBody');
        if (!channelList) {
            console.warn('Channel list element not found - looking for alternative elements');
            // Try to find the alternative table body
            const alternativeList = document.getElementById('channelList');
            if (!alternativeList) {
                console.error('No channel list element found on page');
                return;
            }
        }
        
        // Show loading indicator
        if (channelList) {
            channelList.innerHTML = '<tr><td colspan="6" class="text-center"><div class="spinner-border text-primary" role="status"></div><p>Loading channels...</p></td></tr>';
        }
        
        // Use the correct endpoint
        console.log('Fetching channel data from /api/channels endpoint');
        fetch('/api/channels')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Channel data received:', data);
                this.populateChannelTable(data);
            })
            .catch(error => {
                console.error('Error loading channels:', error);
                
                if (channelList) {
                    channelList.innerHTML = `
                        <tr><td colspan="6" class="text-center text-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            Error loading channels: ${error.message}
                            <button class="btn btn-sm btn-primary ms-3" onclick="window.BotController.loadChannels()">
                                <i class="fas fa-redo me-1"></i>Retry
                            </button>
                        </td></tr>
                    `;
                }
            });
    },
    
    // Populate channel table with data
    populateChannelTable: function(data) {
        const channelList = document.getElementById('channelsTableBody');
        
        if (!channelList) {
            console.warn('Channel list element not found');
            return;
        }
        
        if (!data || data.length === 0) {
            channelList.innerHTML = '<tr><td colspan="6" class="text-center">No channels configured</td></tr>';
            return;
        }
        
        // Clear existing content
        channelList.innerHTML = '';
        
        // Process each channel for table view
        data.forEach(channel => {
            // Normalize channel data format
            const normalizedChannel = this.normalizeChannelData(channel);
            
            const row = document.createElement('tr');
            
            // Create cells with correct property names from the API
            const nameCell = document.createElement('td');
            nameCell.innerHTML = `<a href="https://twitch.tv/${normalizedChannel.name}" target="_blank">${normalizedChannel.name}</a>`;
            
            const statusCell = document.createElement('td');
            statusCell.innerHTML = `<span class="badge ${normalizedChannel.connected ? 'bg-success' : 'bg-danger'}">${normalizedChannel.connected ? 'Connected' : 'Disconnected'}</span>`;
            
            const ttsCell = document.createElement('td');
            ttsCell.innerHTML = `<span class="badge ${normalizedChannel.tts_enabled ? 'bg-success' : 'bg-secondary'}">${normalizedChannel.tts_enabled ? 'Enabled' : 'Disabled'}</span>`;
            
            // Add cells for messages and last activity (if available)
            const messagesCell = document.createElement('td');
            messagesCell.textContent = normalizedChannel.messages_sent || '0';
            
            const activityCell = document.createElement('td');
            activityCell.textContent = normalizedChannel.last_activity || 'N/A';
            
            // Add action buttons
            const actionsCell = document.createElement('td');
            actionsCell.innerHTML = `
                <button class="btn btn-sm btn-outline-primary me-1" onclick="joinChannel('${normalizedChannel.name}')">
                    <i class="fas fa-sign-in-alt me-1"></i>Join
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="leaveChannel('${normalizedChannel.name}')">
                    <i class="fas fa-sign-out-alt me-1"></i>Leave
                </button>
            `;
            
            // Add all cells to row
            row.appendChild(nameCell);
            row.appendChild(statusCell);
            row.appendChild(ttsCell);
            row.appendChild(messagesCell);
            row.appendChild(activityCell);
            row.appendChild(actionsCell);
            
            // Add row to table
            channelList.appendChild(row);
        });
    },
    
    // Normalize channel data from different sources to a consistent format
    normalizeChannelData: function(channel) {
        // If ChannelManager exists, use its normalization method
        if (window.ChannelManager && typeof window.ChannelManager.normalizeChannelData === 'function') {
            return window.ChannelManager.normalizeChannelData([channel])[0];
        }
        
        // Otherwise do basic normalization
        let normalizedChannel = {
            name: null,
            connected: false,
            tts_enabled: false,
            messages_sent: 0,
            last_activity: null
        };
        
        if (Array.isArray(channel)) {
            normalizedChannel.name = channel[0];
            if (channel.length > 1) normalizedChannel.tts_enabled = !!channel[1];
            if (channel.length > 3) normalizedChannel.connected = !!channel[3];
        } else if (typeof channel === 'object' && channel !== null) {
            normalizedChannel.name = channel.name || channel.channel_name || '';
            normalizedChannel.connected = !!channel.currently_connected || !!channel.connected;
            normalizedChannel.tts_enabled = !!channel.tts_enabled;
            normalizedChannel.messages_sent = channel.messages_sent || 0;
            normalizedChannel.last_activity = channel.last_activity || 'N/A';
        } else if (typeof channel === 'string') {
            normalizedChannel.name = channel;
        }
        
        return normalizedChannel;
    },
    
    // Safely show notifications using the notification system
    showNotification: function(message, type = 'info') {
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
            console.error("Error showing notification:", e);
        }
    }
};

// Initialize the bot controller when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.BotController.init();
});

// Legacy compatibility layer - provide functions that older code might use
// These functions now call into the BotController to maintain backward compatibility

// Legacy function for checking bot status
function checkBotStatus() {
    if (window.BotStatus) {
        window.BotStatus.checkStatus();
    }
}

// Legacy function for starting the bot
function startBot() {
    window.BotController.startBot();
}

// Legacy function for stopping the bot
function stopBot() {
    window.BotController.stopBot();
}

// Legacy function for checking for existing bot instances
function checkForExistingBotInstance() {
    window.BotController.checkForExistingBotInstance();
}

// Legacy function for loading channels
function loadChannels() {
    window.BotController.loadChannels();
}

// Legacy function for safely showing toast notifications
function safeShowToast(message, type = 'info') {
    window.BotController.showNotification(message, type);
}