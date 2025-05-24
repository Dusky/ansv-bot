function fetchAvailableModels() {
  fetch("/available-models")
      .then((response) => response.json())
      .then((models) => {
          const modelSelector = document.getElementById("modelSelector");
          
          // Check if the modelSelector element exists on the page
          if (!modelSelector) {
              // console.warn("Element with ID 'modelSelector' not found on this page. Skipping model population for this call.");
              return; // Exit if the selector isn't there
          }

          // Clear existing options before adding new ones
          while (modelSelector.options.length > 0) {
              modelSelector.remove(0);
          }
          
          // Add a default/placeholder option
          const defaultOption = document.createElement("option");
          defaultOption.value = "general_markov"; // Default to general_markov
          defaultOption.textContent = "General Model";
          modelSelector.appendChild(defaultOption);

          models.forEach((model) => {
              let modelName = model; // Assuming model is a string
              if (typeof model === 'object' && model !== null && model.hasOwnProperty('name')) {
                  modelName = model.name; // If model is an object like { name: "model_name", ... }
              } else if (typeof model !== 'string') {
                  console.warn("Unexpected model format in /available-models response:", model);
                  return; 
              }

              // Avoid adding "general_markov" again if it's in the list from the server
              if (modelName.toLowerCase() === "general_markov" || modelName.toLowerCase() === "general model") {
                  // Ensure the default option's text is consistent
                  if (modelSelector.options[0].value === "general_markov") {
                      modelSelector.options[0].textContent = modelName;
                  }
                  return;
              }
              const option = document.createElement("option");
              option.value = modelName;
              option.textContent = modelName;
              modelSelector.appendChild(option);
          });
      })
      .catch((error) => console.error("Error fetching models:", error));
}

/**
 * Centralized message generation and sending
 * Provides a single interface for generating and sending messages to channels
 */
window.MessageManager = window.MessageManager || {
    // Configuration
    defaultModel: 'general_markov', // Updated default
    
    // Initialize the message manager
    init: function() {
        console.log('MessageManager initializing');
        fetchAvailableModels(); // Load models when MessageManager is initialized
        return this;
    },
    
    // Generate a message for a specific channel and model
    generateMessage: function(options = {}) {
        const defaults = {
            channel: null,
            model: this.defaultModel,
            callback: null,
            sendToTwitch: false,
            button: null // Pass the button element for UI updates
        };
        const config = { ...defaults, ...options };

        if (config.sendToTwitch && !config.channel) {
            const errorMsg = 'Channel required when sending to Twitch';
            console.error(errorMsg);
            this.showNotification(errorMsg, 'error');
            if (config.button) this.setButtonLoading(config.button, false); // Reset button
            return Promise.reject(new Error(errorMsg));
        }
        
        if (config.button) {
            this.setButtonLoading(config.button, true, config.sendToTwitch);
        }
        
        const endpoint = config.sendToTwitch
            ? `/send_markov_message/${config.channel}`
            : '/generate-message';
            
        const payload = config.sendToTwitch
            ? { verify_running: true, force_send: true, bypass_check: true } 
            : { model: config.model, channel: config.channel };
            
        return fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.message || data.error || `Request failed: ${response.status}`);
                }).catch(() => {
                    throw new Error(`Request failed: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success !== false) { // Treat missing success as true, or explicitly true
                const message = data.message || '';
                if (config.sendToTwitch) {
                    if (data.sent === true) {
                        this.showNotification(`Message sent to ${config.channel}: "${message}"`, 'success');
                    } else {
                        if (message === null || message === "null" || !message) {
                            this.showNotification("Failed to generate message for sending.", 'error');
                        } else {
                            this.showNotification(`Generated: "${message}" (not sent: ${data.error || 'see console'})`, 'warning');
                        }
                        console.warn("Message was not sent:", data.error || "Unknown reason. Bot running:", data.server_verified);
                    }
                } else {
                     if (message === null || message === "null" || !message) {
                        this.showNotification("Failed to generate message.", 'error');
                     } else {
                        this.showNotification(`Generated message: "${message}"`, 'success');
                     }
                }
                if (typeof config.callback === 'function') {
                    config.callback(message, data);
                }
                return message;
            } else {
                const errorMsg = data.message || data.error || 'Failed to process request';
                this.showNotification(errorMsg, 'error');
                throw new Error(errorMsg);
            }
        })
        .catch(error => {
            console.error('Error in MessageManager.generateMessage:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            throw error; // Re-throw for further handling if needed
        })
        .finally(() => {
            if (config.button) {
                this.setButtonLoading(config.button, false, config.sendToTwitch);
            }
        });
    },
    
    setButtonLoading: function(button, isLoading, isSending = false) {
        if (!button) return;
        const actionText = isSending ? 'Sending' : 'Generating';
        const iconClass = isSending ? 'fa-comment-dots' : 'fa-paper-plane';

        if (isLoading) {
            button.dataset.originalContent = button.innerHTML;
            button.disabled = true;
            button.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>${actionText}...`;
        } else {
            if (button.dataset.originalContent) {
                button.innerHTML = button.dataset.originalContent;
                delete button.dataset.originalContent;
            } else {
                 // Fallback: Reconstruct based on common patterns
                let originalIcon = `<i class="fas ${iconClass} me-1"></i>`;
                let originalActionText = isSending ? 'Generate & Send' : 'Generate Message';
                 // Attempt to find specific button text if possible
                if (button.id === 'generateMsgBtn') originalActionText = 'Generate Message';
                else if (button.classList.contains('send-message-btn')) originalActionText = 'Generate & Send';

                button.innerHTML = `${originalIcon}${originalActionText}`;
            }
            button.disabled = false;
        }
    },
    
    showNotification: function(message, type = 'info') {
        if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
            window.notificationSystem.showToast(message, type);
        } else {
            console.warn('Notification system not available. Message:', message, 'Type:', type);
            alert(`(${type}) ${message}`); // Fallback alert
        }
    }
};

function rebuildCacheForChannel(channelName) {
  console.log(`markov.js: rebuildCacheForChannel called for ${channelName}`);
  
  const button = document.querySelector(`button[data-channel="${channelName}"][data-action="rebuild"]`);
  let originalHTML = null;
  
  if (button) {
    originalHTML = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Building...';
    button.disabled = true;
  } else {
    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
        window.notificationSystem.showToast(`Rebuilding cache for ${channelName}...`, 'info');
    } else {
        alert(`Rebuilding cache for ${channelName}...`);
    }
  }
  
  fetch(`/rebuild-cache/${channelName}`, {
    method: 'POST'
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
            window.notificationSystem.showToast(`Model for ${channelName} rebuilt successfully`, 'success');
        } else {
            alert(`Model for ${channelName} rebuilt successfully`);
        }
        if (typeof window.loadStatistics === 'function') {
          window.loadStatistics(); // Refresh stats table
        }
      } else {
        if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
            window.notificationSystem.showToast(`Failed to rebuild model for ${channelName}: ${data.message || 'Unknown error'}`, 'error');
        } else {
            alert(`Failed to rebuild model for ${channelName}: ${data.message || 'Unknown error'}`);
        }
      }
    })
    .catch(error => {
      console.error('Error rebuilding cache for:', channelName, error);
      if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
        window.notificationSystem.showToast(`Error rebuilding model for ${channelName}: ${error.message}`, 'error');
      } else {
        alert(`Error rebuilding model for ${channelName}: ${error.message}`);
      }
    })
    .finally(() => {
      if (button) {
        button.innerHTML = originalHTML || '<i class="fas fa-tools me-1"></i>Rebuild';
        button.disabled = false;
      }
    });
}

// Initialize MessageManager and expose functions
(function initializeMarkovModule() {
  console.log("Initializing markovModule global object and MessageManager");
  
  window.MessageManager.init();
  
  window.markovModule = window.markovModule || {};
  
  // Expose MessageManager's generateMessage for general use
  window.markovModule.generateMessage = function(options) {
    return window.MessageManager.generateMessage(options);
  };

  // Specific function for sending to Twitch (for convenience)
  window.markovModule.sendMarkovMessage = function(channelName, buttonElement = null) {
    return window.MessageManager.generateMessage({
      channel: channelName,
      sendToTwitch: true,
      button: buttonElement
    });
  };
  
  window.markovModule.rebuildChannelModel = rebuildCacheForChannel; // For stats.js
  window.rebuildCacheForChannelGlobal = rebuildCacheForChannel; // For older references if any

  // Ensure these are available for direct calls from HTML or other scripts if not using markovModule
  window.generateMessage = function(options) { // General purpose, can be display-only or send
      return window.MessageManager.generateMessage(options);
  };
  window.sendMarkovMessage = function(channelName, buttonElement = null) { // Specifically for sending
      return window.MessageManager.generateMessage({ channel: channelName, sendToTwitch: true, button: buttonElement });
  };
  window.rebuildCacheForChannel = rebuildCacheForChannel;


  console.log("markovModule and MessageManager initialized successfully");
})();

// Functions for general and all cache rebuild (usually on stats page)
function rebuildAllCaches() {
  const rebuildAllButton = document.getElementById('rebuildAllCachesBtn');
  if (rebuildAllButton) {
      const originalHTML = rebuildAllButton.innerHTML;
      rebuildAllButton.disabled = true;
      rebuildAllButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rebuilding All...';

      fetch('/rebuild-all-caches', { method: 'POST' })
          .then(response => response.json())
          .then(data => {
              if (data.success) {
                  if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                    window.notificationSystem.showToast('All caches rebuilt successfully', 'success');
                  } else {
                    alert('All caches rebuilt successfully');
                  }
              } else {
                  if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                    window.notificationSystem.showToast(`Failed to rebuild all caches: ${data.message || 'Unknown error'}`, 'error');
                  } else {
                    alert(`Failed to rebuild all caches: ${data.message || 'Unknown error'}`);
                  }
              }
              if (typeof window.loadStatistics === 'function') {
                  window.loadStatistics();
              }
          })
          .catch(error => {
              console.error('Error rebuilding all caches:', error);
              if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                window.notificationSystem.showToast(`Error rebuilding all caches: ${error.message}`, 'error');
              } else {
                alert(`Error rebuilding all caches: ${error.message}`);
              }
          })
          .finally(() => {
              rebuildAllButton.disabled = false;
              rebuildAllButton.innerHTML = originalHTML;
          });
  }
}

function rebuildGeneralCache() {
    const rebuildGeneralButton = document.getElementById('rebuildGeneralCacheBtn');
    if (rebuildGeneralButton) {
        const originalHTML = rebuildGeneralButton.innerHTML;
        rebuildGeneralButton.disabled = true;
        rebuildGeneralButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rebuilding General...';

        fetch('/rebuild-general-cache', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                        window.notificationSystem.showToast('General cache rebuilt successfully', 'success');
                    } else {
                        alert('General cache rebuilt successfully');
                    }
                } else {
                    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                        window.notificationSystem.showToast(`Failed to rebuild general cache: ${data.message || 'Unknown error'}`, 'error');
                    } else {
                        alert(`Failed to rebuild general cache: ${data.message || 'Unknown error'}`);
                    }
                }
                if (typeof window.loadStatistics === 'function') {
                    window.loadStatistics();
                }
            })
            .catch(error => {
                console.error('Error rebuilding general cache:', error);
                if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
                    window.notificationSystem.showToast(`Error rebuilding general cache: ${error.message}`, 'error');
                } else {
                    alert(`Error rebuilding general cache: ${error.message}`);
                }
            })
            .finally(() => {
                rebuildGeneralButton.disabled = false;
                rebuildGeneralButton.innerHTML = originalHTML;
            });
    }
}

// Ensure model selector is populated on DOMContentLoaded if it exists
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('modelSelector')) {
        fetchAvailableModels();
    }
    // Attach listeners for global rebuild buttons if they exist
    const rebuildAllBtn = document.getElementById('rebuildAllCachesBtn');
    if (rebuildAllBtn) {
        rebuildAllBtn.addEventListener('click', rebuildAllCaches);
    }
    const rebuildGeneralBtn = document.getElementById('rebuildGeneralCacheBtn');
    if (rebuildGeneralBtn) {
        rebuildGeneralBtn.addEventListener('click', rebuildGeneralCache);
    }
});
