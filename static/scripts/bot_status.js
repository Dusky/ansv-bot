/**
 * bot_status.js - Centralized bot status management
 * 
 * This file provides a single source of truth for bot status across all pages.
 * It should be included before other scripts that need to check bot status.
 */

// Global bot status variable - accessible to all scripts
window.BotStatus = {
  // Status flags
  running: false,
  connected: false,
  tts_enabled: false,
  
  // Timestamps
  last_checked: new Date(),
  uptime: null,
  
  // Initialization
  init: function() {
    console.log("BotStatus initialized");
    
    // Do initial check
    this.checkStatus();
    
    // Set up periodic checking
    setInterval(() => this.checkStatus(), 10000); // Check every 10 seconds
    
    // Return self for chaining
    return this;
  },
  
  // Check bot status from server
  checkStatus: function() {
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
        
        // Update internal state
        this.running = !!data.running;
        this.connected = !!data.connected;
        this.tts_enabled = !!data.tts_enabled;
        this.last_checked = new Date();
        this.uptime = data.uptime || null;
        
        // Trigger UI updates
        this.updateUI();
        
        // Dispatch event for other scripts
        const event = new CustomEvent('botstatus', { 
          detail: { 
            running: this.running,
            connected: this.connected,
            tts_enabled: this.tts_enabled
          }
        });
        window.dispatchEvent(event);
      })
      .catch(error => {
        console.error("Error checking bot status:", error);
        
        // Set to not running on error
        this.running = false;
        this.connected = false;
        
        // Still update UI
        this.updateUI();
      });
  },
  
  // Update all UI elements
  updateUI: function() {
    // Update buttons
    this.updateButtons();
    
    // Update status indicators
    this.updateStatusIndicators();
    
    // Update uptime display if available
    this.updateUptimeDisplay();
  },
  
  // Update button states based on status
  updateButtons: function() {
    // Global buttons: find all buttons with specific data attributes
    const allButtons = document.querySelectorAll('[data-bot-action]');
    
    allButtons.forEach(button => {
      const action = button.getAttribute('data-bot-action');
      
      switch (action) {
        case 'start':
          button.disabled = this.running;
          break;
        case 'stop':
          button.disabled = !this.running;
          break;
        case 'generate':
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
        case 'tts-toggle':
          // Don't disable, but maybe update checked state
          if (button.tagName === 'INPUT' && button.type === 'checkbox') {
            button.checked = this.tts_enabled;
          }
          break;
      }
    });
    
    // Legacy support - for older code that doesn't use data attributes
    // Generate buttons - both class-based and channel-based
    document.querySelectorAll(".send-message-btn, .btn-primary[data-channel]").forEach(button => {
      if (!button.getAttribute('data-bot-action')) {
        button.disabled = !this.running;
        if (!this.running) {
          button.title = "Bot is not running";
        } else {
          button.title = "";
        }
      }
    });
  },
  
  // Update status indicators
  updateStatusIndicators: function() {
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
    
    // Status spinner
    const statusSpinner = document.getElementById('statusSpinner');
    if (statusSpinner) {
      statusSpinner.style.display = 'none';
    }
    
    // Last updated timestamp
    const lastUpdated = document.getElementById('statusLastUpdated');
    if (lastUpdated) {
      lastUpdated.textContent = 'Last updated: ' + this.last_checked.toLocaleTimeString();
    }
  },
  
  // Update uptime display
  updateUptimeDisplay: function() {
    const uptimeDisplay = document.getElementById('botUptime');
    if (uptimeDisplay) {
      if (this.running && this.uptime) {
        uptimeDisplay.textContent = this.uptime;
      } else {
        uptimeDisplay.textContent = 'Not running';
      }
    }
  }
};

// Initialize bot status
document.addEventListener('DOMContentLoaded', function() {
  // Initialize immediately
  window.BotStatus.init();
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