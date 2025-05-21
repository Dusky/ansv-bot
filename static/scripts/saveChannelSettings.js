function saveChannelSettings() {
  if (!validateChannelForm()) {
    return; // Stop if validation fails
  }

  var selectedChannel = document.getElementById("channelSelect").value;
  var isAddChannel = selectedChannel === "add_channel";
  var channelName = isAddChannel
    ? document.getElementById("newChannelName").value.trim()
    : selectedChannel;

  if (isAddChannel && !channelName) {
    alert("Please enter a channel name.");
    return;
  }

  // Fetch the selected voice preset or custom voice
  var voicePresetSelect = document.getElementById("voicePreset");
  var customVoiceSelect = document.getElementById("customVoiceSelect");
  var voicePreset = voicePresetSelect.value === "custom"
    ? customVoiceSelect.value
    : voicePresetSelect.value;

  var updatedData = {
    channel_name: channelName,
    tts_enabled: document.getElementById("ttsEnabled").checked ? 1 : 0,
    voice_enabled: document.getElementById("voiceEnabled").checked ? 1 : 0,
    join_channel: document.getElementById("joinChannel").checked ? 1 : 0,
    owner: document.getElementById("owner").value || channelName,
    trusted_users: document.getElementById("trustedUsers").value,
    ignored_users: document.getElementById("ignoredUsers").value,
    use_general_model: document.getElementById("useGeneralModel").checked ? 1 : 0,
    lines_between_messages: document.getElementById("linesBetweenMessages").value || 0,
    time_between_messages: document.getElementById("timeBetweenMessages").value || 0,
    voice_preset: voicePreset,
    bark_model: document.getElementById("barkModel") ? document.getElementById("barkModel").value : "regular"
  };

  if (isAddChannel) {
    addNewChannel(updatedData, function() {
      // Reload channel list without full page refresh
      fetchChannels();
      // Reset the form
      document.getElementById("channelSelect").selectedIndex = 0;
      checkForAddChannelOption(document.getElementById("channelSelect"));
      
      displayNotification('Channel added successfully!', 'success');
    });
  } else {
    updateChannelSettings(updatedData, function() {
      displayNotification('Settings saved successfully!', 'success');
    });
  }
}


function updateChannelSettings(data, callback) {
  fetch("/update-channel-settings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success) {
        // Call callback instead of alert if provided
        if (typeof callback === 'function') {
          callback();
        } else {
          alert("Channel settings updated successfully.");
        }
      } else {
        alert("Failed to update settings: " + result.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while updating settings.");
    });
}
function handleSaveResponse(data) {
  if (data.success) {
    displayNotification("Settings saved successfully.", "success");
  } else {
    displayNotification("Failed to save settings: " + data.message, "error");
  }
}

// Safe notification function
function displayNotification(message, type = "info") {
  // Try namespace first
  if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
    window.notificationSystem.showToast(message, type);
  } 
  // Fall back to global showToast
  else if (typeof window.showToast === "function") {
    window.showToast(message, type);
  } 
  // Use console and alert as a final fallback
  else {
    console.log(`Toast (${type}): ${message}`);
    if (type === 'error') {
      alert(`Error: ${message}`);
    } else {
      alert(message);
    }
  }
}
function addNewChannel(data, callback) {
  fetch("/add-channel", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success) {
        // Call callback instead of alert if provided
        if (typeof callback === 'function') {
          callback();
        } else {
          alert("Channel added: " + result.message);
        }
      } else {
        alert("Failed to add channel: " + result.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while adding the channel.");
    });
}



function displayChannelConfig(channels, selectedChannel) {
  var channelConfigForm = document.getElementById("channelConfig");
  var addChannelDiv = document.getElementById("addChannelDiv");
  var deleteChannelBtn = document.getElementById("deleteChannelBtn");

  if (selectedChannel === "add_channel") {
    channelConfigForm.style.display = "none";
    addChannelDiv.style.display = "block";
    // Hide delete button when adding a new channel
    if (deleteChannelBtn) {
      deleteChannelBtn.style.display = "none";
    }
  } else if (selectedChannel === "") {
    // No channel selected
    channelConfigForm.style.display = "none";
    addChannelDiv.style.display = "none";
    // Hide delete button when no channel is selected
    if (deleteChannelBtn) {
      deleteChannelBtn.style.display = "none";
    }
  } else {
    var channelData = channels.find((c) => c[0] === selectedChannel);
    if (channelData) {
      // Populate the form with existing channel data
      document.getElementById("ttsEnabled").checked = channelData[1] === 1;
      document.getElementById("voiceEnabled").checked = channelData[2] === 1;
      document.getElementById("joinChannel").checked = channelData[3] === 1;
      document.getElementById("owner").value = channelData[4] || "";
      document.getElementById("trustedUsers").value = channelData[5] || "";
      document.getElementById("ignoredUsers").value = channelData[6] || "";
      document.getElementById("useGeneralModel").checked = channelData[7] === 1;
      document.getElementById("linesBetweenMessages").value =
        channelData[8] || 0;
      document.getElementById("timeBetweenMessages").value =
        channelData[9] || 0;

      channelConfigForm.style.display = "block";
      addChannelDiv.style.display = "none";
      
      // Show delete button for existing channels
      if (deleteChannelBtn) {
        deleteChannelBtn.style.display = "block";
        // Set data attribute for the channel name to use when deleting
        deleteChannelBtn.setAttribute("data-channel", selectedChannel);
      }
    } else {
      channelConfigForm.style.display = "none";
      addChannelDiv.style.display = "none";
      // Hide delete button when no valid channel data
      if (deleteChannelBtn) {
        deleteChannelBtn.style.display = "none";
      }
    }
  }
}




function resetFormForNewChannel() {
  // Clear the form and set default values for a new channel
  document.getElementById("ttsEnabled").checked = false;
  document.getElementById("voiceEnabled").checked = false;
  document.getElementById("joinChannel").checked = true;
  document.getElementById("owner").value = "";
  document.getElementById("trustedUsers").value = "";
  document.getElementById("ignoredUsers").value = "";
  document.getElementById("useGeneralModel").checked = true;
  document.getElementById("linesBetweenMessages").value = 100;
  document.getElementById("timeBetweenMessages").value = 0;
  document.getElementById("newChannelName").value = ""; // Clear the new channel name field
}


/**
 * Centralized channel management system
 * Handles channel loading, status updating, and data formatting
 */
 
// Create a globally accessible ChannelManager
window.ChannelManager = window.ChannelManager || {
    // Store channel data
    channels: [],
    lastUpdated: null,
    
    // Initialize
    init: function() {
        console.log("ChannelManager initializing");
        this.loadChannels();
        return this;
    },
    
    // Load channels from the server
    loadChannels: function(callback) {
        console.log("Loading channels from server...");
        
        // Use the preferred API endpoint
        fetch("/api/channels")
            .then(response => {
                if (!response.ok) {
                    // Try fallback endpoint if main one fails
                    console.log("Primary endpoint failed, trying fallback...");
                    return fetch("/get-channels");
                }
                return response;
            })
            .then(response => response.json())
            .then(data => {
                console.log("Received channels data:", data);
                
                // Normalize the channel data format
                this.channels = this.normalizeChannelData(data);
                this.lastUpdated = new Date();
                
                // Update any channel dropdowns
                this.updateChannelDropdowns();
                
                // Run callback if provided
                if (typeof callback === 'function') {
                    callback(this.channels);
                }
                
                // Dispatch an event that other components can listen for
                const event = new CustomEvent('channels-updated', { 
                    detail: { channels: this.channels }
                });
                window.dispatchEvent(event);
            })
            .catch(error => {
                console.error("Error loading channels:", error);
                // Dispatch error event
                const event = new CustomEvent('channels-error', { 
                    detail: { error: error.message }
                });
                window.dispatchEvent(event);
            });
    },
    
    // Normalize channel data to a consistent format
    normalizeChannelData: function(data) {
        if (!data || !Array.isArray(data)) {
            console.warn("Invalid channel data format:", data);
            return [];
        }
        
        return data.map(channel => {
            // Create a standardized channel object
            let channelObj = {
                name: null,
                connected: false,
                tts_enabled: false
            };
            
            // Handle various possible formats
            if (Array.isArray(channel)) {
                channelObj.name = channel[0];
                // If array has more elements, try to parse them
                if (channel.length > 1) {
                    channelObj.tts_enabled = !!channel[1];
                }
                if (channel.length > 3) {
                    channelObj.connected = !!channel[3];
                }
            } else if (typeof channel === 'object' && channel !== null) {
                // Check for 'name' property
                if (channel.name) {
                    channelObj.name = channel.name;
                } else if (channel.channel_name) {
                    // Fallback to channel_name if present
                    channelObj.name = channel.channel_name;
                } else {
                    // Last fallback: use first string property if available
                    const firstStringProp = Object.entries(channel)
                        .find(([key, value]) => typeof value === 'string');
                    
                    if (firstStringProp) {
                        channelObj.name = firstStringProp[1];
                    }
                }
                
                // Copy additional properties if they exist
                if ('tts_enabled' in channel) channelObj.tts_enabled = !!channel.tts_enabled;
                if ('currently_connected' in channel) channelObj.connected = !!channel.currently_connected;
                if ('connected' in channel) channelObj.connected = !!channel.connected;
            } else if (typeof channel === 'string') {
                // Simple string value
                channelObj.name = channel;
            }
            
            return channelObj;
        }).filter(channel => {
            // Filter out invalid channels
            return channel.name && typeof channel.name === 'string' && 
                  channel.name !== 'undefined' && channel.name.trim() !== '';
        });
    },
    
    // Update all channel dropdowns
    updateChannelDropdowns: function() {
        // Find all channel select dropdowns
        const channelSelects = document.querySelectorAll('select[data-channel-select]');
        
        channelSelects.forEach(select => {
            this.updateChannelDropdown(select);
        });
        
        // Also update the main channel selector used in settings
        const mainChannelSelect = document.getElementById('channelSelect');
        if (mainChannelSelect) {
            this.updateSettingsChannelDropdown(mainChannelSelect);
        }
    },
    
    // Update a specific channel dropdown
    updateChannelDropdown: function(select) {
        if (!select) return;
        
        // Save current selection
        const currentValue = select.value;
        
        // Clear existing options (except any with keep-option attribute)
        const optionsToKeep = Array.from(select.options)
            .filter(option => option.hasAttribute('data-keep-option'));
            
        select.innerHTML = '';
        
        // Re-add any options we need to keep
        optionsToKeep.forEach(option => {
            select.appendChild(option);
        });
        
        // Add channel options
        this.channels.forEach(channel => {
            const option = document.createElement('option');
            option.value = channel.name;
            option.textContent = channel.name;
            
            // Add status indicator if the dropdown supports it
            if (select.hasAttribute('data-show-status') && channel.connected) {
                option.textContent += ' ✓';
            }
            
            select.appendChild(option);
        });
        
        // Restore selection if possible
        if (currentValue) {
            // Check if the previously selected option still exists
            const stillExists = Array.from(select.options)
                .some(option => option.value === currentValue);
                
            if (stillExists) {
                select.value = currentValue;
            }
        }
    },
    
    // Special handling for the settings page channel dropdown
    updateSettingsChannelDropdown: function(select) {
        if (!select) return;
        
        // Save current selection
        const currentValue = select.value;
        
        // Clear existing options except the first two (select prompt and add channel)
        while (select.options.length > 2) {
            select.remove(2);
        }
        
        // Add channel options
        this.channels.forEach(channel => {
            const option = document.createElement('option');
            option.value = channel.name;
            option.textContent = channel.name;
            select.appendChild(option);
        });
        
        // Check if the previously selected channel still exists
        let stillExists = false;
        for (let i = 0; i < select.options.length; i++) {
            if (select.options[i].value === currentValue) {
                stillExists = true;
                break;
            }
        }
        
        // If the previously selected channel still exists, select it again
        // Otherwise reset to the first option (no selection)
        if (stillExists && currentValue !== "add_channel") {
            select.value = currentValue;
        } else {
            select.selectedIndex = 0;  // Reset to first option
            // Make sure the form resets as well
            if (typeof checkForAddChannelOption === 'function') {
                checkForAddChannelOption(select);
            }
        }
    },
    
    // Get channel by name
    getChannel: function(channelName) {
        return this.channels.find(channel => channel.name === channelName) || null;
    },
    
    // Check if channel exists
    channelExists: function(channelName) {
        return this.channels.some(channel => channel.name === channelName);
    }
};

// Legacy support for the old fetchChannels function
function fetchChannels() {
    window.ChannelManager.loadChannels();
}


function fetchChannelSettings(channelName) {
  // Fetch settings for the selected channel and update the form
  fetch("/get-channel-settings/" + encodeURIComponent(channelName))
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      if (data) {
        document.getElementById("ttsEnabled").checked = data.tts_enabled === 1;
        document.getElementById("voiceEnabled").checked =
          data.voice_enabled === 1;
        document.getElementById("joinChannel").checked =
          data.join_channel === 1;
        document.getElementById("owner").value = data.owner || "";
        document.getElementById("trustedUsers").value =
          data.trusted_users || "";
        document.getElementById("ignoredUsers").value =
          data.ignored_users || "";
        document.getElementById("useGeneralModel").checked =
          data.use_general_model === 1;
        document.getElementById("linesBetweenMessages").value =
          data.lines_between_messages || 100;
        document.getElementById("timeBetweenMessages").value =
          data.time_between_messages || 0;
      }
    })
    .catch((error) => {
      console.error("Error fetching channel settings:", error);
      // Handle the error gracefully here, e.g., show a user-friendly message
    });
}

function checkForAddChannelOption(selectElement) {
  var addChannelDiv = document.getElementById("addChannelDiv");
  var channelConfigForm = document.getElementById("channelConfig");
  var deleteChannelBtn = document.getElementById("deleteChannelBtn");
  
  if (selectElement.value === "add_channel") {
    // Show add channel form, hide config form
    addChannelDiv.style.display = "block";
    if (channelConfigForm) {
      channelConfigForm.style.display = "none";
    }
    // Hide delete button when adding a new channel
    if (deleteChannelBtn) {
      deleteChannelBtn.style.display = "none";
    }
    
    // Hide send message button when adding a new channel
    const sendMessageBtn = document.getElementById("sendMessageBtn");
    if (sendMessageBtn) {
      sendMessageBtn.style.display = "none";
    }
  } else if (selectElement.value !== "") {
    // Load channel config
    addChannelDiv.style.display = "none";
    
    // Fetch channel settings
    fetch("/get-channel-settings/" + selectElement.value)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          console.error("Error loading channel settings:", data.error);
          return;
        }
        
        // Populate the form with channel data
        if (channelConfigForm) {
          channelConfigForm.style.display = "block";
          
          // Set checkbox values
          document.getElementById("ttsEnabled").checked = data.tts_enabled === 1;
          document.getElementById("voiceEnabled").checked = data.voice_enabled === 1;
          document.getElementById("joinChannel").checked = data.join_channel === 1;
          document.getElementById("useGeneralModel").checked = data.use_general_model === 1;
          
          // Set text field values
          document.getElementById("owner").value = data.owner || "";
          document.getElementById("trustedUsers").value = data.trusted_users || "";
          document.getElementById("ignoredUsers").value = data.ignored_users || "";
          document.getElementById("linesBetweenMessages").value = data.lines_between_messages || 0;
          document.getElementById("timeBetweenMessages").value = data.time_between_messages || 0;
          
          // Set Bark model if available
          if (document.getElementById("barkModel")) {
            const barkModelSelect = document.getElementById("barkModel");
            if (data.bark_model) {
              barkModelSelect.value = data.bark_model;
            } else {
              barkModelSelect.value = "regular"; // Default value
            }
          }
          
          // Set voice preset if available
          if (data.voice_preset) {
            const voicePresetSelect = document.getElementById("voicePreset");
            // Check if this is a built-in voice or custom voice
            if (data.voice_preset.startsWith('v2/')) {
              // Built-in voice
              voicePresetSelect.value = data.voice_preset;
              // Hide custom voice row
              document.getElementById("customVoiceRow").style.display = "none";
            } else {
              // Custom voice
              voicePresetSelect.value = "custom";
              // Show and populate custom voice row
              document.getElementById("customVoiceRow").style.display = "block"; // Changed from "" to "block"
              const customVoiceSelect = document.getElementById("customVoiceSelect");
              // Load custom voices if not already loaded
              if (customVoiceSelect.options.length <= 1 || !Array.from(customVoiceSelect.options).some(opt => opt.value === data.voice_preset)) {
                loadCustomVoices(data.voice_preset);
              } else {
                customVoiceSelect.value = data.voice_preset;
              }
            }
          } else {
             // Default voice preset if none is set
            const voicePresetSelect = document.getElementById("voicePreset");
            voicePresetSelect.value = "v2/en_speaker_0"; // A common default
            document.getElementById("customVoiceRow").style.display = "none";
          }
          
          // Show and update delete button for existing channels
          if (deleteChannelBtn) {
            deleteChannelBtn.style.display = "block";
            deleteChannelBtn.setAttribute("data-channel", selectElement.value);
            console.log("Delete button enabled for channel:", selectElement.value);
          }
          
          // Show and update send message button for existing channels
          const sendMessageBtn = document.getElementById("sendMessageBtn");
          if (sendMessageBtn) {
            sendMessageBtn.style.display = "block";
            sendMessageBtn.setAttribute("data-channel", selectElement.value);
            console.log("Send Message button enabled for channel:", selectElement.value);
            // Make sure it has the correct channel attribute for the event listener
            if (sendMessageBtn.getAttribute("data-channel") !== selectElement.value) {
              console.warn("Failed to set data-channel attribute, trying again");
              setTimeout(() => {
                sendMessageBtn.setAttribute("data-channel", selectElement.value);
                console.log("Send Message button data-channel re-set to:", sendMessageBtn.getAttribute("data-channel"));
              }, 50);
            }
          }
        }
      })
      .catch(error => {
        console.error("Error fetching channel settings:", error);
      });
  } else {
    // No channel selected, hide both forms
    addChannelDiv.style.display = "none";
    if (channelConfigForm) {
      channelConfigForm.style.display = "none";
    }
    // Hide delete button when no channel is selected
    if (deleteChannelBtn) {
      deleteChannelBtn.style.display = "none";
    }
    
    // Hide send message button when no channel is selected
    const sendMessageBtn = document.getElementById("sendMessageBtn");
    if (sendMessageBtn) {
      sendMessageBtn.style.display = "none";
    }
  }
}

// Function to load custom voices
function loadCustomVoices(selectedVoice) {
  fetch("/list-voices")
    .then(response => response.json())
    .then(data => {
      const voices = data.voices || [];
      const customVoiceSelect = document.getElementById("customVoiceSelect");
      
      // Clear existing options
      customVoiceSelect.innerHTML = '';
      
      // Add a default "Select Custom Voice" option if needed, or ensure it's there
      let placeholderOption = document.createElement('option');
      placeholderOption.value = ""; // Or a specific placeholder value
      placeholderOption.textContent = "Select Custom Voice...";
      placeholderOption.disabled = true;
      if (!selectedVoice || selectedVoice.startsWith('v2/')) { // Select placeholder if no custom voice is active
          placeholderOption.selected = true;
      }
      customVoiceSelect.appendChild(placeholderOption);

      // Add options for each voice
      voices.forEach(voice => {
        const voiceName = voice.replace('.npz', '');
        const option = document.createElement('option');
        option.value = voiceName;
        option.textContent = voiceName;
        customVoiceSelect.appendChild(option);
      });
      
      // Set selected voice if provided and it's a custom voice
      if (selectedVoice && !selectedVoice.startsWith('v2/')) {
        customVoiceSelect.value = selectedVoice;
      } else if (!selectedVoice) {
        // If no voice is selected (e.g. new channel), ensure placeholder is selected
        customVoiceSelect.value = "";
      }
    })
    .catch(error => {
      console.error("Error loading custom voices:", error);
    });
}

function handleError(error) {
  console.error("Error:", error);
  alert("An error occurred while saving settings.");
}

// Function to delete a channel
function deleteChannel(channelName) {
  if (!channelName) {
    displayNotification('No channel selected for deletion', 'error');
    return;
  }
  
  // Confirm with the user before deleting
  if (!confirm(`Are you sure you want to delete the channel "${channelName}"? This cannot be undone.`)) {
    return;
  }
  
  console.log(`Deleting channel: ${channelName}`);
  
  fetch("/delete-channel", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ channel_name: channelName }),
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success) {
        displayNotification(`Channel "${channelName}" deleted successfully`, 'success');
        
        // Reset the form first
        const channelSelect = document.getElementById("channelSelect");
        channelSelect.selectedIndex = 0; // Reset to "Select a channel..."
        
        // Hide configuration form
        const channelConfigForm = document.getElementById("channelConfig");
        if (channelConfigForm) {
          channelConfigForm.style.display = "none";
        }
        
        // Hide the delete button
        const deleteChannelBtn = document.getElementById("deleteChannelBtn");
        if (deleteChannelBtn) {
          deleteChannelBtn.style.display = "none";
        }
        
        // Clear the form state
        checkForAddChannelOption(channelSelect);
        
        // Finally refresh the channel list from the server
        setTimeout(() => {
          fetchChannels(); // Slight delay to ensure server has processed
        }, 200);
      } else {
        displayNotification(`Failed to delete channel: ${result.message}`, 'error');
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      displayNotification("An error occurred while deleting the channel", 'error');
    });
}

// Make sure this function is called on page load
document.addEventListener("DOMContentLoaded", function() {
  var channelSelect = document.getElementById("channelSelect");
  if (channelSelect) {
    fetchChannels(); // This will be handled by ChannelManager.init() if available
    // Ensure ChannelManager is initialized if it exists
    if (window.ChannelManager && typeof window.ChannelManager.init === 'function' && !window.ChannelManager.lastUpdated) {
        window.ChannelManager.init();
    }
  }
  
  // Set up delete channel button if it exists
  var deleteChannelBtn = document.getElementById("deleteChannelBtn");
  if (deleteChannelBtn) {
    deleteChannelBtn.addEventListener("click", function() {
      const channelToDelete = this.getAttribute("data-channel");
      deleteChannel(channelToDelete);
    });
  }
  
  // SINGLE EVENT HANDLER: Set up send message button programmatically
  var sendMessageBtn = document.getElementById("sendMessageBtn");
  if (sendMessageBtn) {
    console.log("Adding event listener to Send Message button on settings page");
    
    // First, remove any existing event listeners by cloning the button
    const newSendMessageBtn = sendMessageBtn.cloneNode(true);
    sendMessageBtn.parentNode.replaceChild(newSendMessageBtn, sendMessageBtn);
    sendMessageBtn = newSendMessageBtn; // Update reference to the new button
    
    // Then add our single event listener
    sendMessageBtn.addEventListener("click", function(event) {
      event.preventDefault();
      event.stopPropagation();
      
      const channelName = this.getAttribute("data-channel");
      console.log(`Send Message button clicked for channel: ${channelName}`);
      if (!channelName) {
        console.error("No channel name found in data-channel attribute for send message button");
        displayNotification("Error: No channel selected to send message to.", "error");
        return;
      }
      // Use the MessageManager from markov.js
      if (window.MessageManager && typeof window.MessageManager.generateMessage === 'function') {
        window.MessageManager.generateMessage({
            channel: channelName,
            sendToTwitch: true,
            button: this // Pass the button for UI updates
        });
      } else {
        console.error("MessageManager is not available.");
        displayNotification("Error: Message sending module not loaded.", "error");
      }
    });
    
    console.log("Send Message button (settings page) set up with single event handler using MessageManager");
  }
  
  // Set up voice preset change handler if not already defined
  // This should be handled by handle_voice.js, but as a fallback:
  if (typeof handleVoicePresetChange !== 'function') {
    window.handleVoicePresetChange = function() {
      const voicePresetSelect = document.getElementById("voicePreset");
      const customVoiceRow = document.getElementById("customVoiceRow");
      
      if (!voicePresetSelect || !customVoiceRow) return;

      if (voicePresetSelect.value === "custom") {
        customVoiceRow.style.display = "block"; // Changed from ""
        if (typeof loadCustomVoices === 'function') {
            loadCustomVoices();
        } else if (typeof fetchAndShowCustomVoices === 'function') { // from handle_voice.js
            fetchAndShowCustomVoices();
        }
      } else {
        customVoiceRow.style.display = "none";
      }
    }
    // Attach it if voicePreset element exists
    const voicePresetElement = document.getElementById("voicePreset");
    if (voicePresetElement) {
        voicePresetElement.addEventListener('change', window.handleVoicePresetChange);
        // Initial call to set visibility
        window.handleVoicePresetChange();
    }
  } else {
    // If handleVoicePresetChange is defined (likely from handle_voice.js), ensure it's called initially
     const voicePresetElement = document.getElementById("voicePreset");
     if (voicePresetElement) {
        handleVoicePresetChange(); // Call it to set initial state
     }
  }
});

function validateChannelForm() {
  // Get form elements
  const linesBetween = document.getElementById('linesBetweenMessages');
  const timeBetween = document.getElementById('timeBetweenMessages');
  
  // Validate numeric inputs
  if (linesBetween && (isNaN(parseInt(linesBetween.value)) || parseInt(linesBetween.value) < 0)) {
    alert('Lines between messages must be a non-negative number.');
    linesBetween.focus();
    return false;
  }
  
  if (timeBetween && (isNaN(parseInt(timeBetween.value)) || parseInt(timeBetween.value) < 0)) {
    alert('Time between messages must be a non-negative number.');
    timeBetween.focus();
    return false;
  }
  
  return true;
}
