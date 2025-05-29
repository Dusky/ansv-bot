class TTSPopup {
    constructor(channelName) {
        this.channelName = channelName;
        this.autoplayEnabled = true;
        this.isUserInteracted = false;
        this.currentAudio = null;
        this.ttsHistory = [];
        this.maxHistory = 5;
        
        this.initializeElements();
        this.initializeWebSocket();
        this.bindEvents();
        this.loadRecentTTS();
    }
    
    initializeElements() {
        this.audioElement = document.getElementById('ttsAudio');
        this.toggleButton = document.getElementById('toggleAutoplay');
        this.statusMessage = document.getElementById('statusMessage');
        this.currentTTS = document.getElementById('currentTTS');
        this.currentMessage = document.getElementById('currentMessage');
        this.currentTime = document.getElementById('currentTime');
        this.historyContainer = document.getElementById('ttsHistory');
    }
    
    initializeWebSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('TTS Popup connected to WebSocket');
            this.socket.emit('subscribe_channel', this.channelName);
        });
        
        this.socket.on('new_tts_entry', (data) => {
            if (data.channel === this.channelName) {
                this.handleNewTTS(data.id);
            }
        });
        
        this.socket.on('disconnect', () => {
            console.log('TTS Popup disconnected from WebSocket');
        });
    }
    
    bindEvents() {
        // Enable autoplay on any user interaction
        document.addEventListener('click', () => {
            if (!this.isUserInteracted) {
                this.isUserInteracted = true;
                this.hideStatusMessage();
                console.log('User interaction detected, autoplay enabled');
            }
        }, { once: true });
        
        this.toggleButton.addEventListener('click', () => {
            this.toggleAutoplay();
        });
        
        document.getElementById('clearHistory').addEventListener('click', () => {
            this.clearHistory();
        });
        
        this.audioElement.addEventListener('ended', () => {
            this.onAudioEnded();
        });
        
        this.audioElement.addEventListener('error', (e) => {
            console.error('Audio playback error:', e);
            this.onAudioEnded();
        });
        
        // Handle window close
        window.addEventListener('beforeunload', () => {
            if (this.socket) {
                this.socket.disconnect();
            }
        });
    }
    
    async handleNewTTS(ttsId) {
        try {
            const response = await fetch(`/api/tts-logs?id=${ttsId}`);
            const data = await response.json();
            
            if (data.data && data.data.length > 0) {
                const ttsEntry = data.data[0];
                this.addToHistory(ttsEntry);
                
                if (this.autoplayEnabled && this.isUserInteracted) {
                    await this.playTTS(ttsEntry);
                } else if (!this.isUserInteracted) {
                    this.showStatusMessage('Click to enable autoplay');
                }
            }
        } catch (error) {
            console.error('Error fetching TTS entry:', error);
        }
    }
    
    async playTTS(ttsEntry) {
        try {
            this.showCurrentPlaying(ttsEntry);
            
            this.audioElement.src = `/static/${ttsEntry.file_path}`;
            this.audioElement.currentTime = 0;
            
            await this.audioElement.play();
            
        } catch (error) {
            console.error('Failed to play TTS:', error);
            this.onAudioEnded();
            
            if (error.name === 'NotAllowedError') {
                this.showStatusMessage('Click to enable autoplay');
                this.isUserInteracted = false;
            }
        }
    }
    
    showCurrentPlaying(ttsEntry) {
        this.currentMessage.textContent = ttsEntry.message;
        this.currentTime.textContent = this.formatTime(ttsEntry.timestamp);
        this.currentTTS.style.display = 'block';
        
        // Mark entry as currently playing in history
        this.updateHistoryPlayingState(ttsEntry.message_id);
    }
    
    onAudioEnded() {
        this.currentTTS.style.display = 'none';
        this.clearHistoryPlayingState();
    }
    
    addToHistory(ttsEntry) {
        // Add to beginning of array
        this.ttsHistory.unshift(ttsEntry);
        
        // Limit to max history
        if (this.ttsHistory.length > this.maxHistory) {
            this.ttsHistory = this.ttsHistory.slice(0, this.maxHistory);
        }
        
        this.renderHistory();
    }
    
    renderHistory() {
        this.historyContainer.innerHTML = '';
        
        this.ttsHistory.forEach(entry => {
            const entryElement = document.createElement('div');
            entryElement.className = 'tts-entry';
            entryElement.dataset.messageId = entry.message_id;
            
            entryElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <span class="text-truncate flex-grow-1" title="${entry.message}">
                        ${entry.message}
                    </span>
                    <small class="text-muted ms-2">${this.formatTime(entry.timestamp)}</small>
                </div>
            `;
            
            // Make entries clickable to replay
            entryElement.addEventListener('click', () => {
                if (this.isUserInteracted) {
                    this.playTTS(entry);
                }
            });
            
            this.historyContainer.appendChild(entryElement);
        });
    }
    
    updateHistoryPlayingState(messageId) {
        this.clearHistoryPlayingState();
        const entry = this.historyContainer.querySelector(`[data-message-id="${messageId}"]`);
        if (entry) {
            entry.classList.add('playing');
        }
    }
    
    clearHistoryPlayingState() {
        this.historyContainer.querySelectorAll('.playing').forEach(entry => {
            entry.classList.remove('playing');
        });
    }
    
    toggleAutoplay() {
        this.autoplayEnabled = !this.autoplayEnabled;
        
        if (this.autoplayEnabled) {
            this.toggleButton.innerHTML = '<i class="fas fa-volume-up"></i> ON';
            this.toggleButton.className = 'btn btn-success btn-sm';
        } else {
            this.toggleButton.innerHTML = '<i class="fas fa-volume-mute"></i> OFF';
            this.toggleButton.className = 'btn btn-danger btn-sm';
        }
    }
    
    clearHistory() {
        this.ttsHistory = [];
        this.renderHistory();
        this.onAudioEnded();
    }
    
    async loadRecentTTS() {
        try {
            const response = await fetch(`/api/tts-logs?channel=${this.channelName}&limit=5`);
            const data = await response.json();
            
            if (data.data) {
                this.ttsHistory = data.data.reverse(); // Reverse to show newest first
                this.renderHistory();
            }
        } catch (error) {
            console.error('Error loading recent TTS:', error);
        }
    }
    
    showStatusMessage(message) {
        this.statusMessage.textContent = message;
        this.statusMessage.style.display = 'block';
    }
    
    hideStatusMessage() {
        this.statusMessage.style.display = 'none';
    }
    
    formatTime(timestamp) {
        try {
            const date = new Date(timestamp);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (error) {
            return '--:--';
        }
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Extract channel name from URL path
    const pathParts = window.location.pathname.split('/');
    const channelName = pathParts[pathParts.length - 1];
    
    if (channelName) {
        console.log('Initializing TTS Popup for channel:', channelName);
        window.ttsPopup = new TTSPopup(channelName);
    } else {
        console.error('Could not determine channel name from URL');
    }
});