let lastId = 0;

function updateTable(data) {
  console.log("Updating table with data:", data);
  let tableBody = document.getElementById("ttsFilesBody");
  let isNewData = false;

  // Check if data exists and is not empty
  if (!data || !Array.isArray(data) || data.length === 0) {
    console.log("No data to update");
    return false;
  }

  data.forEach((file) => {
    let messageIdInt = parseInt(file[1]);
    console.log(`Processing messageIdInt: ${messageIdInt}, lastId: ${lastId}`);
    if (messageIdInt > lastId) {
      addRowToTable(file, true);
      isNewData = true;
    }
  });

  if (isNewData && data.length > 0) {
    lastId = parseInt(data[0][1]); 
  }

  return isNewData;
}

// Function to add a row to the table
function addRowToTable(file, prepend = false) {
  let tableBody = document.getElementById("ttsFilesBody");
  let audioSrc = `/static/${file[4]}`;
  let audioId = `audio-${file[1]}`;
  console.log(`Adding new row with audio ID: ${audioId}`);
  let row = `<tr>
                   <td>${file[0]}</td>
                   <td>${file[2]}</td>
                   <td>${file[3]}</td>
                   <td>${file[5]}</td>
                   <td class="text-center">
                       <button onclick="playAudio('${audioSrc}')" class="btn btn-outline-primary btn-sm" data-tooltip="Play Audio">
                           <i class="fa fa-play"></i>
                       </button>
                    </td>
                    <td class="text-center">
                       <a href="${audioSrc}" download class="btn btn-outline-secondary btn-sm" data-tooltip="Download Audio">
                           <i class="fa fa-download"></i>
                       </a>
                    
                   </td>
               </tr>`;

  if (prepend) {
    tableBody.insertAdjacentHTML("afterbegin", row);
  } else {
    tableBody.insertAdjacentHTML("beforeend", row);
  }

  setTimeout(() => {
    checkAutoplay([file]);
  }, 100); 
}
function addLatestRow() {
  fetch("/latest-messages")
    .then((response) => response.json())
    .then((data) => {
      if (data && data.length > 0) {
        let latestData = data[0];
        addRowToTable(latestData, true);
        setTimeout(() => {
          if (document.getElementById("autoplay").checked) {
            playAudio(`/static/${latestData[4]}`);
          }
        }, 100);
      }
    })
    .catch((error) => console.error("Error fetching latest data:", error));
}

// Function to play audio
function playAudio(src) {
  let audio = new Audio(src);
  audio.play().catch((error) => console.error("Play error:", error));
}

// Function to check if autoplay is enabled and play the latest file
function checkAutoplay(data) {
  // Get the autoplay checkbox element
  const autoplayCheckbox = document.getElementById("autoplay");
  
  // Check if element exists and if autoplay is enabled
  if (!autoplayCheckbox) {
    console.log("Autoplay checkbox not found");
    return;
  }
  
  const autoplayEnabled = autoplayCheckbox.checked;

  // Check if we have data and autoplay is enabled
  if (autoplayEnabled && data && Array.isArray(data) && data.length > 0) {
    // Construct the audio URL directly instead of finding an element
    const channel = data[0][0]; // channel name
    const timestamp = data[0][2]; // timestamp
    const audioPath = `/static/outputs/${channel}/${channel}-${timestamp}.wav`;
    
    console.log(`Attempting to autoplay: ${audioPath}`);
    
    // Create audio element programmatically
    const audioPlayer = new Audio(audioPath);
    audioPlayer.muted = true; // Start muted to comply with autoplay policies
    
    audioPlayer.play()
      .then(() => {
        console.log("Autoplay started");
        audioPlayer.muted = false; // Unmute after successfully starting
      })
      .catch((error) => {
        console.error("Autoplay failed:", error);
      });
  }
}

function refreshTable() {
    currentPage = 1;  // Assuming currentPage is declared elsewhere in your script
    const tableBody = document.getElementById("ttsFilesBody");
    if (tableBody) {
        tableBody.innerHTML = "";
        loadMoreData(); // Load the initial set of data
    } else {
    }
}


let currentPage = 1;
let totalPages = 0;

function loadMoreData() {
  fetch(`/messages/${currentPage}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.items && data.items.length > 0) {
        data.items.forEach((file) => {
          addRowToTable(file); // Append new rows to the table
        });
        lastId = parseInt(data.items[data.items.length - 1][1]); // Update lastId to the ID of the last item
        currentPage++; // Increment page number after successful data fetch
      } else {
        // No more data or an empty response
        document.getElementById("loadMore").disabled = true; // Disable the button
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      document.getElementById("loadMore").disabled = true; // Disable the button in case of an error
    });
}

function loadLatestData() {
  fetch("/latest-messages")
    .then((response) => response.json())
    .then((data) => {
      if (data && data.length > 0) {
        let latestMessageId = parseInt(data[0][1]);
        if (latestMessageId > lastId) {
          addRowToTable(data[0], true); // Append only the latest row
          lastId = latestMessageId;
        }
      }
    })
    .catch((error) => {
      console.error("Error:", error);
    });
}

// Function to populate the channel selector in Generate Message section
function populateMessageChannels() {
    fetch('/get-channels')
        .then(response => response.json())
        .then(channels => {
            const selector = document.getElementById('channelForMessage');
            if (selector) {
                // Clear existing options
                selector.innerHTML = '';
                
                // Add channels to dropdown
                channels.forEach(channel => {
                    const option = document.createElement('option');
                    option.value = channel[0];
                    option.textContent = channel[0];
                    selector.appendChild(option);
                });
                
                // If no channels, add a placeholder
                if (channels.length === 0) {
                    const option = document.createElement('option');
                    option.disabled = true;
                    option.textContent = 'No channels available';
                    selector.appendChild(option);
                }
            }
        })
        .catch(error => console.error('Error loading channels for message generation:', error));
}

// Update the generateMessage function to use the selected channel
function generateMessage() {
    const modelSelect = document.getElementById('modelSelector');
    const channelSelect = document.getElementById('channelForMessage');
    const messageContainer = document.getElementById('generatedMessageContainer');
    const messageElement = document.getElementById('generatedMessage');
    
    // Show loading state
    messageContainer.classList.remove('d-none');
    messageElement.innerHTML = 'Generating message...';
    
    // Get selected values
    const model = modelSelect.value;
    const channel = channelSelect.value;
    
    fetch('/generate-message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ model: model, channel: channel })
    })
    .then(response => response.json())
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

// Function to check bot status and update UI
function checkBotStatus() {
    fetch('/api/bot-status')
        .then(response => response.json())
        .then(data => {
            const statusIndicator = document.getElementById('botStatusIndicator');
            if (statusIndicator) {
                if (data.running) {
                    statusIndicator.innerHTML = '<span class="badge bg-success">Running</span>';
                } else {
                    statusIndicator.innerHTML = '<span class="badge bg-danger">Stopped</span>';
                }
            }
        })
        .catch(error => {
            console.error('Error checking bot status:', error);
            const statusIndicator = document.getElementById('botStatusIndicator');
            if (statusIndicator) {
                statusIndicator.innerHTML = '<span class="badge bg-warning">Unknown</span>';
            }
        });
}

// Call this function when page loads and periodically
document.addEventListener('DOMContentLoaded', function() {
    // Check immediately
    checkBotStatus();
    
    // Then check every 10 seconds
    setInterval(checkBotStatus, 10000);
});

function showLoading() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.style.display = 'flex';
}

function hideLoading() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.style.display = 'none';
}

// Auto-refresh stats data periodically
function setupStatsAutoRefresh() {
  const statsContainer = document.getElementById('statsContainer');
  if (statsContainer) {
    try {
      // Initial load - try multiple function names in order of preference
      if (typeof window.loadStatistics === 'function') {
        console.log("Using loadStatistics from stats.js");
        window.loadStatistics();
      } else if (typeof window.eventListenerLoadStats === 'function') {
        console.log("Using eventListenerLoadStats from event_listener.js");
        window.eventListenerLoadStats();
      } else if (typeof window.loadStats === 'function') {
        console.log("Using loadStats function");
        window.loadStats();
      } else {
        console.warn("No stats loading function found in window scope!");
        
        // Last resort - try to define a local version that calls updateChannelCount
        if (typeof window.updateChannelCount === 'function') {
          console.log("Only updateChannelCount is available, using that");
          window.updateChannelCount();
        }
      }
      
      // Refresh every 2 minutes with the best available function
      setInterval(function() {
        console.log("Auto-refreshing stats...");
        if (typeof window.loadStatistics === 'function') {
          window.loadStatistics();
        } else if (typeof window.eventListenerLoadStats === 'function') {
          window.eventListenerLoadStats();
        } else if (typeof window.loadStats === 'function') {
          window.loadStats();
        } else if (typeof window.updateChannelCount === 'function') {
          window.updateChannelCount();
        }
      }, 120000);
    } catch (error) {
      console.error("Error in setupStatsAutoRefresh:", error);
    }
  }
}

// Call this from your DOMContentLoaded event
document.addEventListener('DOMContentLoaded', function() {
  console.log("data_handler.js: Setting up stats auto-refresh");
  // Use a longer delay to ensure all other scripts are loaded
  setTimeout(setupStatsAutoRefresh, 1500);
});


