// Channel-specific page functionality
document.addEventListener('DOMContentLoaded', function() {
    const channelName = window.channelData?.name;
    
    if (!channelName) {
        console.error('Channel name not found in window.channelData');
        return;
    }
    
    console.log(`[Channel Page] Initializing for channel: ${channelName}`);
    
    // DOM Elements
    const elements = {
        // Stats
        totalMessagesCount: document.getElementById('totalMessagesCount'),
        ttsCount: document.getElementById('ttsCount'),
        botResponses: document.getElementById('botResponses'),
        todayMessages: document.getElementById('todayMessages'),
        
        // Controls
        ttsToggle: document.getElementById('ttsToggle'),
        voiceToggle: document.getElementById('voiceToggle'),
        generateBtn: document.getElementById('generateBtn'),
        generateSendBtn: document.getElementById('generateSendBtn'),
        sendGeneratedBtn: document.getElementById('sendGeneratedBtn'),
        regenerateBtn: document.getElementById('regenerateBtn'),
        
        // TTS
        ttsSection: document.getElementById('ttsSection'),
        customTtsText: document.getElementById('customTtsText'),
        charCount: document.getElementById('charCount'),
        generateTtsBtn: document.getElementById('generateTtsBtn'),
        
        // Message display
        generatedMessage: document.getElementById('generatedMessage'),
        messageText: document.getElementById('messageText'),
        
        // Activity
        activityLoading: document.getElementById('activityLoading'),
        activityList: document.getElementById('activityList'),
        activityTableBody: document.getElementById('activityTableBody'),
        activityEmpty: document.getElementById('activityEmpty'),
        refreshActivityBtn: document.getElementById('refreshActivityBtn'),
        lastUpdated: document.getElementById('lastUpdated'),
        
        // Model
        modelInfo: document.getElementById('modelInfo'),
        rebuildModelBtn: document.getElementById('rebuildModelBtn'),
        
        // Audio
        audioPlayer: document.getElementById('channelAudioPlayer'),
        
        // Chat Stream
        chatMessagesContainer: document.getElementById('chatMessagesContainer'),
        chatMessagesLoading: document.getElementById('chatMessagesLoading'),
        chatMessagesList: document.getElementById('chatMessagesList'),
        chatMessagesEmpty: document.getElementById('chatMessagesEmpty'),
        chatStreamToggle: document.getElementById('chatStreamToggle'),
        clearChatBtn: document.getElementById('clearChatBtn'),
        chatMessageCount: document.getElementById('chatMessageCount'),
        chatStreamStatus: document.getElementById('chatStreamStatus'),
        
        // TTS History
        ttsHistoryLoading: document.getElementById('ttsHistoryLoading'),
        ttsHistoryList: document.getElementById('ttsHistoryList'),
        ttsHistoryEmpty: document.getElementById('ttsHistoryEmpty'),
        ttsVoiceFilter: document.getElementById('ttsVoiceFilter'),
        clearTtsHistoryBtn: document.getElementById('clearTtsHistoryBtn'),
        ttsHistoryCount: document.getElementById('ttsHistoryCount'),
        currentlyPlaying: document.getElementById('currentlyPlaying'),
        ttsAudioPlayer: document.getElementById('ttsAudioPlayer'),
        
        // Connection Status
        channelConnectionStatus: document.getElementById('channelConnectionStatus'),
        
        // Quick Settings
        linesBetweenInput: document.getElementById('linesBetweenInput'),
        updateLinesBtn: document.getElementById('updateLinesBtn'),
        timeBetweenInput: document.getElementById('timeBetweenInput'),
        updateTimeBtn: document.getElementById('updateTimeBtn')
    };
    
    // State
    let currentMessage = null;
    let lastActivity = [];
    let currentFilter = 'all';
    let chatMessages = [];
    let lastMessageId = 0;
    let autoScroll = true;
    let ttsHistory = [];
    let currentlyPlayingId = null;
    let selectedVoiceFilter = '';
    
    // Initialize
    init();
    
    function init() {
        setupEventListeners();
        loadChannelStats();
        loadChannelActivity();
        loadChatMessages();
        loadTtsHistory();
        startAutoRefresh();
        
        // Update character count for TTS
        if (elements.customTtsText) {
            updateCharCount();
        }
    }
    
    function setupEventListeners() {
        // Toggle switches
        if (elements.ttsToggle) {
            elements.ttsToggle.addEventListener('change', handleTtsToggle);
        }
        
        if (elements.voiceToggle) {
            elements.voiceToggle.addEventListener('change', handleVoiceToggle);
        }
        
        // Message generation buttons
        if (elements.generateBtn) {
            elements.generateBtn.addEventListener('click', () => generateMessage(false));
        }
        
        if (elements.generateSendBtn) {
            elements.generateSendBtn.addEventListener('click', () => generateMessage(true));
        }
        
        if (elements.sendGeneratedBtn) {
            elements.sendGeneratedBtn.addEventListener('click', sendCurrentMessage);
        }
        
        if (elements.regenerateBtn) {
            elements.regenerateBtn.addEventListener('click', () => generateMessage(false));
        }
        
        // TTS
        if (elements.customTtsText) {
            elements.customTtsText.addEventListener('input', updateCharCount);
        }
        
        if (elements.generateTtsBtn) {
            elements.generateTtsBtn.addEventListener('click', generateTTS);
        }
        
        // Activity
        if (elements.refreshActivityBtn) {
            elements.refreshActivityBtn.addEventListener('click', loadChannelActivity);
        }
        
        // Activity filters
        const filterRadios = document.querySelectorAll('input[name="activityFilter"]');
        filterRadios.forEach(radio => {
            radio.addEventListener('change', handleFilterChange);
        });
        
        // Model rebuild
        if (elements.rebuildModelBtn) {
            elements.rebuildModelBtn.addEventListener('click', rebuildModel);
        }
        
        // Chat stream controls
        if (elements.chatStreamToggle) {
            elements.chatStreamToggle.addEventListener('change', handleChatStreamToggle);
        }
        
        if (elements.clearChatBtn) {
            elements.clearChatBtn.addEventListener('click', clearChatMessages);
        }
        
        // TTS history controls
        if (elements.ttsVoiceFilter) {
            elements.ttsVoiceFilter.addEventListener('change', handleVoiceFilterChange);
        }
        
        if (elements.clearTtsHistoryBtn) {
            elements.clearTtsHistoryBtn.addEventListener('click', clearTtsHistory);
        }
        
        if (elements.ttsAudioPlayer) {
            elements.ttsAudioPlayer.addEventListener('ended', handleAudioEnded);
            elements.ttsAudioPlayer.addEventListener('play', handleAudioPlay);
            elements.ttsAudioPlayer.addEventListener('pause', handleAudioPause);
        }
        
        // Quick settings controls
        if (elements.updateLinesBtn) {
            elements.updateLinesBtn.addEventListener('click', updateLinesBetween);
        }
        
        if (elements.updateTimeBtn) {
            elements.updateTimeBtn.addEventListener('click', updateTimeBetween);
        }
    }
    
    // API Functions
    async function loadChannelStats() {
        try {
            const response = await fetch(`/api/channel/${channelName}/stats`);
            const data = await response.json();
            
            if (response.ok) {
                updateStatsDisplay(data);
                updateModelInfo(data.model_info);
                updateConnectionStatus(data.config);
            } else {
                console.error('Failed to load channel stats:', data.error);
            }
        } catch (error) {
            console.error('Error loading channel stats:', error);
        }
    }
    
    async function loadChannelActivity() {
        if (!elements.activityLoading || !elements.activityList) return;
        
        elements.activityLoading.style.display = 'block';
        elements.activityList.style.display = 'none';
        elements.activityEmpty.style.display = 'none';
        
        try {
            const response = await fetch(`/api/channel/${channelName}/activity?limit=30`);
            const data = await response.json();
            
            if (response.ok) {
                lastActivity = data.activity || [];
                updateActivityDisplay();
                updateLastUpdated();
            } else {
                console.error('Failed to load channel activity:', data.error);
                showActivityError();
            }
        } catch (error) {
            console.error('Error loading channel activity:', error);
            showActivityError();
        } finally {
            elements.activityLoading.style.display = 'none';
        }
    }
    
    async function generateMessage(sendToChat = false) {
        const button = sendToChat ? elements.generateSendBtn : elements.generateBtn;
        if (!button) return;
        
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating...';
        
        try {
            const response = await fetch(`/api/channel/${channelName}/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    send_to_chat: sendToChat
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.message) {
                currentMessage = data.message;
                
                if (sendToChat && data.sent_to_chat) {
                    showNotification(`Message sent to #${channelName}!`, 'success');
                    // Refresh activity to show the new message
                    setTimeout(() => loadChannelActivity(), 1000);
                } else {
                    displayGeneratedMessage(data.message);
                    showNotification('Message generated successfully!', 'success');
                }
            } else {
                showNotification(data.error || 'Failed to generate message', 'error');
            }
        } catch (error) {
            console.error('Error generating message:', error);
            showNotification('Error generating message', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    async function sendCurrentMessage() {
        if (!currentMessage) return;
        
        const button = elements.sendGeneratedBtn;
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Sending...';
        
        try {
            const response = await fetch(`/send_markov_message/${channelName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    verify_running: true,
                    custom_message: currentMessage
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showNotification(`Message sent to #${channelName}!`, 'success');
                hideGeneratedMessage();
                setTimeout(() => loadChannelActivity(), 1000);
            } else {
                showNotification(data.error || 'Failed to send message', 'error');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            showNotification('Error sending message', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    async function generateTTS() {
        const text = elements.customTtsText?.value?.trim();
        if (!text) {
            showNotification('Please enter text for TTS generation', 'warning');
            return;
        }
        
        const button = elements.generateTtsBtn;
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating...';
        
        try {
            const response = await fetch(`/api/channel/${channelName}/tts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showNotification('TTS generated successfully!', 'success');
                
                // Play the audio if available
                if (data.file_path && elements.audioPlayer) {
                    const audioUrl = `/static/${data.file_path}`;
                    elements.audioPlayer.src = audioUrl;
                    elements.audioPlayer.play().catch(e => {
                        console.warn('Autoplay prevented:', e);
                    });
                }
                
                // Clear the text
                elements.customTtsText.value = '';
                updateCharCount();
                
                // Refresh activity
                setTimeout(() => loadChannelActivity(), 1000);
            } else {
                showNotification(data.error || 'Failed to generate TTS', 'error');
            }
        } catch (error) {
            console.error('Error generating TTS:', error);
            showNotification('Error generating TTS', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    async function handleTtsToggle() {
        const enabled = elements.ttsToggle.checked;
        
        try {
            const response = await fetch(`/api/channel/${channelName}/toggle-tts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    enable_tts: enabled
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                elements.ttsSection.style.display = enabled ? 'block' : 'none';
                showNotification(`TTS ${enabled ? 'enabled' : 'disabled'} for #${channelName}`, 'success');
                // Refresh stats to update toggle states
                setTimeout(() => loadChannelStats(), 1000);
            } else {
                // Revert toggle on error
                elements.ttsToggle.checked = !enabled;
                showNotification(data.error || 'Failed to toggle TTS', 'error');
            }
        } catch (error) {
            // Revert toggle on error
            elements.ttsToggle.checked = !enabled;
            console.error('Error toggling TTS:', error);
            showNotification('Error toggling TTS', 'error');
        }
    }
    
    async function handleVoiceToggle() {
        const enabled = elements.voiceToggle.checked;
        
        try {
            const response = await fetch(`/api/channel/${channelName}/toggle-join`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    join_channel: enabled
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showNotification(`Auto-reply ${enabled ? 'enabled' : 'disabled'} for #${channelName}`, 'success');
                // Refresh stats to update connection status
                setTimeout(() => loadChannelStats(), 1000);
            } else {
                // Revert toggle on error
                elements.voiceToggle.checked = !enabled;
                showNotification(data.error || 'Failed to toggle auto-reply', 'error');
            }
        } catch (error) {
            // Revert toggle on error
            elements.voiceToggle.checked = !enabled;
            console.error('Error toggling voice:', error);
            showNotification('Error toggling auto-reply', 'error');
        }
    }
    
    async function rebuildModel() {
        const button = elements.rebuildModelBtn;
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Rebuilding...';
        
        try {
            const response = await fetch(`/rebuild-cache/${channelName}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                showNotification(`Model rebuilt for #${channelName}`, 'success');
                // Refresh stats to show updated model info
                setTimeout(() => loadChannelStats(), 2000);
            } else {
                showNotification('Failed to rebuild model', 'error');
            }
        } catch (error) {
            console.error('Error rebuilding model:', error);
            showNotification('Error rebuilding model', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    // UI Update Functions
    function updateStatsDisplay(data) {
        if (elements.totalMessagesCount) {
            elements.totalMessagesCount.textContent = data.total_messages?.toLocaleString() || '0';
        }
        if (elements.ttsCount) {
            elements.ttsCount.textContent = data.tts_count?.toLocaleString() || '0';
        }
        if (elements.botResponses) {
            elements.botResponses.textContent = data.bot_responses?.toLocaleString() || '0';
        }
        if (elements.todayMessages) {
            elements.todayMessages.textContent = data.today_messages?.toLocaleString() || '0';
        }
    }
    
    function updateModelInfo(modelInfo) {
        if (!elements.modelInfo) return;
        
        if (modelInfo) {
            elements.modelInfo.innerHTML = `
                <table class="table table-sm">
                    <tr>
                        <td><strong>Model Name:</strong></td>
                        <td><code>${modelInfo.name || 'Unknown'}</code></td>
                    </tr>
                    <tr>
                        <td><strong>Lines Processed:</strong></td>
                        <td>${(modelInfo.line_count || 0).toLocaleString()}</td>
                    </tr>
                    <tr>
                        <td><strong>File Size:</strong></td>
                        <td>${modelInfo.cache_size_str || 'Unknown'}</td>
                    </tr>
                    <tr>
                        <td><strong>Last Updated:</strong></td>
                        <td>${modelInfo.last_modified ? new Date(modelInfo.last_modified * 1000).toLocaleString() : 'Unknown'}</td>
                    </tr>
                </table>
            `;
        } else {
            elements.modelInfo.innerHTML = `
                <div class="text-center py-3 text-muted">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>No model information available</p>
                    <small>Try rebuilding the model to generate statistics</small>
                </div>
            `;
        }
    }
    
    function updateConnectionStatus(config) {
        if (!elements.channelConnectionStatus) return;
        
        // Check if bot is running and if this channel is configured to join
        const shouldBeConnected = config && config.join_channel;
        
        // Get actual connection status from bot status API
        fetch('/api/bot-status')
            .then(response => response.json())
            .then(botStatus => {
                let isActuallyConnected = false;
                
                if (botStatus.running && botStatus.joined_channels) {
                    const cleanChannelName = channelName.toLowerCase();
                    isActuallyConnected = botStatus.joined_channels.some(ch => 
                        ch.toLowerCase().replace('#', '') === cleanChannelName
                    );
                }
                
                // Update the UI based on actual connection status
                updateConnectionDisplay(isActuallyConnected, shouldBeConnected);
            })
            .catch(error => {
                console.error('Error checking bot status:', error);
                updateConnectionDisplay(false, shouldBeConnected);
            });
    }
    
    function updateConnectionDisplay(isConnected, shouldBeConnected) {
        if (!elements.channelConnectionStatus) return;
        
        let statusClass, statusText;
        
        if (isConnected) {
            statusClass = 'connected';
            statusText = 'Connected';
        } else if (shouldBeConnected) {
            statusClass = 'connecting';
            statusText = 'Connecting...';
        } else {
            statusClass = 'disconnected';
            statusText = 'Disconnected';
        }
        
        elements.channelConnectionStatus.className = `connection-status ${statusClass}`;
        elements.channelConnectionStatus.innerHTML = `
            <span class="connection-dot"></span>
            <span class="fw-medium">${statusText}</span>
        `;
    }
    
    function updateActivityDisplay() {
        if (!elements.activityTableBody) return;
        
        const filteredActivity = filterActivity(lastActivity);
        
        if (filteredActivity.length === 0) {
            elements.activityList.style.display = 'none';
            elements.activityEmpty.style.display = 'block';
            return;
        }
        
        elements.activityEmpty.style.display = 'none';
        elements.activityList.style.display = 'block';
        
        elements.activityTableBody.innerHTML = filteredActivity.map(item => createActivityTableRow(item)).join('');
        
        // Add click handlers for TTS playback
        elements.activityTableBody.querySelectorAll('.tts-play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filePath = e.target.closest('.tts-play-btn').dataset.filePath;
                playTtsAudio(filePath);
            });
        });
    }
    
    function createActivityTableRow(item) {
        const timestamp = new Date(item.timestamp).toLocaleTimeString();
        
        if (item.type === 'message') {
            return `
                <tr data-type="message">
                    <td>
                        <span class="badge bg-primary">
                            <i class="fas fa-comment me-1"></i>
                            Chat
                        </span>
                    </td>
                    <td><strong>${escapeHtml(item.username)}</strong></td>
                    <td>${escapeHtml(item.message.length > 60 ? item.message.substring(0, 60) + '...' : item.message)}</td>
                    <td><small>${timestamp}</small></td>
                    <td></td>
                </tr>
            `;
        } else if (item.type === 'tts') {
            return `
                <tr data-type="tts">
                    <td>
                        <span class="badge bg-success">
                            <i class="fas fa-volume-up me-1"></i>
                            TTS
                        </span>
                    </td>
                    <td>
                        <span class="text-muted">System</span>
                        ${item.voice_preset ? `<br><small class="text-muted">${item.voice_preset}</small>` : ''}
                    </td>
                    <td>${escapeHtml(item.message.length > 60 ? item.message.substring(0, 60) + '...' : item.message)}</td>
                    <td><small>${timestamp}</small></td>
                    <td>
                        ${item.file_path ? `
                            <button class="btn btn-sm btn-outline-success tts-play-btn action-btn" data-file-path="${item.file_path}" title="Play TTS">
                                <i class="fas fa-play"></i>
                            </button>
                        ` : ''}
                    </td>
                </tr>
            `;
        }
        
        return '';
    }
    
    function filterActivity(activity) {
        if (currentFilter === 'all') return activity;
        return activity.filter(item => item.type === currentFilter.replace('filter', '').toLowerCase());
    }
    
    function handleFilterChange(e) {
        currentFilter = e.target.id;
        updateActivityDisplay();
    }
    
    function displayGeneratedMessage(message) {
        if (elements.generatedMessage && elements.messageText) {
            elements.messageText.textContent = message;
            elements.generatedMessage.classList.remove('d-none');
        }
    }
    
    function hideGeneratedMessage() {
        if (elements.generatedMessage) {
            elements.generatedMessage.classList.add('d-none');
        }
        currentMessage = null;
    }
    
    function updateCharCount() {
        if (elements.customTtsText && elements.charCount) {
            const count = elements.customTtsText.value.length;
            elements.charCount.textContent = `${count}/500`;
            
            if (count > 450) {
                elements.charCount.classList.add('text-warning');
            } else if (count > 500) {
                elements.charCount.classList.remove('text-warning');
                elements.charCount.classList.add('text-danger');
            } else {
                elements.charCount.classList.remove('text-warning', 'text-danger');
            }
        }
    }
    
    function updateLastUpdated() {
        if (elements.lastUpdated) {
            elements.lastUpdated.textContent = new Date().toLocaleTimeString();
        }
    }
    
    function showActivityError() {
        if (elements.activityList) {
            elements.activityList.style.display = 'block';
            elements.activityList.innerHTML = `
                <div class="list-group-item text-center text-danger">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>Failed to load activity</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="loadChannelActivity()">
                        <i class="fas fa-sync-alt me-1"></i>
                        Retry
                    </button>
                </div>
            `;
        }
    }
    
    function playTtsAudio(filePath) {
        if (elements.audioPlayer && filePath) {
            const audioUrl = `/static/${filePath}`;
            elements.audioPlayer.src = audioUrl;
            elements.audioPlayer.play().catch(e => {
                console.warn('Audio playback failed:', e);
                showNotification('Audio playback failed', 'warning');
            });
        }
    }
    
    function startAutoRefresh() {
        // Refresh stats every 30 seconds
        setInterval(() => {
            loadChannelStats();
        }, 30000);
        
        // Refresh activity every 15 seconds
        setInterval(() => {
            loadChannelActivity();
        }, 15000);
        
        // Refresh chat messages every 5 seconds
        setInterval(() => {
            loadChatMessages();
        }, 5000);
        
        // Refresh TTS history every 10 seconds
        setInterval(() => {
            loadTtsHistory();
        }, 10000);
    }
    
    // Chat Stream Functions
    async function loadChatMessages() {
        try {
            const response = await fetch(`/api/chat-logs?channel=${encodeURIComponent(channelName)}&per_page=50&page=1`);
            const data = await response.json();
            
            if (response.ok && data.logs) {
                const newMessages = data.logs.filter(msg => !msg.is_bot_response);
                updateChatDisplay(newMessages);
                updateChatStatus('connected');
            } else {
                console.error('Failed to load chat messages:', data.error);
                updateChatStatus('disconnected');
            }
        } catch (error) {
            console.error('Error loading chat messages:', error);
            updateChatStatus('disconnected');
        }
    }
    
    function updateChatDisplay(messages) {
        if (!elements.chatMessagesList) return;
        
        // Show loading state initially if this is the first load
        if (chatMessages.length === 0) {
            elements.chatMessagesLoading.style.display = 'none';
            elements.chatMessagesList.style.display = 'block';
        }
        
        // Check for new messages
        const newMessageIds = messages.map(msg => msg.id);
        const existingIds = chatMessages.map(msg => msg.id);
        const hasNewMessages = newMessageIds.some(id => !existingIds.includes(id));
        
        if (hasNewMessages) {
            chatMessages = messages.slice(); // Create a copy
            renderChatMessages();
            
            if (autoScroll) {
                scrollChatToBottom();
            }
        }
        
        // Update count
        if (elements.chatMessageCount) {
            elements.chatMessageCount.textContent = chatMessages.length;
        }
        
        // Show empty state if no messages
        if (chatMessages.length === 0) {
            elements.chatMessagesList.style.display = 'none';
            elements.chatMessagesEmpty.style.display = 'block';
        } else {
            elements.chatMessagesEmpty.style.display = 'none';
        }
    }
    
    function renderChatMessages() {
        if (!elements.chatMessagesList) return;
        
        const chatContainer = elements.chatMessagesList;
        chatContainer.innerHTML = '';
        
        // Reverse to show newest first, but we'll scroll to bottom
        const sortedMessages = [...chatMessages].reverse();
        
        sortedMessages.forEach(message => {
            const messageElement = createChatMessageElement(message);
            chatContainer.appendChild(messageElement);
        });
    }
    
    function createChatMessageElement(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        messageDiv.dataset.messageId = message.id;
        
        // Add special classes for different message types
        if (message.username && message.username.toLowerCase() === 'ansvbot') {
            messageDiv.classList.add('bot-message');
        }
        
        const timestamp = new Date(message.timestamp).toLocaleTimeString();
        const username = message.username || 'Anonymous';
        const avatarLetter = username.charAt(0).toUpperCase();
        
        messageDiv.innerHTML = `
            <div class="chat-message-avatar">${avatarLetter}</div>
            <div class="chat-message-content">
                <div class="chat-message-header">
                    <span class="chat-message-username">${escapeHtml(username)}</span>
                    <span class="chat-message-timestamp">${timestamp}</span>
                </div>
                <p class="chat-message-text">${escapeHtml(message.message)}</p>
            </div>
        `;
        
        return messageDiv;
    }
    
    function handleChatStreamToggle() {
        autoScroll = elements.chatStreamToggle.checked;
        if (autoScroll) {
            scrollChatToBottom();
        }
    }
    
    function clearChatMessages() {
        chatMessages = [];
        if (elements.chatMessagesList) {
            elements.chatMessagesList.innerHTML = '';
        }
        if (elements.chatMessageCount) {
            elements.chatMessageCount.textContent = '0';
        }
        showNotification('Chat messages cleared', 'info');
    }
    
    function scrollChatToBottom() {
        if (elements.chatMessagesContainer) {
            elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
        }
    }
    
    function updateChatStatus(status) {
        if (!elements.chatStreamStatus) return;
        
        elements.chatStreamStatus.className = `connection-status ${status}`;
        
        const statusText = {
            'connected': 'Connected',
            'disconnected': 'Disconnected', 
            'connecting': 'Connecting...'
        };
        
        elements.chatStreamStatus.innerHTML = `
            <span class="connection-dot"></span>
            ${statusText[status] || 'Unknown'}
        `;
    }
    
    // TTS History Functions
    async function loadTtsHistory() {
        try {
            const response = await fetch(`/api/tts-logs?channel_filter=${encodeURIComponent(channelName)}&per_page=20&page=1&sort_by=timestamp&sort_order=desc`);
            const data = await response.json();
            
            if (response.ok && data.logs) {
                updateTtsHistoryDisplay(data.logs);
            } else {
                console.error('Failed to load TTS history:', data.error);
            }
        } catch (error) {
            console.error('Error loading TTS history:', error);
        }
    }
    
    function updateTtsHistoryDisplay(logs) {
        if (!elements.ttsHistoryList) return;
        
        // Show loading state initially if this is the first load
        if (ttsHistory.length === 0) {
            elements.ttsHistoryLoading.style.display = 'none';
            elements.ttsHistoryList.style.display = 'block';
        }
        
        ttsHistory = logs.slice(); // Create a copy
        updateVoiceFilter();
        renderTtsHistory();
        
        // Update count
        if (elements.ttsHistoryCount) {
            elements.ttsHistoryCount.textContent = ttsHistory.length;
        }
        
        // Show empty state if no TTS history
        if (ttsHistory.length === 0) {
            elements.ttsHistoryList.style.display = 'none';
            elements.ttsHistoryEmpty.style.display = 'block';
        } else {
            elements.ttsHistoryEmpty.style.display = 'none';
        }
    }
    
    function updateVoiceFilter() {
        if (!elements.ttsVoiceFilter) return;
        
        // Get unique voice presets
        const voices = [...new Set(ttsHistory.map(item => item.voice_preset).filter(Boolean))];
        
        // Update voice filter dropdown
        const currentValue = elements.ttsVoiceFilter.value;
        elements.ttsVoiceFilter.innerHTML = '<option value="">All Voices</option>';
        
        voices.forEach(voice => {
            const option = document.createElement('option');
            option.value = voice;
            option.textContent = voice;
            if (voice === currentValue) {
                option.selected = true;
            }
            elements.ttsVoiceFilter.appendChild(option);
        });
    }
    
    function renderTtsHistory() {
        if (!elements.ttsHistoryList) return;
        
        // Filter by voice if selected
        let filteredHistory = ttsHistory;
        if (selectedVoiceFilter) {
            filteredHistory = ttsHistory.filter(item => item.voice_preset === selectedVoiceFilter);
        }
        
        elements.ttsHistoryList.innerHTML = '';
        
        filteredHistory.forEach(item => {
            const historyElement = createTtsHistoryElement(item);
            elements.ttsHistoryList.appendChild(historyElement);
        });
    }
    
    function createTtsHistoryElement(item) {
        const historyDiv = document.createElement('div');
        historyDiv.className = 'tts-history-item';
        historyDiv.dataset.ttsId = item.id;
        
        if (currentlyPlayingId === item.id) {
            historyDiv.classList.add('playing');
        }
        
        const timestamp = new Date(item.timestamp).toLocaleString();
        const voicePreset = item.voice_preset || 'Unknown';
        const isPlaying = currentlyPlayingId === item.id;
        
        historyDiv.innerHTML = `
            <div class="tts-history-content">
                <div class="tts-history-header">
                    <span class="tts-voice-badge">${escapeHtml(voicePreset)}</span>
                    <span class="tts-history-timestamp">${timestamp}</span>
                </div>
                <p class="tts-history-text">${escapeHtml(item.message)}</p>
            </div>
            <div class="tts-history-controls">
                <button class="tts-play-button ${isPlaying ? 'playing' : ''}" data-file-path="${item.file_path}" data-tts-id="${item.id}" title="${isPlaying ? 'Pause' : 'Play'} TTS">
                    <i class="fas ${isPlaying ? 'fa-pause' : 'fa-play'}"></i>
                </button>
            </div>
        `;
        
        // Add click handler for play button
        const playButton = historyDiv.querySelector('.tts-play-button');
        if (playButton) {
            playButton.addEventListener('click', (e) => {
                e.preventDefault();
                const ttsId = parseInt(playButton.dataset.ttsId);
                const filePath = playButton.dataset.filePath;
                toggleTtsPlayback(ttsId, filePath);
            });
        }
        
        return historyDiv;
    }
    
    function toggleTtsPlayback(ttsId, filePath) {
        if (!elements.ttsAudioPlayer || !filePath) return;
        
        // If this TTS is currently playing, pause it
        if (currentlyPlayingId === ttsId && !elements.ttsAudioPlayer.paused) {
            elements.ttsAudioPlayer.pause();
            return;
        }
        
        // Otherwise, play this TTS
        const audioUrl = `/static/${filePath}`;
        elements.ttsAudioPlayer.src = audioUrl;
        currentlyPlayingId = ttsId;
        
        elements.ttsAudioPlayer.play().then(() => {
            updateCurrentlyPlaying(ttsId);
            updatePlayingStates();
        }).catch(e => {
            console.warn('TTS playback failed:', e);
            showNotification('TTS playback failed', 'warning');
            currentlyPlayingId = null;
            updateCurrentlyPlaying(null);
            updatePlayingStates();
        });
    }
    
    function updateCurrentlyPlaying(ttsId) {
        if (!elements.currentlyPlaying) return;
        
        if (ttsId) {
            const ttsItem = ttsHistory.find(item => item.id === ttsId);
            if (ttsItem) {
                const truncatedMessage = ttsItem.message.length > 30 
                    ? ttsItem.message.substring(0, 30) + '...' 
                    : ttsItem.message;
                elements.currentlyPlaying.textContent = truncatedMessage;
            }
        } else {
            elements.currentlyPlaying.textContent = 'None';
        }
    }
    
    function updatePlayingStates() {
        // Update all play buttons and history items
        document.querySelectorAll('.tts-history-item').forEach(item => {
            const ttsId = parseInt(item.dataset.ttsId);
            const playButton = item.querySelector('.tts-play-button');
            const icon = playButton?.querySelector('i');
            
            if (ttsId === currentlyPlayingId) {
                item.classList.add('playing');
                playButton?.classList.add('playing');
                if (icon) {
                    icon.className = 'fas fa-pause';
                }
                playButton?.setAttribute('title', 'Pause TTS');
            } else {
                item.classList.remove('playing');
                playButton?.classList.remove('playing');
                if (icon) {
                    icon.className = 'fas fa-play';
                }
                playButton?.setAttribute('title', 'Play TTS');
            }
        });
    }
    
    function handleVoiceFilterChange(e) {
        selectedVoiceFilter = e.target.value;
        renderTtsHistory();
    }
    
    function clearTtsHistory() {
        if (confirm('Are you sure you want to clear the TTS history display? This will not delete the actual files.')) {
            ttsHistory = [];
            currentlyPlayingId = null;
            elements.ttsAudioPlayer.pause();
            elements.ttsAudioPlayer.src = '';
            updateCurrentlyPlaying(null);
            renderTtsHistory();
            if (elements.ttsHistoryCount) {
                elements.ttsHistoryCount.textContent = '0';
            }
            elements.ttsHistoryList.style.display = 'none';
            elements.ttsHistoryEmpty.style.display = 'block';
            showNotification('TTS history display cleared', 'info');
        }
    }
    
    function handleAudioEnded() {
        currentlyPlayingId = null;
        updateCurrentlyPlaying(null);
        updatePlayingStates();
    }
    
    function handleAudioPlay() {
        updatePlayingStates();
    }
    
    function handleAudioPause() {
        updatePlayingStates();
    }
    
    // Quick Settings Functions
    async function updateLinesBetween() {
        const value = parseInt(elements.linesBetweenInput.value);
        if (isNaN(value) || value < 1 || value > 1000) {
            showNotification('Lines between messages must be between 1 and 1000', 'warning');
            return;
        }
        
        await updateChannelSetting('lines_between_messages', value, elements.updateLinesBtn);
    }
    
    async function updateTimeBetween() {
        const value = parseInt(elements.timeBetweenInput.value);
        if (isNaN(value) || value < 0 || value > 3600) {
            showNotification('Time between messages must be between 0 and 3600 seconds', 'warning');
            return;
        }
        
        await updateChannelSetting('time_between_messages', value, elements.updateTimeBtn);
    }
    
    async function updateChannelSetting(settingName, value, button) {
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        
        try {
            const response = await fetch('/update-channel-settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    channel_name: channelName,
                    [settingName]: value
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification(`${settingName.replace('_', ' ')} updated successfully`, 'success');
                // Refresh stats to show updated settings
                setTimeout(() => loadChannelStats(), 1000);
            } else {
                showNotification(data.message || 'Failed to update setting', 'error');
            }
        } catch (error) {
            console.error('Error updating setting:', error);
            showNotification('Error updating setting', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    // Utility Functions
    function showNotification(message, type = 'info') {
        if (window.notificationSystem && window.notificationSystem.showToast) {
            window.notificationSystem.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Expose functions for debugging
    window.channelPageDebug = {
        loadStats: loadChannelStats,
        loadActivity: loadChannelActivity,
        generateMessage,
        channelName,
        lastActivity
    };
    
    console.log(`[Channel Page] Initialized successfully for #${channelName}`);
});