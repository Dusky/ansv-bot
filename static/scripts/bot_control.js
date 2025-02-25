// Function to check bot status
function checkBotStatus() {
    const statusSpinner = document.getElementById('statusSpinner');
    const statusText = document.getElementById('botStatusText');
    const lastUpdated = document.getElementById('statusLastUpdated');
    const startBtn = document.getElementById('startBotBtn');
    const stopBtn = document.getElementById('stopBotBtn');
    
    // Show spinner while checking
    if (statusSpinner) statusSpinner.style.display = 'block';
    
    fetch('/api/bot-status')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(status => {
            console.log("Bot status:", status); // Debug info
            
            if (status.running) {
                // Bot is running
                statusText.textContent = 'Bot is Running';
                statusText.className = 'mb-0 text-success';
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                // Bot is not running
                statusText.textContent = 'Bot is Stopped';
                statusText.className = 'mb-0 text-danger';
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
            
            // Update timestamp
            const now = new Date();
            lastUpdated.textContent = `Last updated: ${now.toLocaleTimeString()}`;
        })
        .catch(error => {
            console.error('Error checking bot status:', error);
            statusText.textContent = 'Error Checking Status';
            statusText.className = 'mb-0 text-warning';
        })
        .finally(() => {
            // Hide spinner
            if (statusSpinner) statusSpinner.style.display = 'none';
        });
}

// Check status on page load and every 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    // Initial check
    checkBotStatus();
    
    // Setup periodic checking
    setInterval(checkBotStatus, 5000);
    
    // Setup button handlers if not already set
    const startBtn = document.getElementById('startBotBtn');
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            startBot();
        });
    }
    
    const stopBtn = document.getElementById('stopBotBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            stopBot();
        });
    }

    // Check for existing bot instances first
    checkForExistingBotInstance();
});

// Improved bot starting function
function startBot() {
    // Disable buttons during operation
    document.getElementById('startBotBtn').disabled = true;
    document.getElementById('stopBotBtn').disabled = true;
    
    // Update UI to show starting state
    const startBtn = document.getElementById('startBotBtn');
    startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Starting...';
    
    // Show a loading toast
    showToast('Starting bot...', 'info');
    
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
            showToast('Bot started successfully', 'success');
            
            // Important: Reset the button text immediately for successful start
            startBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Bot';
        } else {
            showToast(`Failed to start bot: ${data.message || 'Unknown error'}`, 'error');
            
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
        showToast(`Error starting bot: ${error.message}`, 'error');
        
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
        // Only check status, let the bot_status endpoint handle button states
        setTimeout(() => {
            checkBotStatus();
        }, 3000);  // Small delay to let the bot status update
    });
}

function stopBot() {
    if (confirm('Are you sure you want to stop the bot?')) {
        // Disable buttons during operation
        document.getElementById('startBotBtn').disabled = true;
        document.getElementById('stopBotBtn').disabled = true;
        
        // Show a loading toast
        showToast('Stopping bot...', 'info');
        
        fetch('/stop_bot', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Bot stopped successfully', 'success');
            } else {
                showToast(`Failed to stop bot: ${data.message}`, 'error');
            }
            
            // Update status immediately
            checkBotStatus();
        })
        .catch(error => {
            console.error('Error stopping bot:', error);
            showToast('Error stopping bot', 'error');
            
            // Restore button states based on last known status
            document.getElementById('startBotBtn').disabled = false;
            document.getElementById('stopBotBtn').disabled = false;
        });
    }
}

// Enhanced channel loading function with better error handling
function loadChannels() {
    console.log('Loading channels...');
    
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
    
    // Use the correct endpoint - the URL was incorrect!
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
            
            if (!data || data.length === 0) {
                if (channelList) {
                    channelList.innerHTML = '<tr><td colspan="6" class="text-center">No channels configured</td></tr>';
                }
                return;
            }
            
            // We have data, clear loading state
            if (channelList) {
                channelList.innerHTML = '';
                
                // Process each channel for table view
                data.forEach(channel => {
                    const row = document.createElement('tr');
                    
                    // Create cells with correct property names from the API
                    const nameCell = document.createElement('td');
                    nameCell.innerHTML = `<a href="https://twitch.tv/${channel.name}" target="_blank">${channel.name}</a>`;
                    
                    const statusCell = document.createElement('td');
                    statusCell.innerHTML = `<span class="badge ${channel.currently_connected ? 'bg-success' : 'bg-danger'}">${channel.currently_connected ? 'Connected' : 'Disconnected'}</span>`;
                    
                    const ttsCell = document.createElement('td');
                    ttsCell.innerHTML = `<span class="badge ${channel.tts_enabled ? 'bg-success' : 'bg-secondary'}">${channel.tts_enabled ? 'Enabled' : 'Disabled'}</span>`;
                    
                    // Add cells for messages and last activity (if available)
                    const messagesCell = document.createElement('td');
                    messagesCell.textContent = channel.messages_sent || '0';
                    
                    const activityCell = document.createElement('td');
                    activityCell.textContent = channel.last_activity || 'N/A';
                    
                    // Add action buttons
                    const actionsCell = document.createElement('td');
                    actionsCell.innerHTML = `
                        <button class="btn btn-sm btn-outline-primary me-1" onclick="joinChannel('${channel.name}')">
                            <i class="fas fa-sign-in-alt me-1"></i>Join
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="leaveChannel('${channel.name}')">
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
            }
        })
        .catch(error => {
            console.error('Error loading channels:', error);
            
            if (channelList) {
                channelList.innerHTML = `
                    <tr><td colspan="6" class="text-center text-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error loading channels: ${error.message}
                        <button class="btn btn-sm btn-primary ms-3" onclick="loadChannels()">
                            <i class="fas fa-redo me-1"></i>Retry
                        </button>
                    </td></tr>
                `;
            }
            
            // Try to fetch debug information
            fetch('/debug/channels')
                .then(response => response.json())
                .then(debug => {
                    console.log('Channel debug info:', debug);
                })
                .catch(debugError => {
                    console.error('Error fetching debug info:', debugError);
                });
        });
}

// Call this when the document loads
document.addEventListener('DOMContentLoaded', function() {
    const channelList = document.getElementById('channelsTableBody');
    if (channelList) {
        loadChannels();
    }
});

// Add this function to check for existing instances
function checkForExistingBotInstance() {
    fetch('/check_existing_instance')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Found existing bot instance:', data);
                // Update UI to show bot is already running
                showToast(`Bot is already running (PID: ${data.pid})`, 'info');
                // Trigger status check to update buttons
                checkBotStatus();
            }
        })
        .catch(error => {
            console.error('Error checking for existing instances:', error);
        });
} 