function fetchAvailableModels() {
  fetch("/available-models")
      .then((response) => response.json())
      .then((models) => {
          const modelSelector = document.getElementById("modelSelector");
          models.forEach((model) => {
              const option = document.createElement("option");
              option.value = model;
              option.textContent = model;
              modelSelector.appendChild(option);
          });
      })
      .catch((error) => console.error("Error fetching models:", error));
}

// This is a delegating implementation of generateMessage
// It calls the primary implementation in data_handler.js
function generateMessage() {
  console.log("markov.js: Delegating to primary generateMessage implementation");
  
  // Check if the data_handler.js implementation is available in global scope
  if (typeof window.generateMessage === 'function') {
    // Call the global implementation
    window.generateMessage();
  } else {
    // Fallback if data_handler.js hasn't loaded or defined the function globally
    const modelSelect = document.getElementById('modelSelector');
    const channelSelect = document.getElementById('channelForMessage');
    const messageContainer = document.getElementById('generatedMessageContainer');
    const messageElement = document.getElementById('generatedMessage');
    const generateBtn = document.getElementById('generateMsgBtn');
    
    // Check if elements exist
    if (!modelSelect || !messageElement || !messageContainer) {
      console.error("Required elements not found for message generation");
      return;
    }
    
    // Show loading state
    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
    }
    
    messageContainer.classList.remove('d-none');
    messageElement.innerHTML = 'Generating message...';
    
    // Get selected values
    const model = modelSelect.value;
    const channel = channelSelect ? channelSelect.value : null;
    
    console.log(`Generating message with model: ${model}, channel: ${channel}`);
    
    fetch('/generate-message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ model: model, channel: channel })
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to generate message: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      if (data.message) {
        messageElement.textContent = data.message;
      } else {
        messageElement.textContent = 'Failed to generate message.';
      }
    })
    .catch(error => {
      console.error('Error:', error);
      messageElement.textContent = 'Error generating message.';
    })
    .finally(() => {
      // Re-enable button
      if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = 'Generate Message';
      }
    });
  }
}

function rebuildCacheForChannel(channelName) {
  // Show loading state
  const button = document.querySelector(`button[data-channel="${channelName}"][data-action="rebuild"]`);
  if (button) {
    const originalText = button.textContent;
    button.textContent = "Building...";
    button.disabled = true;
    
    // Call the API to rebuild the model directly - let server handle errors
    fetch(`/rebuild-cache/${channelName}`, {
      method: 'POST'
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showToast(`Model for ${channelName} rebuilt successfully`, 'success');
        } else {
          showToast(`Failed: ${data.message}`, 'error');
        }
      })
      .catch(error => {
        console.error('Error rebuilding model:', error);
        showToast(`Error rebuilding model: ${error.message}`, 'error');
      })
      .finally(() => {
        // Restore button state
        if (button) {
          button.textContent = originalText;
          button.disabled = false;
        }
      });
  }
}

/**
 * Send a Markov-generated message to a channel
 * @param {string} channelName - The channel to send the message to
 */
function sendMarkovMessage(channelName) {
  // This function can be used in two ways:
  // 1. Generate message only - always works regardless of bot status
  // 2. Generate and send to Twitch - only works if bot is running
  
  // Log and show loading state
  console.log(`Generating message for channel: ${channelName}`);
  const button = document.querySelector(`button[data-channel="${channelName}"]`);
  let originalText = "Generate";
  let originalHTML = null;
  
  if (button) {
    // Save original state
    originalText = button.textContent;
    originalHTML = button.innerHTML;
    
    // Set loading state - always show generating, not sending
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating...';
    button.disabled = true;
  } else {
    console.warn(`Button for channel ${channelName} not found`);
  }
  
  // Call the API directly - let server handle any errors
  fetch(`/send_markov_message/${channelName}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => {
      if (!response.ok) {
        // Try to get error message if possible
        return response.json().then(data => {
          throw new Error(data.message || `Failed to send message: ${response.status}`);
        }).catch(() => {
          throw new Error(`Failed to send message: ${response.status}`);
        });
      }
      return response.json();
    })
    .then(data => {
      if (data.success) {
        if (data.sent === true) {
          // Message was successfully sent to Twitch
          showToast(`Message sent to ${channelName}: "${data.message}"`, 'success');
        } else {
          // Message was generated but couldn't be sent to Twitch
          // Important: Only show a success toast with the generated message
          showToast(`Generated message: "${data.message}"`, 'success');
          
          // Log but DON'T SHOW any "bot is not running" messages to user
          console.log(`Message generated but not sent: ${data.error || 'No reason provided'}`);
        }
      } else {
        // Only show error toast if generation completely failed,
        // and make sure it never mentions "bot not running"
        showToast(`Failed to generate message`, 'error');
        console.error('Error generating message:', data.message);
      }
    })
    .catch(error => {
      console.error('Error sending message:', error);
      showToast(`Error sending message: ${error.message}`, 'error');
    })
  .finally(() => {
    // Restore button state if it exists
    if (button) {
      if (originalHTML) {
        button.innerHTML = originalHTML;
      } else {
        button.textContent = originalText;
      }
      button.disabled = false;
    }
  });
}

// Create a global module object for cross-file access - CRITICAL for button functionality
// Initialize this right away but ensure BotStatus is available first
(function initializeMarkovModule() {
  console.log("Initializing markovModule global object");
  
  // Wait until DOM is ready before initializing
  document.addEventListener('DOMContentLoaded', function() {
    // Create module and expose functions
    window.markovModule = window.markovModule || {};
    window.markovModule.sendMarkovMessage = sendMarkovMessage;
    window.markovModule.rebuildChannelModel = rebuildCacheForChannel;
    
    console.log("markovModule initialized successfully");
  });
})();

// NOTE: rebuildChannelModel was a duplicate function of rebuildCacheForChannel
// We're keeping rebuildCacheForChannel as the primary implementation 
// and exposing it via window.markovModule.rebuildChannelModel for consistency.

function rebuildAllCaches() {
  const rebuildAllButton = document.getElementById('rebuildAllCachesBtn');
  if (rebuildAllButton) {
      rebuildAllButton.disabled = true;
      rebuildAllButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> In Surgery';

      fetch('/rebuild-all-caches', { method: 'POST' })
          .then(response => {
              if (!response.ok) {
                  throw new Error('Failed to rebuild all caches');
              }
              return response.json();
          })
          .then(data => {
              if (data.success) {
                  alert('All caches rebuilt successfully');
              } else {
                  alert('Failed to rebuild all caches');
              }
          })
          .catch(error => {
              console.error('Error:', error);
              alert(`Error rebuilding all caches: ${error}`);
          })
          .finally(() => {
              rebuildAllButton.disabled = false;
              rebuildAllButton.textContent = 'Rebuild All Caches';
          });
  }
}

// Diagnostic function to check what rebuild functions are available on window
function diagnoseRebuild() {
    console.log("==== REBUILD FUNCTIONS DIAGNOSIS ====");
    console.log("window.rebuildCacheForChannelGlobal exists:", typeof window.rebuildCacheForChannelGlobal === 'function');
    console.log("window.markovModule exists:", typeof window.markovModule === 'object');
    if (window.markovModule) {
        console.log("window.markovModule.rebuildChannelModel exists:", typeof window.markovModule.rebuildChannelModel === 'function');
    }
    console.log("window.rebuildCacheForChannel exists:", typeof window.rebuildCacheForChannel === 'function');
    
    // Force update all rebuild buttons to use the correct handler
    console.log("Updating all rebuild buttons to use correct handler...");
    const rebuildButtons = document.querySelectorAll('button[data-action="rebuild"]');
    rebuildButtons.forEach(button => {
        const channel = button.getAttribute('data-channel');
        if (channel) {
            console.log(`Found rebuild button for channel: ${channel}`);
            // Remove any previous onclick handler
            button.onclick = null;
            // Add new handler that explicitly uses the correct function
            button.addEventListener('click', function(event) {
                // Prevent default to stop any existing handler
                event.preventDefault();
                event.stopPropagation();
                console.log(`Rebuild button clicked for channel: ${channel}`);
                
                // Log which function we're using
                if (typeof window.rebuildCacheForChannelGlobal === 'function') {
                    console.log("Using global rebuildCacheForChannelGlobal function");
                    window.rebuildCacheForChannelGlobal(channel);
                } else if (typeof window.rebuildCacheForChannel === 'function') {
                    console.log("Using local rebuildCacheForChannel function");
                    window.rebuildCacheForChannel(channel);
                } else {
                    console.log("Using direct implementation");
                    // Inline implementation to ensure it works
                    const btn = event.target.closest('button');
                    if (btn) {
                        const originalText = btn.textContent;
                        btn.textContent = "Building...";
                        btn.disabled = true;
                        
                        fetch(`/rebuild-cache/${channel}`, {
                            method: 'POST'
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                showToast(`Model for ${channel} rebuilt successfully`, 'success');
                            } else {
                                showToast(`Failed to rebuild model: ${data.message}`, 'error');
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            showToast(`Error rebuilding model: ${error.message}`, 'error');
                        })
                        .finally(() => {
                            btn.textContent = originalText;
                            btn.disabled = false;
                        });
                    }
                }
            });
            console.log(`Updated rebuild button for channel: ${channel}`);
        }
    });
    console.log("==== DIAGNOSIS COMPLETE ====");
    
    // Return a message that can be shown to the user
    return "Rebuild buttons updated. Check console for details.";
}

function rebuildGeneralCache() {
    const rebuildGeneralCacheBtn = document.getElementById('rebuildGeneralCacheBtn');
    rebuildGeneralCacheBtn.disabled = true;
    rebuildGeneralCacheBtn.textContent = 'Rebuilding...';

    fetch('/rebuild-general-cache', { method: 'POST' })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to rebuild general cache');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert('General cache rebuilt successfully');
            } else {
                alert('Failed to rebuild general cache');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert(`Error rebuilding general cache: ${error}`);
        })
        .finally(() => {
            rebuildGeneralCacheBtn.disabled = false;
            rebuildGeneralCacheBtn.textContent = 'Rebuild General Cache';
        });
}