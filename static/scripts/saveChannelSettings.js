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
    bark_model: document.getElementById("barkModel").value
  };

  if (isAddChannel) {
    addNewChannel(updatedData, function() {
      // Reload channel list without full page refresh
      fetchChannels();
      // Reset the form
      document.getElementById("channelSelect").selectedIndex = 0;
      checkForAddChannelOption(document.getElementById("channelSelect"));
      
      showToast('Channel added successfully!', 'success');
    });
  } else {
    updateChannelSettings(updatedData, function() {
      showToast('Settings saved successfully!', 'success');
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
    showToast("Settings saved successfully.", "success");
  } else {
    showToast("Failed to save settings: " + data.message, "error");
  }
}

// Toast function if not already defined
function showToast(message, type = "info") {
  // Check if the notification.js showToast function exists
  if (typeof window.showToast === "function") {
    window.showToast(message, type);
  } else {
    // Fallback to alert if toast function not available
    alert(message);
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

  if (selectedChannel === "add_channel") {
    channelConfigForm.style.display = "none";
    addChannelDiv.style.display = "block";
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
    } else {
      channelConfigForm.style.display = "none";
      addChannelDiv.style.display = "none";
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


function fetchChannels() {
  fetch("/get-channels")
    .then((response) => response.json())
    .then((channels) => {
      let channelSelect = document.getElementById("channelSelect");
      if (channelSelect) {
        // Clear existing options except the first two
        while (channelSelect.options.length > 2) {
          channelSelect.remove(2);
        }
        
        // Debug the received data
        console.log("Received channels data:", channels);
        
        // Add channel options
        channels.forEach((channel) => {
          let option = document.createElement("option");
          
          // Handle various possible formats
          if (Array.isArray(channel)) {
            option.value = channel[0];
            option.text = channel[0];
          } else if (typeof channel === 'object' && channel !== null) {
            // Check for 'name' property
            if (channel.name) {
              option.value = channel.name;
              option.text = channel.name;
            } else if (channel.channel_name) {
              // Fallback to channel_name if present
              option.value = channel.channel_name;
              option.text = channel.channel_name;
            } else {
              // Last fallback: use first property if available
              const firstKey = Object.keys(channel)[0];
              if (firstKey) {
                option.value = channel[firstKey];
                option.text = channel[firstKey];
                console.warn("Using fallback property for channel name:", firstKey);
              } else {
                console.warn("Unknown channel data format:", channel);
              }
            }
          } else if (typeof channel === 'string') {
            // Simple string value
            option.value = channel;
            option.text = channel;
          } else {
            console.warn("Unrecognized channel data type:", typeof channel, channel);
          }
          
          // Only add if we got a valid value and it's not "undefined"
          if (option.value && option.value !== "undefined" && option.text !== "undefined") {
            channelSelect.add(option);
          }
        });
      }
    })
    .catch((error) => {
      console.error("Error fetching channels:", error);
    });
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
  
  if (selectElement.value === "add_channel") {
    // Show add channel form, hide config form
    addChannelDiv.style.display = "block";
    if (channelConfigForm) {
      channelConfigForm.style.display = "none";
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
          if (data.bark_model) {
            const barkModelSelect = document.getElementById("barkModel");
            barkModelSelect.value = data.bark_model;
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
              document.getElementById("customVoiceRow").style.display = "block";
              const customVoiceSelect = document.getElementById("customVoiceSelect");
              // Load custom voices if not already loaded
              if (customVoiceSelect.options.length <= 1) {
                loadCustomVoices(data.voice_preset);
              } else {
                customVoiceSelect.value = data.voice_preset;
              }
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
      
      // Add options for each voice
      voices.forEach(voice => {
        const voiceName = voice.replace('.npz', '');
        const option = document.createElement('option');
        option.value = voiceName;
        option.textContent = voiceName;
        customVoiceSelect.appendChild(option);
      });
      
      // Set selected voice if provided
      if (selectedVoice && !selectedVoice.startsWith('v2/')) {
        customVoiceSelect.value = selectedVoice;
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

// Make sure this function is called on page load
document.addEventListener("DOMContentLoaded", function() {
  var channelSelect = document.getElementById("channelSelect");
  if (channelSelect) {
    fetchChannels();
  }
  
  // Set up voice preset change handler if not already defined
  if (typeof handleVoicePresetChange !== 'function') {
    window.handleVoicePresetChange = function() {
      const voicePresetSelect = document.getElementById("voicePreset");
      const customVoiceRow = document.getElementById("customVoiceRow");
      
      if (voicePresetSelect.value === "custom") {
        customVoiceRow.style.display = "block";
        loadCustomVoices();
      } else {
        customVoiceRow.style.display = "none";
      }
    }
  }
});

function validateChannelForm() {
  // Get form elements
  const linesBetween = document.getElementById('linesBetweenMessages');
  const timeBetween = document.getElementById('timeBetweenMessages');
  
  // Validate numeric inputs
  if (linesBetween && isNaN(parseInt(linesBetween.value))) {
    alert('Lines between messages must be a number');
    linesBetween.focus();
    return false;
  }
  
  if (timeBetween && isNaN(parseInt(timeBetween.value))) {
    alert('Time between messages must be a number');
    timeBetween.focus();
    return false;
  }
  
  return true;
}

