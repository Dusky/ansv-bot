// Initialize socket properly at the top
const socket = io();

document.addEventListener("DOMContentLoaded", function () {  
  // Check bot status first
  checkBotStatus();

  // Populate channel and model selectors for message generation
  const channelForMessage = document.getElementById('channelForMessage');
  if (channelForMessage) {
    populateMessageChannels();
  }

  // Also populate the models if modelSelector exists
  const modelSelector = document.getElementById('modelSelector');
  if (modelSelector) {
    populateModels();
  }

  // Populate channel settings dropdown
  var channelSelect = document.getElementById("channelSelect");
  if (channelSelect) {
    channelSelect.addEventListener("change", function () {
      checkForAddChannelOption(this);
    });
    fetchChannels(); // Populate the channels when the settings page loads
  }

  // Set up button event listeners
  setupButtonListeners();
  
  // Set up theme toggle
  setupThemeToggle();
  
  // Set up autoplay toggle
  setupAutoplayToggle();
  
  // Set up WebSocket
  setupWebSocket();
  
  // Load initial data for tables if needed
  refreshTable();

  // Add keyboard shortcuts
  setupKeyboardShortcuts();

  // Fix muteIcon/unmuteIcon null reference error 
  // by adding proper null checks before accessing properties
  const autoplayElement = document.getElementById("autoplay");
  const muteIcon = document.getElementById("muteIcon");
  const unmuteIcon = document.getElementById("unmuteIcon");
  
  // Set the UI based on stored preferences
  const isMuted = localStorage.getItem("muteStatus") === "true";
  
  // Only attempt to modify elements if they exist
  if (autoplayElement) {
    autoplayElement.checked = !isMuted;
  }
  
  // Update icons function
  function updateIcons() {
    if (muteIcon && unmuteIcon) {
      muteIcon.classList.toggle('d-none', !isMuted);
      unmuteIcon.classList.toggle('d-none', isMuted);
    }
  }
  
  // Call the function if elements exist
  if (muteIcon || unmuteIcon) {
    updateIcons();
  }
});

// Function to set up event listeners for buttons
function setupButtonListeners() {
  // Start bot button
  var startBotButton = document.getElementById("startBotButton");
  if (startBotButton) {
    startBotButton.addEventListener("click", function () {
      fetch("/start_bot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Network response was not ok");
          }
          return response.json();
        })
        .then((data) => {
          console.log("Bot started successfully");
          checkBotStatus(); // Update status immediately
        })
        .catch((error) => {
          console.error("There was a problem with the fetch operation:", error);
        });
    });
  }
  
  // Save settings button
  var saveSettingsButton = document.getElementById("saveSettings");
  if (saveSettingsButton) {
    saveSettingsButton.addEventListener("click", function (event) {
      event.preventDefault();
      saveChannelSettings();
    });
  }
  
  // Add channel button
  var addChannelSaveButton = document.getElementById("addChannelSave");
  if (addChannelSaveButton) {
    addChannelSaveButton.addEventListener("click", function () {
      var newChannelName = document.getElementById("newChannelName").value;
      if (newChannelName) {
        var newChannelData = {
          channel_name: newChannelName,
          tts_enabled: 0,
          voice_enabled: 0,
          join_channel: 1,
          owner: newChannelName,
          trusted_users: "",
          ignored_users: "",
          use_general_model: 1,
          lines_between_messages: 100,
          time_between_messages: 0,
        };
        addNewChannel(newChannelData);
      } else {
        alert("Please enter a channel name.");
      }
    });
  }
  
  // Refresh table button
  var refreshTableButton = document.getElementById("refreshTable");
  if (refreshTableButton) {
    refreshTableButton.addEventListener("click", function () {
      refreshTable();
    });
  }
  
  // Load more button
  const loadMoreButton = document.getElementById("loadMore");
  if (loadMoreButton) {
    loadMoreButton.addEventListener("click", loadMoreData);
  }
}

// Function to set up theme toggle - modified to use global theme system
function setupThemeToggle() {
  const themeToggle = document.getElementById("themeToggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function() {
      const currentTheme = document.documentElement.getAttribute("data-bs-theme");
      console.log("Theme toggle clicked, current theme:", currentTheme);
      
      if (currentTheme === "dark") {
        // Switch to light theme (use the global system if available)
        if (window.selectTheme) {
          window.selectTheme('flatly');
        } else {
          // Fallback
          document.documentElement.setAttribute("data-bs-theme", "light");
          fetch('/set_theme/flatly')
            .then(() => {
              // Add a small delay then reload to ensure cookie is set
              setTimeout(() => window.location.reload(), 100);
            });
        }
      } else {
        // Switch to dark theme (use the global system if available)
        if (window.selectTheme) {
          window.selectTheme('darkly');
        } else {
          // Fallback
          document.documentElement.setAttribute("data-bs-theme", "dark");
          fetch('/set_theme/darkly')
            .then(() => {
              // Add a small delay then reload to ensure cookie is set
              setTimeout(() => window.location.reload(), 100);
            });
        }
      }
      
      // Update toggle button appearance
      updateButtonTheme();
    });
    
    // Initialize button on load
    updateButtonTheme();
  }
}

// Function to update theme toggle button
function updateButtonTheme() {
  const themeToggle = document.getElementById("themeToggle");
  if (!themeToggle) return;
  
  const currentTheme = document.documentElement.getAttribute("data-bs-theme");
  console.log("Updating theme toggle appearance for theme:", currentTheme);
  
  if (currentTheme === "dark") {
    themeToggle.className = "btn btn-sm btn-outline-light";
    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    themeToggle.setAttribute('title', 'Switch to Light Theme');
  } else {
    themeToggle.className = "btn btn-sm btn-outline-light";
    themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
    themeToggle.setAttribute('title', 'Switch to Dark Theme');
  }
}

// Global bot status variable - accessible to all scripts
window.globalBotStatus = {
  running: false,
  connected: false,
  tts_enabled: false,
  last_checked: new Date()
};

// Global function to update button states based on bot status
function updateButtonStates(isBotRunning) {
  // Store the status in the global variable
  window.globalBotStatus.running = isBotRunning;
  window.globalBotStatus.last_checked = new Date();
  
  // Update all message buttons
  document.querySelectorAll(".send-message-btn, .btn-primary[data-channel]").forEach(button => {
    if (!button.classList.contains('in-countdown')) {
      button.disabled = !isBotRunning;
      
      // Add visual indication
      if (!isBotRunning) {
        button.title = "Bot is not running";
        if (!button.classList.contains('disabled')) {
          button.classList.add('disabled');
        }
      } else {
        button.title = "";
        if (button.classList.contains('disabled')) {
          button.classList.remove('disabled');
        }
      }
    }
  });
  
  // Update status indicators if they exist
  const botStatusIndicator = document.getElementById('botStatusIndicator');
  if (botStatusIndicator) {
    botStatusIndicator.className = isBotRunning ? 'ms-2 badge bg-success' : 'ms-2 badge bg-danger';
    botStatusIndicator.innerHTML = isBotRunning ? 'Bot Online' : 'Bot Offline';
  }
}

// Global function to fetch bot status and update UI
function fetchBotStatusAndUpdateUI() {
  fetch("/api/bot-status")
    .then(response => response.json())
    .then(data => {
      updateButtonStates(data.running);
      
      // Also store connected status and TTS status
      if (data.connected !== undefined) window.globalBotStatus.connected = data.connected;
      if (data.tts_enabled !== undefined) window.globalBotStatus.tts_enabled = data.tts_enabled;
    })
    .catch(error => {
      updateButtonStates(false); // Assume bot is not running on error
    });
}

// Initial check and periodic updates
document.addEventListener('DOMContentLoaded', fetchBotStatusAndUpdateUI);
setInterval(fetchBotStatusAndUpdateUI, 30000); // 30 seconds

// startBotButton event listener is already defined in setupButtonListeners()

// Define autoplay functionality in a single place
function initializeAutoplayToggle() {
  const autoplayElement = document.getElementById("autoplay");
  const muteIcon = document.getElementById("muteIcon");
  const unmuteIcon = document.getElementById("unmuteIcon");
  
  if (autoplayElement) {
    // Set the UI based on stored preferences
    const isMuted = localStorage.getItem("muteStatus") === "true";
    autoplayElement.checked = !isMuted;
    updateIcons(isMuted);
    
    // Add event listener
    autoplayElement.addEventListener("change", function () {
      const autoplayEnabled = this.checked;
      updateIcons(!autoplayEnabled);
      localStorage.setItem("muteStatus", !autoplayEnabled);
    });
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializeAutoplayToggle);

function updateIcons(isMuted) {
  const muteIcon = document.getElementById("muteIcon");
  const unmuteIcon = document.getElementById("unmuteIcon");
  
  if (!muteIcon || !unmuteIcon) return; // Exit if icons don't exist
  
  if (isMuted) {
    muteIcon.classList.remove("d-none");
    unmuteIcon.classList.add("d-none");
  } else {
    muteIcon.classList.add("d-none");
    unmuteIcon.classList.remove("d-none");
  }
}

// Function to set up WebSocket
function setupWebSocket() {
  try {
    socket.on("refresh_table", function () {
      addLatestRow();
    });
    
    socket.on("bot_status_change", function(data) {
      updateBotStatusUI(data.status);
    });
  } catch (error) {
    // Silent fail for WebSocket errors
  }
}

var saveSettingsButton = document.getElementById("saveSettings");
if (saveSettingsButton) {
  saveSettingsButton.addEventListener("click", function (event) {
    event.preventDefault(); // Prevent the default form submission
    saveChannelSettings(); // Call the saveChannelSettings function
  });
} else {
}

var addChannelSaveButton = document.getElementById("addChannelSave");
if (addChannelSaveButton) {
  addChannelSaveButton.addEventListener("click", function () {
    var newChannelName = document.getElementById("newChannelName").value;
    if (newChannelName) {
      var newChannelData = {
        channel_name: newChannelName,
        tts_enabled: 0, // Default values for a new channel
        voice_enabled: 0,
        join_channel: 1,
        owner: newChannelName,
        trusted_users: "",
        ignored_users: "",
        use_general_model: 1,
        lines_between_messages: 100,
        time_between_messages: 0,
      };
      addNewChannel(newChannelData);
    } else {
      alert("Please enter a channel name.");
    }
  });
} else {
}

var refreshTableButton = document.getElementById("refreshTable");
if (refreshTableButton) {
  refreshTableButton.addEventListener("click", function () {
    refreshTable();
  });
} else {
}

var settingsTab = document.getElementById("settingsTab");

const loadMoreButton = document.getElementById("loadMore");
if (loadMoreButton) {
  loadMoreButton.addEventListener("click", loadMoreData);
} else {
}

// Load initial data
//loadMoreData();
//loadLatestData();
var voicePresetSelect = document.getElementById("voicePresetSelect");
if (voicePresetSelect) {
  handleVoicePresetChange();
}
refreshTable();
socket.on("refresh_table", function () {
  addLatestRow();
});

var statsContainer = document.getElementById("statsContainer");
if (statsContainer) {
  statsContainer.addEventListener("click", function (event) {
    if (
      event.target &&
      event.target.classList.contains("rebuild-cache-btn")
    ) {
      const channelName = event.target.getAttribute("data-channel");
      if (channelName) {
        rebuildCacheForChannel(channelName);
      }
    }
  });
}
if (statsContainer) {
  // Make loadStats globally accessible in two ways for better compatibility
  window.loadStats = loadStats; 
  window.eventListenerLoadStats = loadStats;
  loadStats();
}

var rebuildAllCachesBtn = document.getElementById("rebuildAllCachesBtn");
if (rebuildAllCachesBtn) {
  // If the button exists, add the event listener
  rebuildAllCachesBtn.addEventListener("click", function () {
    rebuildAllCaches();
  });
}
function loadStats() {
  let statsContainer = document.getElementById("statsContainer");
  if (!statsContainer) return;

  let loadingIndicator = document.getElementById("loadingIndicator");
  if (loadingIndicator) loadingIndicator.style.display = "block";

  // Update the channel count display
  updateChannelCount();

  fetch("/api/stats")
    .then((response) => response.json())
    .then((data) => {
      // Safety check - make sure data is an array
      if (!Array.isArray(data)) {
        throw new Error("Invalid data format - expected an array");
      }
      
      statsContainer.innerHTML = "";

      data.forEach((stat) => {
        let row = document.createElement("tr");
        let channelCell = document.createElement("th");
        channelCell.scope = "row";
        channelCell.innerHTML =
          stat.channel === "General Model"
            ? "General Model"
            : `<a href="http://twitch.tv/${stat.channel}" target="_blank">${stat.channel}</a>`;

        let cacheCell = createCell(stat.cache);
        let logCell = createCell(stat.log);
        
        // Make sure cache_size is properly formatted
        let cacheSizeValue = typeof stat.cache_size === 'number' 
          ? formatFileSize(stat.cache_size) 
          : stat.cache_size || '0 B';
          
        let cacheSizeCell = createCell(cacheSizeValue);
        
        // Make sure line_count is a string
        let lineCountValue = stat.line_count !== undefined 
          ? stat.line_count.toString() 
          : '0';
          
        let lineCountCell = createCell(lineCountValue);
        let actionsCell = document.createElement("td");

        // Append existing Rebuild Cache button
        if (stat.channel !== "General Model") {
          let rebuildCacheButton = createActionButton(
            "btn-warning rebuild-cache-btn me-2",
            "Rebuild",
            stat.channel,
            rebuildCacheForChannel
          );
          actionsCell.appendChild(rebuildCacheButton);
        }

        // Append new Send Message button
        if (stat.channel !== "General Model") {
          let sendMessageButton = createActionButton(
            "btn-success send-message-btn",
            "Send Message",
            stat.channel,
            sendMarkovMessageToChannel
          );
          actionsCell.appendChild(sendMessageButton);
        }

        row.append(
          channelCell,
          cacheCell,
          logCell,
          cacheSizeCell,
          lineCountCell,
          actionsCell
        );
        statsContainer.appendChild(row);
      });

      if (loadingIndicator) loadingIndicator.style.display = "none";
    })
    .catch((error) => {
      console.error("Error fetching stats:", error);
      if (statsContainer) {
        statsContainer.innerHTML = '<tr><td colspan="6" class="text-danger">Failed to load data: ' + error.message + '</td></tr>';
      }
      if (loadingIndicator) loadingIndicator.style.display = "none";
    });
}

// Function to send Markov message to a channel
function sendMarkovMessageToChannel(channelName) {
  // Just delegate to the method in markov.js
  if (window.markovModule && window.markovModule.sendMarkovMessage) {
    window.markovModule.sendMarkovMessage(channelName);
  } else {
    console.error("Markov module not found");
    alert("Error: Markov module not loaded properly");
  }
}

// Function to update the channel count display
function updateChannelCount() {
  const channelCountElement = document.getElementById('channelCount');
  if (!channelCountElement) return;
  
  // Make this function globally available
  window.updateChannelCount = updateChannelCount;
  
  fetch("/get-stats")
    .then(response => response.json())
    .then(data => {
        // Count channels but exclude the general model
      const channelCount = data.filter(channel => 
        channel.name !== 'general_markov' && 
        channel.name !== 'General Model'
      ).length;
      
      channelCountElement.textContent = channelCount;
    })
    .catch(error => {
      console.error("Error updating channel count:", error);
      channelCountElement.textContent = "?";
    });
}

function createCell(content) {
  let cell = document.createElement("td");
  cell.innerHTML = content;
  return cell;
}

function createActionButton(
  buttonClass,
  buttonText,
  channelName,
  actionFunction
) {
  let button = document.createElement("button");
  button.className = `btn ${buttonClass} ml-2`;
  button.innerText = buttonText;
  button.setAttribute("data-channel", channelName);
  button.addEventListener("click", function () {
    actionFunction(channelName);
  });
  return button;
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " Bytes";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
  return (bytes / 1073741824).toFixed(1) + " GB";
}

const rebuildGeneralCacheBtn = document.getElementById(
  "rebuildGeneralCacheBtn"
);
if (rebuildGeneralCacheBtn) {
  rebuildGeneralCacheBtn.addEventListener("click", function () {
    rebuildGeneralCache();
  });
}

// Populate channels for message generation if the element exists
const channelForMessage = document.getElementById('channelForMessage');
if (channelForMessage) {
  populateMessageChannels();
}

// Also populate the models if modelSelector exists
const modelSelector = document.getElementById('modelSelector');
if (modelSelector) {
  populateModels();
}

// Add proper element declarations at the top
const botControlTab = document.getElementById('botControlTab');
const mainContent = document.getElementById('mainContent');
const mainTab = document.getElementById('mainTab');
const settingsContent = document.getElementById('settingsContent');

if (botControlTab && mainContent && mainTab && settingsContent) {
  botControlTab.addEventListener("click", function () {
    mainContent.style.display = "none";
    settingsContent.style.display = "none";

    botControlTab.classList.add("active");
    mainTab.classList.remove("active");
    settingsTab.classList.remove("active");
  });
}

// Function to populate model selector
function populateModels() {
  console.log("Populating models");
  
  // Show loading state in the selector
  const selector = document.getElementById('modelSelector');
  if (selector) {
    selector.innerHTML = '<option>Loading models...</option>';
    selector.disabled = true;
  }
  
  fetch('/available-models')
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to load models: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then(models => {
      console.log("Models received:", models);
      
      if (selector) {
        // Clear existing options
        selector.innerHTML = '';
        selector.disabled = false;
        
        // Add default "General" model
        const generalOption = document.createElement('option');
        generalOption.value = 'general';
        generalOption.textContent = 'General Model';
        selector.appendChild(generalOption);
        
        // Add channel-specific models
        if (models.length > 0) {
          models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            selector.appendChild(option);
          });
          
          console.log(`Populated model selector with ${models.length + 1} options`);
        } else {
          console.warn("No models returned from server");
          
          // Add a placeholder if no models found
          const noModelsOption = document.createElement('option');
          noModelsOption.disabled = true;
          noModelsOption.textContent = 'No models available';
          selector.appendChild(noModelsOption);
        }
      } else {
        console.warn("Model selector element not found");
      }
    })
    .catch(error => {
      console.error('Error loading models:', error);
      
      if (selector) {
        selector.innerHTML = '<option>Error loading models</option>';
        selector.disabled = false;
      }
    });
}

function updateBotStatusUI(statusData) {
  const botStatusIcon = document.getElementById('botStatusIcon');
  const botStatusIndicator = document.getElementById('botStatusIndicator');
  
  if (botStatusIcon) {
    if (statusData.status === 'running') {
      botStatusIcon.className = 'bi bi-circle-fill text-success';
    } else {
      botStatusIcon.className = 'bi bi-circle-fill text-danger';
    }
  }
  
  if (botStatusIndicator) {
    if (statusData.status === 'running') {
      botStatusIndicator.innerHTML = '<span class="badge bg-success">Running</span>';
    } else {
      botStatusIndicator.innerHTML = '<span class="badge bg-danger">Stopped</span>';
    }
  }
  
  // Also update button states
  updateButtonStates(statusData.status === 'running');
}

// Add keyboard shortcuts
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', function(event) {
    // Ctrl+S to save settings
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      const saveSettingsBtn = document.getElementById('saveSettings');
      if (saveSettingsBtn && saveSettingsBtn.offsetParent !== null) {
        saveSettingsBtn.click();
      }
    }
    
    // Ctrl+G to generate message
    if (event.ctrlKey && event.key === 'g') {
      event.preventDefault();
      const generateMsgBtn = document.getElementById('generateMsgBtn');
      if (generateMsgBtn && generateMsgBtn.offsetParent !== null) {
        generateMsgBtn.click();
      }
    }
  });
}

// Function to set up autoplay toggle
function setupAutoplayToggle() {
  const autoplayElement = document.getElementById("autoplay");
  if (!autoplayElement) return; // Exit if element doesn't exist
  
  const muteIcon = document.getElementById("muteIcon");
  const unmuteIcon = document.getElementById("unmuteIcon");
  if (!muteIcon || !unmuteIcon) return; // Exit if icons don't exist
  
  // Just initialize with default settings - avoid accessing localStorage
  muteIcon.classList.remove("d-none");
  unmuteIcon.classList.add("d-none");
  
  // Add simple listener
  autoplayElement.addEventListener("change", function() {
    if (this.checked) {
      muteIcon.classList.add("d-none");
      unmuteIcon.classList.remove("d-none");
    } else {
      muteIcon.classList.remove("d-none");
      unmuteIcon.classList.add("d-none");
    }
  });
}
