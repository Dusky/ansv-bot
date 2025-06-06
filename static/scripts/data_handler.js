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
  
  // Check if file exists and file[4] (file_path) exists
  if (!file || !file[4]) {
    console.warn("Invalid file data for table row:", file);
    return;
  }
  
  // Process the audio source path correctly
  let audioSrc = '';
  
  // Check if the path already includes "/static/"
  if (file[4].startsWith('static/')) {
    audioSrc = `/${file[4]}`;
  } else {
    audioSrc = `/static/${file[4]}`;
  }
  
  // Fix double static in path if present
  audioSrc = audioSrc.replace('/static/static/', '/static/');
  
  let audioId = `audio-${file[1]}`;
  console.log(`Adding new row with audio ID: ${audioId} - Path: ${audioSrc}`);
  
  // Use playAudioIfExists to check file existence first
  let row = `<tr>
                   <td>${file[0]}</td>
                   <td>${file[2]}</td>
                   <td>${file[3] || 'Default'}</td>
                   <td>${file[5] || ''}</td>
                   <td class="text-center">
                       <button onclick="playAudioIfExists('${audioSrc}')" class="btn btn-outline-primary btn-sm" data-tooltip="Play Audio">
                           <i class="fa fa-play"></i>
                       </button>
                    </td>
                    <td class="text-center">
                       <a href="${audioSrc}" download="${audioSrc.split('/').pop()}" class="btn btn-outline-secondary btn-sm" data-tooltip="Download Audio">
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
            let audioSrc = `/static/${latestData[4]}`;
            // Fix double static in path if present
            audioSrc = audioSrc.replace('/static/static/', '/static/');
            playAudio(audioSrc);
          }
        }, 100);
      }
    })
    .catch((error) => console.error("Error fetching latest data:", error));
}

// Function to play audio - use the safer version that checks for existence
function playAudio(src) {
  // Use our safer function that first checks if the file exists
  playAudioIfExists(src);
}

// Function to safely display a toast message without recursion
function safeShowMessage(message, type = 'info') {
  console.log(`[${type}] ${message}`);
  
  // Attempt to use Bootstrap toast if available
  try {
    let container = document.getElementById('toastContainer');
    if (container && typeof bootstrap !== 'undefined') {
      // Create a simple toast with Bootstrap
      const toastId = 'toast-' + Date.now();
      const bgClass = (type === 'error') ? 'bg-danger' : 
                      (type === 'success') ? 'bg-success' :
                      (type === 'warning') ? 'bg-warning' : 'bg-info';
                      
      const toastHTML = `
        <div id="${toastId}" class="toast align-items-center ${bgClass} text-white border-0" role="alert" aria-live="assertive" aria-atomic="true">
          <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
          </div>
        </div>
      `;
      container.insertAdjacentHTML('beforeend', toastHTML);
      
      // Initialize and show toast
      const toastElement = document.getElementById(toastId);
      const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
      toast.show();
      
      // Clean up DOM after toast is hidden
      toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
      });
      
      return;
    }
  } catch (e) {
    console.error('Error showing toast via bootstrap:', e);
  }
  
  // Fallback to alert for critical errors only
  if (type === 'error') {
    alert(`Error: ${message}`);
  }
}

// Function to check if an audio file exists before playing it
window.playAudioIfExists = function(src) {
  // Fix double static in path if present
  src = src.replace('/static/static/', '/static/');
  
  // First check if the file exists
  fetch(src, { method: 'HEAD' })
    .then(response => {
      if (response.ok) {
        // File exists, play it
        let audio = new Audio(src);
        audio.play()
          .then(() => console.log("Audio playing:", src))
          .catch(error => {
            console.error("Play error:", error);
            // Use the namespaced version to avoid circular references
            window.notificationSystem.showToast("Browser blocked audio playback. Try clicking again.", "warning");
          });
      } else {
        console.warn(`Audio file not found: ${src}`);
        window.notificationSystem.showToast("Audio file not found. It may have been deleted or moved.", "warning");
      }
    })
    .catch(error => {
      console.error("Error checking audio file:", error);
      window.notificationSystem.showToast("Error accessing audio file", "error");
    });
}

// Function to check if autoplay is enabled and play the latest file
function checkAutoplay(data) {
  // Autoplay is problematic in modern browsers due to policies
  // Instead of attempting autoplay, we'll just skip it to avoid errors
  
  // Get the autoplay checkbox element
  const autoplayCheckbox = document.getElementById("autoplay");
  
  // Check if element exists and if autoplay is enabled
  if (!autoplayCheckbox || !autoplayCheckbox.checked) {
    return;
  }
  
  // Skip autoplay to avoid browser policy errors
  console.log("Skipping autoplay due to browser policies");
  
  // Optional: Consider showing a UI message that autoplay is disabled
  // showToast("Autoplay is disabled due to browser policy. Please click Play buttons manually.", "info");
}

// Refreshes the TTS table with the latest data
// Making this globally available for other scripts
window.refreshTable = function() {
    console.log("Refreshing TTS table...");
    currentPage = 1;  // Reset to first page
    const tableBody = document.getElementById("ttsFilesBody");
    if (tableBody) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center">Loading messages...</td></tr>'; // Updated colspan to 6
        loadMoreData(); // Load the initial set of data
        
        // Update last refreshed indicator
        const statusLastUpdated = document.getElementById('statusLastUpdated');
        if (statusLastUpdated) {
            statusLastUpdated.textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        }
    } else {
        console.log("TTS table body not found");
    }
};

// For compatibility with existing code
function refreshTable() {
    window.refreshTable();
}

// Make sure notification system is properly integrated
// Setup our namespaced functions first if not already defined
window.notificationSystem = window.notificationSystem || {};
if (typeof window.notificationSystem.showToast !== 'function') {
    // Use our safe internal version for the namespace
    window.notificationSystem.showToast = safeShowMessage;
    
    // Set the global reference to point to our namespaced function 
    window.showToast = window.notificationSystem.showToast;
}

// Function to flush TTS entries that don't have valid audio files
window.flushTTSEntries = function() {
    // Show confirmation dialog
    if (!confirm("This will remove all TTS entries with missing audio files. Continue?")) {
        return;
    }
    
    // Show loading state
    const flushBtn = document.getElementById('flushTTSBtn');
    if (flushBtn) {
        flushBtn.disabled = true;
        flushBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
    }
    
    // Call API to flush entries
    fetch('/api/flush-tts-entries', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Show success message
            window.notificationSystem.showToast(`${data.message}`, 'success');
            
            // Refresh table after cleanup
            setTimeout(() => {
                if (window.refreshTable) {
                    window.refreshTable();
                }
            }, 1000);
        } else {
            window.notificationSystem.showToast(`Error: ${data.error || 'Unknown error'}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error flushing TTS entries:', error);
        window.notificationSystem.showToast(`Error: ${error.message}`, 'error');
    })
    .finally(() => {
        // Reset button state
        if (flushBtn) {
            flushBtn.disabled = false;
            flushBtn.innerHTML = '<i class="fas fa-trash-alt me-1"></i>Clean Up';
        }
    });
};


let currentPage = 1;
let totalPages = 0;

function loadMoreData() {
  fetch(`/messages/${currentPage}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.items && data.items.length > 0) {
        // Remove any loading indicator
        const tableBody = document.getElementById("ttsFilesBody");
        if (tableBody && tableBody.innerHTML.includes('Loading messages...')) {
          tableBody.innerHTML = '';
        }
        
        // Add each TTS entry
        data.items.forEach((file) => {
          // Skip if file data is invalid
          if (!file || !Array.isArray(file) || file.length < 5) {
            console.warn("Skipping invalid file data:", file);
            return;
          }
          
          addRowToTable(file); // Append new rows to the table
        });
        
        // Update lastId and increment page
        if (data.items.length > 0 && data.items[data.items.length - 1][1]) {
          lastId = parseInt(data.items[data.items.length - 1][1]);
          currentPage++; // Increment page number after successful data fetch
        }
        
        // If fewer items than expected, we might be at the end
        const loadMoreBtn = document.getElementById("loadMore");
        if (loadMoreBtn && data.items.length < 10) { // Assuming 10 items per page
          loadMoreBtn.disabled = true;
          loadMoreBtn.textContent = "No more messages";
        } else if (loadMoreBtn) {
          loadMoreBtn.disabled = false; // Re-enable if more data might be available
        }
      } else {
        // No more data or an empty response
        const loadMoreBtn = document.getElementById("loadMore");
        if (loadMoreBtn) {
          loadMoreBtn.disabled = true;
          loadMoreBtn.textContent = "No more messages";
        }
        
        // If empty on first page, show message
        if (currentPage === 1) {
          const tableBody = document.getElementById("ttsFilesBody");
          if (tableBody) {
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No TTS messages found</td></tr>'; // Updated colspan
          }
        }
      }
    })
    .catch((error) => {
      console.error("Error loading TTS data:", error);
      
      const loadMoreBtn = document.getElementById("loadMore");
      if (loadMoreBtn) {
        loadMoreBtn.disabled = true;
        loadMoreBtn.textContent = "Error loading data";
      }
      
      // Show error in the table if it's empty
      const tableBody = document.getElementById("ttsFilesBody");
      if (tableBody && currentPage === 1) {
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Error loading TTS data: ${error.message}</td></tr>`; // Updated colspan
      }
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
    fetch('/api/channels') // Use the consistent /api/channels endpoint
        .then(response => response.json())
        .then(channelsData => {
            const selector = document.getElementById('channelForMessage');
            if (selector) {
                selector.innerHTML = ''; // Clear existing options
                
                if (channelsData && channelsData.length > 0) {
                    channelsData.forEach(channel => {
                        const option = document.createElement('option');
                        option.value = channel.name; // API returns objects with 'name'
                        option.textContent = channel.name;
                        selector.appendChild(option);
                    });
                } else {
                    const option = document.createElement('option');
                    option.disabled = true;
                    option.selected = true;
                    option.textContent = 'No channels available';
                    selector.appendChild(option);
                }
            }
        })
        .catch(error => console.error('Error loading channels for message generation:', error));
}

// Primary implementation of generateMessage function
function generateMessage() {
    const modelSelect = document.getElementById('modelSelector');
    const channelSelect = document.getElementById('channelForMessage');
    const messageContainer = document.getElementById('generatedMessageContainer');
    const messageElement = document.getElementById('generatedMessage');
    const generateBtn = document.getElementById('generateMsgBtn');
    
    if (!modelSelect || !messageContainer || !messageElement) {
        console.error("Required DOM elements for message generation not found");
        if (window.MessageManager) {
            window.MessageManager.showNotification("UI Error: Message generation elements missing.", "error");
        }
        return;
    }
    
    const model = modelSelect.value;
    const channel = channelSelect && channelSelect.value ? channelSelect.value : null;
    
    messageContainer.classList.remove('d-none'); // Show container immediately
    messageElement.innerHTML = '<i>Generating message...</i>'; // Initial text

    if (window.MessageManager && typeof window.MessageManager.generateMessage === 'function') {
        window.MessageManager.generateMessage({
            model: model,
            channel: channel,
            button: generateBtn, // Pass the button for MessageManager to handle its state
            callback: function(generatedMessage, data) {
                // This callback updates the UI once MessageManager is done
                if (generatedMessage) {
                    messageElement.textContent = generatedMessage;
                } else {
                    messageElement.textContent = data.error || 'Failed to generate message.';
                }
            }
        }).catch(error => {
            // Catch errors from MessageManager promise if any
            messageElement.textContent = `Error: ${error.message || 'Failed to generate message'}`;
        });
    } else {
        console.error("MessageManager is not available.");
        messageElement.textContent = 'Error: Message generation module not loaded.';
        if (generateBtn) { // Manually reset button if MessageManager is not there
             generateBtn.disabled = false;
             generateBtn.innerHTML = 'Generate Message';
        }
    }
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
    // setInterval(checkBotStatus, 10000); // checkBotStatus is part of BotStatus which has its own interval

    // Periodically refresh Bot Analytics data
    if (document.getElementById('totalMessages') || document.getElementById('totalTTS') || document.getElementById('totalResponses')) {
        loadSystemInfo(); // Initial load
        setInterval(loadSystemInfo, 20000); // Refresh every 20 seconds
    }

    // Populate channels for message generation if the selector exists
    if (document.getElementById('channelForMessage')) {
        populateMessageChannels();
    }
    // Populate models for message generation if the selector exists
    // This is now handled by MessageManager.init() in markov.js, which should be called
    // if (document.getElementById('modelSelector') && typeof fetchAvailableModels === 'function') {
    //     fetchAvailableModels();
    // }

    // Attach event listener to the generate message button if it exists
    const generateMsgBtn = document.getElementById('generateMsgBtn');
    if (generateMsgBtn) {
        generateMsgBtn.addEventListener('click', generateMessage);
    }

    // Load initial TTS data if the table exists
    if (document.getElementById("ttsFilesBody")) {
        loadMoreData();
    }

    // Setup "Load More" button if it exists
    const loadMoreBtn = document.getElementById("loadMore");
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener("click", loadMoreData);
    }
});

function showLoading() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.style.display = 'flex';
}

function hideLoading() {
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.style.display = 'none';
}

// Auto-refresh stats data periodically - THIS IS REMOVED as stats.js now handles its own page logic.
/*
function setupStatsAutoRefresh() {
  // IMPORTANT: Do not auto-refresh on settings page to prevent constant refreshing
  if (window.location.pathname.includes('/settings')) {
    console.log("On settings page - disabling auto-refresh to prevent refresh loops");
    return;
  }

  const statsContainer = document.getElementById('statsContainer');
  if (statsContainer) { // This implies it would only run on stats page anyway
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
      // But ONLY if we're not on the settings page
      if (!window.location.pathname.includes('/settings')) {
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
      }
    } catch (error) {
      console.error("Error in setupStatsAutoRefresh:", error);
    }
  }
}
*/

// Call this from your DOMContentLoaded event
document.addEventListener('DOMContentLoaded', function() {
  // console.log("data_handler.js: Stats auto-refresh setup removed.");
  // Use a longer delay to ensure all other scripts are loaded
  // setTimeout(setupStatsAutoRefresh, 1500); // Removed call

  // Make key functions globally available
  // window.generateMessage = generateMessage; // generateMessage is now specific to its button
  console.log("data_handler.js: generateMessage is now locally scoped or uses MessageManager.");
  
  // Setup any available generate buttons
  setTimeout(function() {
    const generateBtn = document.getElementById('generateMsgBtn');
    if (generateBtn && !generateBtn.getAttribute('listener')) { // Check if listener already attached
      console.log("Found generate button in data_handler.js, ensuring it's connected to handler");
      generateBtn.addEventListener('click', generateMessage);
      generateBtn.setAttribute('listener', 'true');
    }
  }, 500);
});
