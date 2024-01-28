function saveChannelSettings() {
  var selectedChannel = document.getElementById("channelSelect").value;
  var isAddChannel = selectedChannel === "add_channel";
  var channelName = isAddChannel
    ? document.getElementById("newChannelName").value.trim()
    : selectedChannel;

  if (isAddChannel && !channelName) {
    alert("Please enter a channel name.");
    return;
  }

  var updatedData = {
    channel_name: channelName,
    tts_enabled: document.getElementById("ttsEnabled").checked ? 1 : 0,
    voice_enabled: document.getElementById("voiceEnabled").checked ? 1 : 0,
    join_channel: document.getElementById("joinChannel").checked ? 1 : 0,
    owner: document.getElementById("owner").value || channelName,
    trusted_users: document.getElementById("trustedUsers").value,
    ignored_users: document.getElementById("ignoredUsers").value,
    use_general_model: document.getElementById("useGeneralModel").checked
      ? 1
      : 0,
    lines_between_messages:
      document.getElementById("linesBetweenMessages").value || 0,
    time_between_messages:
      document.getElementById("timeBetweenMessages").value || 0,
    voice_preset: document.getElementById("voicePreset").value
  };

  if (isAddChannel) {
    addNewChannel(updatedData);
  } else {
    updateChannelSettings(updatedData);
  }
}
function updateChannelSettings(data) {
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
        alert("Channel settings updated successfully.");
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
    alert("Settings saved successfully.");
  } else {
    alert("Failed to save settings: " + data.message);
  }
}
function addNewChannel(data) {
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
        alert("Channel added successfully.");
        // Optionally, dynamically update the channel list in the UI here
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

// function checkForAddChannelOption(selectElement, channels) {
// if (selectElement.value === "add_channel") {
//     // Reset form fields for new channel
//     resetFormForNewChannel();
//     document.getElementById("addChannelDiv").style.display = "block";
// } else {
//     displayChannelConfig(channels, selectElement.value);
// }
// }


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
    .then((data) => {
      var channelSelect = document.getElementById("channelSelect");
      channelSelect.innerHTML = ""; // Clear existing options

      // Re-add the default 'Select a channel...' option
      var defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.text = "Select a channel...";
      defaultOption.disabled = true;
      defaultOption.selected = true;
      channelSelect.appendChild(defaultOption);

      // Append other channel options
      data.forEach((channel) => {
        var option = document.createElement("option");
        option.value = channel[0];
        option.text = channel[0];
        channelSelect.appendChild(option);
      });

      // Add 'Add Channel' option
      var addChannelOption = document.createElement("option");
      addChannelOption.value = "add_channel";
      addChannelOption.text = "Add Channel";
      channelSelect.appendChild(addChannelOption);
    })
    .catch((error) => console.error("Error fetching channels:", error));
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
  var newChannelNameInput = document.getElementById("newChannelName"); // Get the new channel name input

  if (selectElement.value === "add_channel") {
    resetFormForNewChannel(); // Reset form fields for new channel
    addChannelDiv.style.display = "block"; // Show the additional field for the new channel name
    newChannelNameInput.style.display = "block"; // Ensure new channel name input is visible
    channelConfigForm.style.display = "none"; // Hide the channel configuration form
  } else {
    addChannelDiv.style.display = "none"; // Hide the additional field for the new channel name
    newChannelNameInput.style.display = "none"; // Hide new channel name input
    channelConfigForm.style.display = "block"; // Show the channel configuration form
    fetchChannelSettings(selectElement.value); // Fetch settings for the selected channel
  }
}

function handleError(error) {
  console.error("Error:", error);
  alert("An error occurred while saving settings.");
}
