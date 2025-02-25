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

function generateMessage() {
  const modelSelect = document.getElementById('modelSelector');
  const channelSelect = document.getElementById('channelForMessage');
  const messageContainer = document.getElementById('generatedMessageContainer');
  const messageElement = document.getElementById('generatedMessage');
  
  if (!modelSelect || !messageElement) {
    console.error("Required elements not found for message generation");
    return;
  }
  
  // Show loading state
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
  });
}

function rebuildCacheForChannel(channelName) {
  // Show loading state
  const button = document.querySelector(`button[data-channel="${channelName}"][data-action="rebuild"]`);
  if (button) {
    const originalText = button.textContent;
    button.textContent = "Building...";
    button.disabled = true;
    
    // Call the API to rebuild the model - use the existing endpoint
    fetch(`/rebuild-channel-model/${channelName}`, {
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
      showToast('Error rebuilding model', 'error');
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
  // Show loading state
  const button = document.querySelector(`button[data-channel="${channelName}"]`);
  if (!button) {
    console.error(`Button for channel ${channelName} not found`);
    return;
  }

  const originalText = button.textContent;
  button.textContent = "Sending...";
  button.disabled = true;
  
  console.log(`Sending message to channel: ${channelName}`);
  
  // Call the API to send the message
  fetch(`/send_markov_message/${channelName}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    if (data.success) {
      showToast(`Message ${data.message.includes('request') ? 'queued' : 'sent'} to ${channelName}`, 'success');
    } else {
      showToast(`Failed: ${data.message}`, 'error');
      console.error('Error sending message:', data.message);
    }
  })
  .catch(error => {
    console.error('Error sending message:', error);
    showToast('Error sending message', 'error');
  })
  .finally(() => {
    // Restore button state
    button.textContent = originalText;
    button.disabled = false;
  });
}

/**
 * Rebuild the Markov model for a specific channel
 * @param {string} channelName - The channel to rebuild the model for
 */
function rebuildChannelModel(channelName) {
  // Show loading state
  const button = document.querySelector(`button[data-channel="${channelName}"][data-action="rebuild"]`);
  if (button) {
    const originalText = button.textContent;
    button.textContent = "Building...";
    button.disabled = true;
    
    // Call the API to rebuild the model
    fetch(`/rebuild-channel-model/${channelName}`, {
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
      showToast('Error rebuilding model', 'error');
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