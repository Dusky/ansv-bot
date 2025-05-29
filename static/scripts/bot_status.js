/**
 * bot_status.js - Centralized bot status management
 * 
 * This file provides a single source of truth for bot status across all pages.
 * It should be included before other scripts that need to check bot status.
 */

// Global bot status variable - accessible to all scripts
window.BotStatus = window.BotStatus || {
  // Status flags
  running: false,
  connected: false,
  tts_enabled: false,
  
  // Timestamps
  last_checked: new Date(),
  uptime: null,
  
  // Initialization
  init: function() {
    console.log("BotStatus initializing");
    
    // PERFORMANCE: Use WebSocket by default, fallback to polling
    this.useWebSocket = true;
    this.pollingInterval = null;
    
    // Do initial check
    this.checkStatus();
    
    // Set up WebSocket or polling based on availability
    this.initializeUpdates();
    
    // Listen for events from the EventBus if available
    if (window.EventBus) {
      window.EventBus.on(window.AppEvents?.BOT_STATUS_CHANGED || 'bot:status-changed', data => {
        this.handleStatusUpdate(data);
      });
    }
    
    // Return self for chaining
    return this;
  },
  
  // PERFORMANCE: Initialize WebSocket or polling updates
  initializeUpdates: function() {
    if (this.useWebSocket && window.wsClient) {
      // Use WebSocket for real-time updates
      console.log("BotStatus using WebSocket for real-time updates");
      window.wsClient.on('bot_status_update', (data) => {
        this.updateFromWebSocket(data);
      });
    } else {
      // Fallback to polling
      this.enablePolling();
    }
  },
  
  // Enable polling mode (fallback)
  enablePolling: function() {
    console.log("BotStatus enabling polling mode");
    this.useWebSocket = false;
    
    // Clear any existing interval
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }
    
    // Set up periodic checking with longer intervals to reduce load
    this.pollingInterval = setInterval(() => this.checkStatus(), 15000); // Check every 15 seconds
  },
  
  // Disable polling (when WebSocket is working)
  disablePolling: function() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  },
  
  // Update status from WebSocket event
  updateFromWebSocket: function(data) {
    console.log("BotStatus received WebSocket update:", data);
    
    // Update internal state
    this.running = data.running || false;
    this.connected = data.connected || false;
    this.tts_enabled = data.tts_enabled || false;
    this.last_checked = new Date();
    
    if (data.uptime !== undefined) {
      this.uptime = data.uptime;
    }
    
    // Update UI immediately
    this.updateDisplay();
    
    // Disable polling since WebSocket is working
    this.disablePolling();
  },
  
  // Check bot status from server
  checkStatus: function() {
    // CRITICAL: Don't check bot status repeatedly on settings page to prevent theme refresh loop
    const isSettingsPage = window.location.pathname.includes('settings');
    
    // If on settings page, only check status once and then skip future auto-checks
    if (isSettingsPage && this._settingsPageChecked) {
        console.log("Skipping auto status check on settings page");
        return;
    }
    
    console.log("Checking bot status...");
    
    fetch('/api/bot-status')
      .then(response => {
        if (!response.ok) {
          throw new Error(`Server responded with ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        console.log("Bot status response:", data);
        
        // Check if status has changed
        const statusChanged = 
          this.running !== !!data.running || 
          this.connected !== !!data.connected || 
          this.tts_enabled !== !!data.tts_enabled;
        
        // Update internal state
        this.running = !!data.running;
        this.connected = !!data.connected;
        this.tts_enabled = !!data.tts_enabled;
        this.last_checked = new Date();
        this.uptime = data.uptime || null;
        
        // If on settings page, mark that we've checked once
        if (isSettingsPage) {
            this._settingsPageChecked = true;
        }
        
        // Skip updates on settings page to avoid theme refresh loops
        if (!isSettingsPage) {
            this.updateUI(false);
        }
        
        // Dispatch event for other scripts using DOM events (legacy)
        const event = new CustomEvent('botstatus', { 
          detail: { 
            running: this.running,
            connected: this.connected,
            tts_enabled: this.tts_enabled,
            statusChanged: statusChanged
          }
        });
        window.dispatchEvent(event);
        
        // Also dispatch through EventBus if available (modern)
        if (window.EventBus && window.EventBus.emit) {
          const botStatusEvent = window.AppEvents?.BOT_STATUS_CHANGED || 'bot:status-changed';
          window.EventBus.emit(botStatusEvent, { 
            running: this.running,
            connected: this.connected,
            tts_enabled: this.tts_enabled,
            statusChanged: statusChanged
          });
          
          // Also emit specific events for started/stopped for better component control
          if (this.running) {
            const botStartedEvent = window.AppEvents?.BOT_STARTED || 'bot:started';
            window.EventBus.emit(botStartedEvent, { uptime: this.uptime });
          } else {
            const botStoppedEvent = window.AppEvents?.BOT_STOPPED || 'bot:stopped';
            window.EventBus.emit(botStoppedEvent, {});
          }
        }
      })
      .catch(error => {
        console.error("Error checking bot status:", error);
        
        // Don't change running status on error - keep previous state
        // This prevents flicker when network errors occur
        
        // Still update UI but skip notifications
        this.updateUI(true);
        
        // Emit error event if EventBus is available
        if (window.EventBus && window.EventBus.emit) {
          const errorEvent = window.AppEvents?.BOT_ERROR || 'bot:error';
          window.EventBus.emit(errorEvent, {
            message: error.message,
            error: error
          });
        }
      });
  },
  
  // Handle status updates from other sources (like WebSockets)
  handleStatusUpdate: function(data) {
    // Update status if we have valid data
    if (data && (typeof data.running !== 'undefined' || typeof data.status !== 'undefined')) {
      // Handle both data formats (direct running property or status property)
      if (typeof data.running !== 'undefined') {
        this.running = !!data.running;
      } else if (typeof data.status !== 'undefined') {
        this.running = data.status === 'running';
      }
      
      // Update other properties if available
      if (typeof data.connected !== 'undefined') this.connected = !!data.connected;
      if (typeof data.tts_enabled !== 'undefined') this.tts_enabled = !!data.tts_enabled;
      
      // Update timestamp
      this.last_checked = new Date();
      
      // Update uptime if provided
      if (data.uptime) this.uptime = data.uptime;
      
      // Update UI
      this.updateUI(false);
    }
  },
  
  // Update all UI elements
  updateUI: function(skipNotifications = false) {
    // Update buttons
    this.updateButtons();
    
    // Update status indicators
    this.updateStatusIndicators(skipNotifications);
    
    // Update uptime display if available
    this.updateUptimeDisplay();
  },
  
  // Update button states based on status
  updateButtons: function() {
    // Global buttons: find all buttons with specific data attributes
    const allButtons = document.querySelectorAll('[data-bot-action]');
    
    allButtons.forEach(button => {
      // If button has data-always-enabled, never disable it regardless of other attributes
      if (button.hasAttribute('data-always-enabled')) {
        button.disabled = false;
        button.removeAttribute('data-bot-disabled');
        button.title = "";
        return; // Skip further processing for this button
      }
      
      const action = button.getAttribute('data-bot-action');
      
      switch (action) {
        case 'start':
          button.disabled = this.running;
          break;
        case 'stop':
          button.disabled = !this.running;
          break;
        case 'send':
          button.disabled = !this.running;
          
          // Add visual indication with title
          if (!this.running) {
            button.title = "Bot is not running";
            button.setAttribute('data-bot-disabled', 'true');
          } else {
            button.title = "";
            button.removeAttribute('data-bot-disabled');
          }
          break;
        // Special case for generate buttons - Don't disable them even if bot is not running
        case 'generate':
          // Message generation works without bot running, so don't disable the button
          button.removeAttribute('data-bot-disabled');
          button.title = "";
          button.disabled = false;
          break;
        case 'tts-toggle':
          // Don't disable, but maybe update checked state
          if (button.tagName === 'INPUT' && button.type === 'checkbox') {
            button.checked = this.tts_enabled;
          }
          break;
      }
    });
    
    // Legacy support - for older code that doesn't use data attributes
    // Only for send message buttons, not generate buttons
    document.querySelectorAll(".send-message-btn").forEach(button => {
      if (!button.getAttribute('data-bot-action')) {
        // Only disable if it doesn't have a "generate" class
        if (!button.classList.contains('generate') && !button.hasAttribute('data-bot-action')) {
          button.disabled = !this.running;
          if (!this.running) {
            button.title = "Bot is not running";
          } else {
            button.title = "";
          }
        }
      }
    });
    
    // For channel-based buttons, distinguish between generate and send buttons
    document.querySelectorAll(".btn-primary[data-channel]").forEach(button => {
      if (!button.getAttribute('data-bot-action')) {
        // Only disable if it doesn't have a generate-related attribute
        const isGenerateButton = 
          button.classList.contains('generate') || 
          button.textContent.includes('Generate') ||
          button.innerHTML.includes('Generate');
          
        if (!isGenerateButton) {
          button.disabled = !this.running;
          if (!this.running) {
            button.title = "Bot is not running";
          } else {
            button.title = "";
          }
        } else {
          // Ensure generate buttons are enabled
          button.disabled = false;
          button.title = "";
        }
      }
    });
  },
  
  // Update status indicators
  updateStatusIndicators: function(skipNotifications = false) {
    // Hero Status Elements
    const heroStatusDot = document.getElementById('heroStatusDot');
    const heroStatusText = document.getElementById('heroStatusText');

    if (heroStatusDot && heroStatusText) {
        if (this.running) {
            // Using class for hero status dot as defined in index.html CSS
            if (this.connected) {
                heroStatusDot.parentElement.classList.add('status-active'); // Assumes heroStatusDot is child of element with status-active
                heroStatusDot.style.backgroundColor = ''; // Rely on CSS
                heroStatusText.textContent = 'Online & Connected';
            } else {
                heroStatusDot.parentElement.classList.remove('status-active');
                heroStatusDot.style.backgroundColor = '#ffc107'; // Yellow for 'Online (Not Connected)'
                heroStatusText.textContent = 'Online (Not Connected)';
            }
        } else {
            heroStatusDot.parentElement.classList.remove('status-active');
            heroStatusDot.style.backgroundColor = '#dc3545'; // Red for 'Offline'
            heroStatusText.textContent = 'Offline';
        }
    }

    // Main status in navbar
    const navbarIcon = document.getElementById('botStatusIcon');
    if (navbarIcon) {
      if (this.running) {
        if (this.connected) {
          navbarIcon.className = 'bi bi-circle-fill ms-2 text-success';
        } else {
          navbarIcon.className = 'bi bi-circle-fill ms-2 text-warning';
        }
      } else {
        navbarIcon.className = 'bi bi-circle-fill ms-2 text-danger';
      }
    }
    
    // Status text on bot control page
    const statusText = document.getElementById('botStatusText');
    if (statusText) {
      if (this.running) {
        if (this.connected) {
          statusText.textContent = 'Running & Connected';
          statusText.className = 'mb-0 text-success';
        } else {
          statusText.textContent = 'Running (Not Connected)';
          statusText.className = 'mb-0 text-warning';
        }
      } else {
        statusText.textContent = 'Stopped';
        statusText.className = 'mb-0 text-danger';
      }
    }
    
    // Status badge used on various pages
    const statusBadge = document.getElementById('botStatusIndicator');
    if (statusBadge) {
      statusBadge.className = this.running ? 'ms-2 badge bg-success' : 'ms-2 badge bg-danger';
      statusBadge.textContent = this.running ? 'Bot Online' : 'Bot Offline';
    }
    
    // Status spinner - always hide after update
    const statusSpinner = document.getElementById('statusSpinner');
    if (statusSpinner) {
      statusSpinner.style.display = 'none';
    }
    
    // TTS toggle - ensure it reflects server state
    const ttsToggle = document.getElementById('enable_tts');
    if (ttsToggle && ttsToggle.type === 'checkbox') {
      ttsToggle.checked = this.tts_enabled;
    }
    
    // Last updated timestamp
    const lastUpdated = document.getElementById('statusLastUpdated');
    if (lastUpdated) {
      lastUpdated.textContent = 'Last updated: ' + this.last_checked.toLocaleTimeString();
    }
    
    // Update diagnostics link if debug data is enabled
    const debugLink = document.getElementById('botStatusDebugLink');
    if (debugLink) {
      debugLink.style.display = this.running ? 'block' : 'none';
    }
    
    // Skip showing any toasts/notifications on settings page if we were asked to
    if (skipNotifications) {
      // Don't show "updating theme" or other toasts during routine checks
      console.log("Skipping notifications during routine status check");
    }
  },
  
  // Update uptime display
  updateUptimeDisplay: function() {
    const uptimeDisplay = document.getElementById('activeSince'); // Target 'activeSince' in Bot Analytics
    if (uptimeDisplay) {
      if (this.running && typeof this.uptime === 'number' && this.uptime > 0) {
        let seconds = this.uptime;
        const days = Math.floor(seconds / (3600 * 24));
        seconds -= days * 3600 * 24;
        const hours = Math.floor(seconds / 3600);
        seconds -= hours * 3600;
        const minutes = Math.floor(seconds / 60);
        seconds -= minutes * 60;
        const secs = Math.floor(seconds);

        let uptimeString = '';
        if (days > 0) uptimeString += `${days}d `;
        if (hours > 0 || days > 0) uptimeString += `${hours}h `; // Show hours if days are present
        if (minutes > 0 || hours > 0 || days > 0) uptimeString += `${minutes}m `; // Show minutes if hours/days are present
        uptimeString += `${secs}s`;
        
        uptimeDisplay.textContent = uptimeString.trim();
      } else if (this.running) {
        uptimeDisplay.textContent = 'Calculating...'; // Or 'Online' if uptime is 0/null but running
      }
      else {
        uptimeDisplay.textContent = 'Offline';
      }
    }
  }
};

// Initialize bot status immediately - don't wait for DOMContentLoaded
// This is critical since other scripts depend on BotStatus being available
(function initializeBotStatus() {
  console.log("Initializing BotStatus immediately");
  window.BotStatus.init();
  console.log("BotStatus initialization completed");
})();

// Also keep the DOMContentLoaded handler for safety
document.addEventListener('DOMContentLoaded', function() {
  // Make sure it's initialized - this is backup
  if (!window.BotStatus.last_checked || 
      (new Date() - window.BotStatus.last_checked) > 10000) {
    console.log("Re-initializing BotStatus on DOMContentLoaded");
    window.BotStatus.init();
  }
});

// Legacy compatibility layer - provide functions that older code might use
function checkBotStatus() {
  window.BotStatus.checkStatus();
}

function updateButtonStates(isBotRunning) {
  window.BotStatus.running = isBotRunning;
  window.BotStatus.updateButtons();
}

function fetchBotStatusAndUpdateUI() {
  window.BotStatus.checkStatus();
}
