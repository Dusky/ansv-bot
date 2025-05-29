/**
 * WebSocket Client for Real-Time Updates
 * Replaces polling with event-driven updates for better performance
 */

class WebSocketClient {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.isConnected = false;
        this.eventHandlers = new Map();
        
        // Initialize connection
        this.connect();
    }
    
    connect() {
        try {
            // Initialize Socket.IO connection
            this.socket = io();
            
            this.setupEventHandlers();
            this.setupConnectionHandlers();
            
            console.log('WebSocket client initialized');
        } catch (error) {
            console.error('Failed to initialize WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    setupConnectionHandlers() {
        this.socket.on('connect', () => {
            console.log('Connected to WebSocket server');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            // Request initial status
            this.socket.emit('request_status');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket server');
            this.isConnected = false;
            this.scheduleReconnect();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            this.isConnected = false;
            this.scheduleReconnect();
        });
    }
    
    setupEventHandlers() {
        // Bot status updates
        this.socket.on('bot_status_update', (data) => {
            this.handleBotStatusUpdate(data);
        });
        
        // Channel updates
        this.socket.on('channel_update', (data) => {
            this.handleChannelUpdate(data);
        });
        
        // New messages
        this.socket.on('new_message', (data) => {
            this.handleNewMessage(data);
        });
        
        // TTS events
        this.socket.on('new_tts_entry', (data) => {
            this.handleNewTTS(data);
        });
        
        // Model rebuild events
        this.socket.on('model_rebuilt', (data) => {
            this.handleModelRebuilt(data);
        });
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached. Falling back to polling.');
            this.fallbackToPolling();
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    }
    
    fallbackToPolling() {
        console.warn('WebSocket failed, falling back to polling mode');
        // Re-enable polling for critical functions
        if (window.BotStatus) {
            window.BotStatus.enablePolling();
        }
    }
    
    // Event Handlers
    handleBotStatusUpdate(data) {
        console.log('Bot status update received:', data);
        
        // Update bot status display
        if (window.BotStatus) {
            window.BotStatus.updateFromWebSocket(data);
        }
        
        // Trigger custom event handlers
        this.triggerCustomHandlers('bot_status_update', data);
    }
    
    handleChannelUpdate(data) {
        console.log('Channel update received:', data);
        
        // Update channel-specific displays
        const channel = data.channel;
        const updateData = data.data;
        
        // Trigger page-specific updates
        if (window.location.pathname.includes(`/channel/${channel}`)) {
            // On channel page - refresh relevant sections
            if (window.loadChannelStats) {
                window.loadChannelStats();
            }
        }
        
        // Update channel lists
        if (window.BotController && typeof window.BotController.loadChannels === 'function') {
            window.BotController.loadChannels();
        }
        
        this.triggerCustomHandlers('channel_update', data);
    }
    
    handleNewMessage(data) {
        console.log('New message received:', data);
        
        // Update real-time chat displays
        const channel = data.channel;
        const message = data.message;
        
        // Update chat on channel pages
        if (window.location.pathname.includes(`/channel/${channel}`)) {
            if (window.addMessageToChat) {
                window.addMessageToChat(message);
            }
        }
        
        this.triggerCustomHandlers('new_message', data);
    }
    
    handleNewTTS(data) {
        console.log('New TTS entry received:', data);
        
        // Update TTS history displays
        if (window.loadTtsHistory) {
            window.loadTtsHistory();
        }
        
        // Show notification
        if (window.notificationSystem) {
            window.notificationSystem.showToast(
                `🔊 TTS generated for ${data.channel}`, 
                'info'
            );
        }
        
        this.triggerCustomHandlers('new_tts_entry', data);
    }
    
    handleModelRebuilt(data) {
        console.log('Model rebuilt:', data);
        
        // Update statistics displays
        if (window.loadStatistics) {
            window.loadStatistics();
        }
        
        // Show success notification
        if (window.notificationSystem) {
            window.notificationSystem.showToast(
                `🧠 Markov model rebuilt for ${data.channel}`, 
                'success'
            );
        }
        
        this.triggerCustomHandlers('model_rebuilt', data);
    }
    
    // Custom Event Handler Management
    on(eventName, handler) {
        if (!this.eventHandlers.has(eventName)) {
            this.eventHandlers.set(eventName, []);
        }
        this.eventHandlers.get(eventName).push(handler);
    }
    
    off(eventName, handler) {
        if (this.eventHandlers.has(eventName)) {
            const handlers = this.eventHandlers.get(eventName);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    triggerCustomHandlers(eventName, data) {
        if (this.eventHandlers.has(eventName)) {
            this.eventHandlers.get(eventName).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in custom event handler for ${eventName}:`, error);
                }
            });
        }
    }
    
    // Channel Subscription Management
    subscribeToChannel(channelName) {
        if (this.isConnected) {
            this.socket.emit('subscribe_channel', { channel: channelName });
            console.log(`Subscribed to channel updates: ${channelName}`);
        }
    }
    
    unsubscribeFromChannel(channelName) {
        if (this.isConnected) {
            this.socket.emit('unsubscribe_channel', { channel: channelName });
            console.log(`Unsubscribed from channel updates: ${channelName}`);
        }
    }
    
    // Manual status request
    requestStatus() {
        if (this.isConnected) {
            this.socket.emit('request_status');
        }
    }
    
    // Connection status
    isWebSocketConnected() {
        return this.isConnected;
    }
}

// Global WebSocket client instance
window.wsClient = new WebSocketClient();

// Initialize WebSocket client when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('WebSocket client ready for real-time updates');
    
    // Subscribe to current channel if on a channel page
    const channelMatch = window.location.pathname.match(/\/channel\/([^\/]+)/);
    if (channelMatch) {
        const channelName = channelMatch[1];
        window.wsClient.subscribeToChannel(channelName);
    }
});

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (window.wsClient && window.wsClient.socket) {
        window.wsClient.socket.disconnect();
    }
});

// Export for use in other modules
window.WebSocketClient = WebSocketClient;