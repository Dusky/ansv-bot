/**
 * event_listener.js - Centralized event system
 * 
 * This file provides a standardized way for different parts of the application
 * to communicate with each other through events, reducing direct dependencies.
 */

// Initialize socket properly at the top (maintain existing functionality)
const socket = io();

// Create global event bus if it doesn't exist
window.EventBus = window.EventBus || {
    // Event registry
    listeners: {},
    
    // Subscribe to an event
    on: function(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
        
        return {
            // Return an object with unsubscribe method
            unsubscribe: () => {
                this.off(event, callback);
            }
        };
    },
    
    // Unsubscribe from an event
    off: function(event, callback) {
        if (!this.listeners[event]) return;
        
        const index = this.listeners[event].indexOf(callback);
        if (index !== -1) {
            this.listeners[event].splice(index, 1);
        }
    },
    
    // Trigger an event with data
    emit: function(event, data) {
        if (!this.listeners[event]) return;
        
        this.listeners[event].forEach(callback => {
            try {
                callback(data);
            } catch (e) {
                console.error(`Error in event listener for ${event}:`, e);
            }
        });
    },
    
    // Clear all listeners for an event
    clear: function(event) {
        if (event) {
            delete this.listeners[event];
        } else {
            this.listeners = {};
        }
    }
};

// Common events that can be used throughout the application
window.AppEvents = {
    // Bot status events
    BOT_STATUS_CHANGED: 'bot:status-changed',
    BOT_STARTED: 'bot:started',
    BOT_STOPPED: 'bot:stopped',
    BOT_ERROR: 'bot:error',
    
    // Channel events
    CHANNELS_LOADED: 'channels:loaded',
    CHANNEL_JOINED: 'channel:joined',
    CHANNEL_LEFT: 'channel:left',
    CHANNEL_SETTINGS_UPDATED: 'channel:settings-updated',
    CHANNEL_ADDED: 'channel:added',
    CHANNEL_DELETED: 'channel:deleted',
    
    // Message events
    MESSAGE_GENERATED: 'message:generated',
    MESSAGE_SENT: 'message:sent',
    
    // UI events
    THEME_CHANGED: 'ui:theme-changed',
    PAGE_LOADED: 'ui:page-loaded',
    
    // System events
    SYSTEM_ERROR: 'system:error',
    API_ERROR: 'system:api-error',
    
    // TTS events
    TTS_NEW_ENTRY: 'tts:new-entry',
    TTS_PLAYED: 'tts:played'
};

// Helper function for components to use events
function useEvents() {
    return {
        on: window.EventBus.on.bind(window.EventBus),
        off: window.EventBus.off.bind(window.EventBus),
        emit: window.EventBus.emit.bind(window.EventBus),
        events: window.AppEvents
    };
}

// Setup WebSocket connection with event dispatcher
function setupWebSocket() {
    try {
        // Prevent duplicate event listeners by removing existing ones first
        if (socket._eventsCount > 0) {
            console.log("Removing existing socket listeners");
            socket.off("refresh_table");
            socket.off("new_tts_entry");
            socket.off("bot_status_change");
        }
        
        // Listen for refresh_table events
        socket.on("refresh_table", function (data) {
            console.log("Received refresh_table event:", data);
            
            // Call refreshTable in data_handler.js
            if (window.refreshTable) {
                window.refreshTable();
            }
            
            // Emit to event bus for components that use events
            window.EventBus.emit('table:refresh', data);
        });
        
        // Listen for new_tts_entry events
        socket.on("new_tts_entry", function (data) {
            console.log("Received new_tts_entry event:", data);
            
            // Call refreshTable in data_handler.js
            if (window.refreshTable) {
                window.refreshTable();
            }
            
            // Emit to event bus
            window.EventBus.emit(window.AppEvents.TTS_NEW_ENTRY, data);
            
            // Show notification using centralized system
            if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                window.notificationSystem.showToast('New TTS message available', 'info');
            } else if (typeof window.showToast === 'function') {
                window.showToast('New TTS message available', 'info');
            }
        });
        
        // Listen for bot status changes
        socket.on("bot_status_change", function(data) {
            // Update UI with centralized function if available
            if (typeof updateBotStatusUI === 'function') {
                updateBotStatusUI(data.status);
            }
            
            // Emit to event bus for components that use events
            window.EventBus.emit(window.AppEvents.BOT_STATUS_CHANGED, data);
            
            // Also emit specific events for started/stopped
            if (data.status === 'running') {
                window.EventBus.emit(window.AppEvents.BOT_STARTED, data);
            } else {
                window.EventBus.emit(window.AppEvents.BOT_STOPPED, data);
            }
        });
        
        // Mark socket as initialized
        window._socketEventsInitialized = true;
        
        console.log("WebSocket listeners successfully set up");
    } catch (error) {
        console.warn("WebSocket setup error:", error);
        window.EventBus.emit(window.AppEvents.SYSTEM_ERROR, {
            source: 'websocket',
            message: error.message,
            error: error
        });
    }
}

// Main initialization function
function initializeApp() {
    // Check if we've already initialized this page to avoid duplicate setup
    if (window._pageInitialized) {
        console.log("Page already initialized, skipping duplicate initialization");
        return;
    }
    
    // Mark the page as initialized
    window._pageInitialized = true;
    console.log("Initializing page components");
    
    // Check bot status first
    if (typeof checkBotStatus === 'function') {
        checkBotStatus();
    } else if (window.BotStatus && typeof window.BotStatus.checkStatus === 'function') {
        window.BotStatus.checkStatus();
    }
    
    // Populate channel and model selectors for message generation
    const channelForMessage = document.getElementById('channelForMessage');
    if (channelForMessage) {
        if (typeof populateMessageChannels === 'function') {
            populateMessageChannels();
        }
    }
    
    // Also populate the models if modelSelector exists
    const modelSelector = document.getElementById('modelSelector');
    if (modelSelector) {
        if (typeof populateModels === 'function') {
            populateModels();
        }
    }
    
    // Populate channel settings dropdown
    var channelSelect = document.getElementById("channelSelect");
    if (channelSelect) {
        channelSelect.addEventListener("change", function () {
            if (typeof checkForAddChannelOption === 'function') {
                checkForAddChannelOption(this);
            }
        });
        
        // Populate the channels when the settings page loads
        if (typeof fetchChannels === 'function') {
            fetchChannels();
        } else if (window.ChannelManager && typeof window.ChannelManager.loadChannels === 'function') {
            window.ChannelManager.loadChannels();
        }
    }
    
    // Set up button event listeners
    if (typeof setupButtonListeners === 'function') {
        setupButtonListeners();
    }
    
    // Set up theme toggle
    if (typeof setupThemeToggle === 'function') {
        setupThemeToggle();
    } else if (window.ThemeManager && typeof window.ThemeManager.init === 'function') {
        window.ThemeManager.init();
    }
    
    // Set up autoplay toggle
    if (typeof setupAutoplayToggle === 'function') {
        setupAutoplayToggle();
    }
    
    // Set up WebSocket - only if not already set up
    if (!window._socketEventsInitialized) {
        setupWebSocket();
    }
    
    // Load initial data for tables if needed
    if (typeof refreshTable === 'function') {
        refreshTable();
    }
    
    // Add keyboard shortcuts
    if (typeof setupKeyboardShortcuts === 'function') {
        setupKeyboardShortcuts();
    }
    
    // Emit page loaded event for any components listening
    window.EventBus.emit(window.AppEvents.PAGE_LOADED, {
        path: window.location.pathname,
        query: window.location.search,
        hash: window.location.hash
    });
}

// Initialize the app when the DOM content is loaded
document.addEventListener("DOMContentLoaded", initializeApp);

// Expose key functions to global scope for backward compatibility
window.updateBotStatusUI = function(statusData) {
    const botStatusIcon = document.getElementById('botStatusIcon');
    const botStatusIndicator = document.getElementById('botStatusIndicator');
    
    if (botStatusIcon) {
        if (statusData.status === 'running') {
            botStatusIcon.className = 'bi bi-circle-fill text-success';
        } else {
            botStatusIcon.className = 'bi bi-circle-fill text-danger';
        }
    }
    
    if (botStatusIndicator) {
        if (statusData.status === 'running') {
            botStatusIndicator.innerHTML = '<span class="badge bg-success">Running</span>';
        } else {
            botStatusIndicator.innerHTML = '<span class="badge bg-danger">Stopped</span>';
        }
    }
    
    // Also update button states
    if (typeof updateButtonStates === 'function') {
        updateButtonStates(statusData.status === 'running');
    } else if (window.BotStatus && typeof window.BotStatus.updateButtons === 'function') {
        window.BotStatus.running = statusData.status === 'running';
        window.BotStatus.updateButtons();
    }
};

// Legacy compatibility for updateChannelCount
window.updateChannelCount = function() {
    const channelCountElement = document.getElementById('channelCount');
    if (!channelCountElement) return;
    
    fetch("/get-stats")
        .then(response => response.json())
        .then(data => {
            // Count channels but exclude the general model
            const channelCount = data.filter(channel => 
                channel.name !== 'general_markov' && 
                channel.name !== 'General Model'
            ).length;
            
            channelCountElement.textContent = channelCount;
        })
        .catch(error => {
            console.error("Error updating channel count:", error);
            channelCountElement.textContent = "?";
        });
};

// Legacy compatibility for keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(event) {
        // Ctrl+S to save settings
        if (event.ctrlKey && event.key === 's') {
            event.preventDefault();
            const saveSettingsBtn = document.getElementById('saveSettings');
            if (saveSettingsBtn && saveSettingsBtn.offsetParent !== null) {
                saveSettingsBtn.click();
            }
        }
        
        // Ctrl+G to generate message
        if (event.ctrlKey && event.key === 'g') {
            event.preventDefault();
            const generateMsgBtn = document.getElementById('generateMsgBtn');
            if (generateMsgBtn && generateMsgBtn.offsetParent !== null) {
                generateMsgBtn.click();
            }
        }
    });
}

// Setup autoplay toggle with proper backward compatibility
function setupAutoplayToggle() {
    const autoplayElement = document.getElementById("autoplay");
    if (!autoplayElement) return; // Exit if element doesn't exist
    
    const muteIcon = document.getElementById("muteIcon");
    const unmuteIcon = document.getElementById("unmuteIcon");
    if (!muteIcon || !unmuteIcon) return; // Exit if icons don't exist
    
    // Set the UI based on stored preferences
    const isMuted = localStorage.getItem("muteStatus") === "true";
    autoplayElement.checked = !isMuted;
    
    // Update the icons based on the current state
    if (isMuted) {
        muteIcon.classList.remove("d-none");
        unmuteIcon.classList.add("d-none");
    } else {
        muteIcon.classList.add("d-none");
        unmuteIcon.classList.remove("d-none");
    }
    
    // Add listener
    autoplayElement.addEventListener("change", function() {
        const autoplayEnabled = this.checked;
        const isMuted = !autoplayEnabled;
        
        // Update localStorage
        localStorage.setItem("muteStatus", isMuted);
        
        // Update the UI
        if (isMuted) {
            muteIcon.classList.remove("d-none");
            unmuteIcon.classList.add("d-none");
        } else {
            muteIcon.classList.add("d-none");
            unmuteIcon.classList.remove("d-none");
        }
    });
}