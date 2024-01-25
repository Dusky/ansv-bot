let currentPage = 1; // Current page number
let lastId = 0; // Initialize with the ID of the last known entry
let originalChannelData = {};


setInterval(checkForUpdates, 30000);







function saveChannelSettings() {
    var selectedChannel = document.getElementById('channelSelect').value;
    var isAddChannel = selectedChannel === 'add_channel';
    var channelName = isAddChannel ? document.getElementById('newChannelName').value.trim() : selectedChannel;

    if (isAddChannel && !channelName) {
        alert('Please enter a channel name.');
        return;
    }

    var updatedData = {
        channel_name: channelName,
        tts_enabled: document.getElementById('ttsEnabled').checked ? 1 : 0,
        voice_enabled: document.getElementById('voiceEnabled').checked ? 1 : 0,
        join_channel: document.getElementById('joinChannel').checked ? 1 : 0,
        owner: document.getElementById('owner').value || channelName,
        trusted_users: document.getElementById('trustedUsers').value,
        ignored_users: document.getElementById('ignoredUsers').value,
        use_general_model: document.getElementById('useGeneralModel').checked ? 1 : 0,
        lines_between_messages: document.getElementById('linesBetweenMessages').value || 0,
        time_between_messages: document.getElementById('timeBetweenMessages').value || 0
    };

    if (isAddChannel) {
        addNewChannel(updatedData);
    } else {
        updateChannelSettings(updatedData);
    }
}

function updateChannelSettings(data) {
    fetch('/update-channel-settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            alert("Channel settings updated successfully.");
        } else {
            alert("Failed to update settings: " + result.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("An error occurred while updating settings.");
    });
}


function handleSaveResponse(data) {
  if(data.success) {
      alert("Settings saved successfully.");
  } else {
      alert("Failed to save settings: " + data.message);
  }
}

// Function to fetch paginated data
function fetchPaginatedData(page) {
  fetch(`/messages/${page}`)
    .then((response) => response.json())
    .then((data) => {
      if (page === 1) {
        initializeTable(data);
      } else {
        updateTable(data);
      }
    })
    .catch((error) => console.error("Error:", error));
}

function nextPage() {
    currentPage += 1;
    fetchPaginatedData(currentPage);
}

function previousPage() {
    if (currentPage > 1) {
        currentPage -= 1;
        fetchPaginatedData(currentPage);
    }
}


// Function to initialize the table with first page of data
function initializeTable(data) {
  let tableBody = document.getElementById("ttsFilesBody");
  tableBody.innerHTML = ""; // Clear the table
  data.forEach((file) => {
    addRowToTable(file);
  });
}


function updateTable(data) {
  let tableBody = document.getElementById("ttsFilesBody");
  let isNewData = false;

  data.forEach((file) => {
    // Convert message ID to integer for comparison
    let messageIdInt = parseInt(file[1]);

    if (messageIdInt > lastId) {
      addRowToTable(file, true); // Prepend new row
      lastId = messageIdInt; // Update lastId
      isNewData = true;
    }
  });

  return isNewData; // Return true if new data was added
}
function handleSaveResponse(data) {
  if(data.success) {
      alert("Settings saved successfully.");
  } else {
      alert("Failed to save settings: " + data.message);
  }
}

function handleError(error) {
  console.error('Error:', error);
  alert("An error occurred while saving settings.");
}

function checkForAddChannelOption(selectElement) {
    var addChannelDiv = document.getElementById('addChannelDiv');
    var channelConfigForm = document.getElementById('channelConfig');
    var newChannelNameInput = document.getElementById('newChannelName'); // Get the new channel name input

    if (selectElement.value === 'add_channel') {
        resetFormForNewChannel(); // Reset form fields for new channel
        addChannelDiv.style.display = 'block'; // Show the additional field for the new channel name
        newChannelNameInput.style.display = 'block'; // Ensure new channel name input is visible
        channelConfigForm.style.display = 'none'; // Hide the channel configuration form
    } else {
        addChannelDiv.style.display = 'none'; // Hide the additional field for the new channel name
        newChannelNameInput.style.display = 'none'; // Hide new channel name input
        channelConfigForm.style.display = 'block'; // Show the channel configuration form
        fetchChannelSettings(selectElement.value); // Fetch settings for the selected channel
    }
}

function addNewChannel(data) {
    fetch('/add-channel', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            alert("Channel added successfully.");
            // Optionally, dynamically update the channel list in the UI here
        } else {
            alert("Failed to add channel: " + result.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("An error occurred while adding the channel.");
    });
}



// Function to add a row to the table
function addRowToTable(file, prepend = false) {
  let tableBody = document.getElementById("ttsFilesBody");
  let row = `<tr>
                     <td>${file[0]}</td>
                     <td>${file[1]}</td>
                     <td>${file[2]}</td>
                     <td>${file[3]}</td>
                     <td>${file[5]}</td>
                     <td>
                         <audio controls id="audio-${file[1]}">
                             <source src="/static/${file[4]}" type="audio/wav">
                             Your browser does not support the audio element.
                         </audio>
                     </td>
                 </tr>`;
  if (prepend) {
    tableBody.innerHTML = row + tableBody.innerHTML;
  } else {
    tableBody.innerHTML += row;
  }
}

// Function to check if autoplay is enabled and play the latest file
function checkAutoplay(data) {
  let autoplayEnabled = document.getElementById("autoplay").checked;
  if (autoplayEnabled && data.length > 0) {
    let latestAudio = document.getElementById(`audio-${data[0][1]}`);
    if (latestAudio) {
      latestAudio.play();
    }
  }
}

// Function to check for updates and refresh the table if needed
function checkForUpdates() {
  fetch(`/check-updates/${lastId}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.newData) {
        let isNewDataAdded = updateTable(data.entries);
        if (isNewDataAdded) {
          checkAutoplay(data.entries);
        }
      }
    })
    .catch((error) => console.error("Error:", error));
}

function checkAutoplay(data) {
  let autoplayEnabled = document.getElementById("autoplay").checked;
  if (autoplayEnabled && data.length > 0) {
    let latestAudio = document.getElementById(`audio-${data[0][1]}`);
    if (latestAudio && !latestAudio.ended && latestAudio.paused) {
      latestAudio.play();
    }
  }
}

// Check for updates every 30 seconds
setInterval(checkForUpdates, 30000);

document.addEventListener("DOMContentLoaded", function () {
  // Initial fetch and table update
  fetchPaginatedData(currentPage);
});
document.addEventListener('DOMContentLoaded', function() {
    var settingsTab = document.getElementById('settingsTab');

    settingsTab.addEventListener('click', function() {
        fetch('/get-channels')
            .then(response => response.json())
            .then(data => {
                var channelSelect = document.getElementById('channelSelect');
                channelSelect.innerHTML = ''; // Clear existing options

                if (data && Array.isArray(data)) { // Check if data is an array
                    data.forEach(function(channel) {
                        var option = document.createElement('option');
                        option.value = channel[0]; // Assuming channel_name is the first element
                        option.text = channel[0];
                        channelSelect.appendChild(option);
                    });

                    var addChannelOption = document.createElement('option');
                    addChannelOption.value = 'add_channel';
                    addChannelOption.text = 'Add Channel';
                    channelSelect.appendChild(addChannelOption);

                    channelSelect.addEventListener('change', function() {
                        if (this.value === 'add_channel') {
                            checkForAddChannelOption(this);
                        } else {
                            displayChannelConfig(data, this.value);
                        }
                    });

                    checkForAddChannelOption(channelSelect);
                } else {
                    console.error('Error fetching channels: Invalid data format');
                }
            })
            .catch(error => {
                console.error('Error fetching channels:', error);
            });
    });
});

function displayChannelConfig(channels, selectedChannel) {
  var channelConfigForm = document.getElementById('channelConfig');
  var addChannelDiv = document.getElementById('addChannelDiv');

  if (selectedChannel === 'add_channel') {
      channelConfigForm.style.display = 'none';
      addChannelDiv.style.display = 'block';
  } else {
      var channelData = channels.find(c => c[0] === selectedChannel);
      if (channelData) {
          // Populate the form with existing channel data
          document.getElementById('ttsEnabled').checked = channelData[1] === 1;
          document.getElementById('voiceEnabled').checked = channelData[2] === 1;
          document.getElementById('joinChannel').checked = channelData[3] === 1;
          document.getElementById('owner').value = channelData[4] || '';
          document.getElementById('trustedUsers').value = channelData[5] || '';
          document.getElementById('ignoredUsers').value = channelData[6] || '';
          document.getElementById('useGeneralModel').checked = channelData[7] === 1;
          document.getElementById('linesBetweenMessages').value = channelData[8] || 0;
          document.getElementById('timeBetweenMessages').value = channelData[9] || 0;

          channelConfigForm.style.display = 'block';
          addChannelDiv.style.display = 'none';
      } else {
          channelConfigForm.style.display = 'none';
          addChannelDiv.style.display = 'none';
      }
  }
}

function checkForAddChannelOption(selectElement, channels) {
if (selectElement.value === 'add_channel') {
    // Reset form fields for new channel
    resetFormForNewChannel();
    document.getElementById('addChannelDiv').style.display = 'block';
} else {
    displayChannelConfig(channels, selectElement.value);
}
}
function resetFormForNewChannel() {
    // Clear the form and set default values for a new channel
    document.getElementById('ttsEnabled').checked = false;
    document.getElementById('voiceEnabled').checked = false;
    document.getElementById('joinChannel').checked = true;
    document.getElementById('owner').value = '';
    document.getElementById('trustedUsers').value = '';
    document.getElementById('ignoredUsers').value = '';
    document.getElementById('useGeneralModel').checked = true;
    document.getElementById('linesBetweenMessages').value = 100;
    document.getElementById('timeBetweenMessages').value = 0;
    document.getElementById('newChannelName').value = ''; // Clear the new channel name field
  }

function fetchChannels() {
    fetch('/get-channels')
        .then(response => response.json())
        .then(data => {
            var channelSelect = document.getElementById('channelSelect');
            channelSelect.innerHTML = ''; // Clear existing options

            // Re-add the default 'Select a channel...' option
            var defaultOption = document.createElement('option');
            defaultOption.value = "";
            defaultOption.text = "Select a channel...";
            defaultOption.disabled = true;
            defaultOption.selected = true;
            channelSelect.appendChild(defaultOption);

            // Append other channel options
            data.forEach(channel => {
                var option = document.createElement('option');
                option.value = channel[0];
                option.text = channel[0];
                channelSelect.appendChild(option);
            });

            // Add 'Add Channel' option
            var addChannelOption = document.createElement('option');
            addChannelOption.value = 'add_channel';
            addChannelOption.text = 'Add Channel';
            channelSelect.appendChild(addChannelOption);
        })
        .catch(error => console.error('Error fetching channels:', error));
}



function fetchChannelSettings(channelName) {
    // Fetch settings for the selected channel and update the form
    fetch('/get-channel-settings/' + encodeURIComponent(channelName))
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data) {
                document.getElementById('ttsEnabled').checked = data.tts_enabled === 1;
                document.getElementById('voiceEnabled').checked = data.voice_enabled === 1;
                document.getElementById('joinChannel').checked = data.join_channel === 1;
                document.getElementById('owner').value = data.owner || '';
                document.getElementById('trustedUsers').value = data.trusted_users || '';
                document.getElementById('ignoredUsers').value = data.ignored_users || '';
                document.getElementById('useGeneralModel').checked = data.use_general_model === 1;
                document.getElementById('linesBetweenMessages').value = data.lines_between_messages || 100;
                document.getElementById('timeBetweenMessages').value = data.time_between_messages || 0;
            }
        })
        .catch(error => {
            console.error('Error fetching channel settings:', error);
            // Handle the error gracefully here, e.g., show a user-friendly message
        });
}
function setActiveTab(activeTab) {
    const tabs = ['mainTab', 'settingsTab', 'markovTab']; // Add all tab IDs here
    const contents = ['mainContent', 'settingsContent', 'markovContent']; // Add all content IDs here

    tabs.forEach(tab => {
        document.getElementById(tab).classList.remove('active');
    });
    contents.forEach(content => {
        document.getElementById(content).style.display = 'none';
    });

    activeTab.classList.add('active');
    document.getElementById(activeTab.id.replace('Tab', 'Content')).style.display = 'block';
}
document.addEventListener("DOMContentLoaded", function () {
    var mainTab = document.getElementById("mainTab");
    var settingsTab = document.getElementById("settingsTab");
    var mainContent = document.getElementById("mainContent");
    var settingsContent = document.getElementById("settingsContent");

    var markovTab = document.getElementById('markovTab'); // Ensure you have a corresponding element with this ID

    mainTab.addEventListener("click", function () {
        setActiveTab(this);
    });

    settingsTab.addEventListener("click", function () {
        setActiveTab(this);
    });

    if (markovTab) {
        markovTab.addEventListener('click', function() {
            setActiveTab(this);
        });
    }

    var saveSettingsButton = document.getElementById('saveSettings');
    saveSettingsButton.addEventListener('click', function(event) {
        event.preventDefault(); // Prevent the default form submission
        saveChannelSettings(); // Call the saveChannelSettings function
    });


    var addChannelSaveButton = document.getElementById('addChannelSave');
    addChannelSaveButton.addEventListener('click', function() {
        var newChannelName = document.getElementById('newChannelName').value;
        if(newChannelName) {
            var newChannelData = {
                channel_name: newChannelName,
                tts_enabled: 0, // Default values for a new channel
                voice_enabled: 0,
                join_channel: 1,
                owner: newChannelName,
                trusted_users: '',
                ignored_users: '',
                use_general_model: 1,
                lines_between_messages: 100,
                time_between_messages: 0
            };
            addNewChannel(newChannelData); // Call addNewChannel instead of saveOrUpdateChannel
        } else {
            alert("Please enter a channel name.");
        }
    });


    function saveOrUpdateChannel(data) {
        console.log("Saving channel settings:", data);
    
        fetch('/save-channel-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            console.log("Response from server:", data);
            if (data.success) {
                alert("Settings saved successfully.");
                location.reload(); // Reload to update the channel list
            } else {
                alert("Failed to save settings.");
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert("An error occurred while saving settings.");
        });
    }

    mainTab.addEventListener("click", function () {
        mainContent.style.display = "block";
        settingsContent.style.display = "none";
        mainTab.classList.add("active");
        settingsTab.classList.remove("active");
    });

    settingsTab.addEventListener("click", function () {
        mainContent.style.display = "none";
        settingsContent.style.display = "block";
        settingsTab.classList.add("active");
        mainTab.classList.remove("active");

        fetchChannels();
    });


// Fetch paginated data for the main tab
fetchPaginatedData(currentPage);
});

function fetchChannelStats() {
    fetch('/get-channel-stats')
        .then(response => response.json())
        .then(data => {
            let tableBody = document.getElementById("channelStatsBody");
            tableBody.innerHTML = ""; // Clear previous data

            data.forEach(channel => {
                let row = `<tr>
                               <td>${channel[0]}</td>
                               <td>${channel[1]}</td>
                               <td>${channel[2]}</td>
                           </tr>`;
                tableBody.innerHTML += row;
            });
        })
        .catch(error => console.error("Error fetching channel stats:", error));
}

document.getElementById('markovTab').addEventListener('click', function() {
    fetchChannelStats(); // Fetch and display stats when Markov tab is clicked
});