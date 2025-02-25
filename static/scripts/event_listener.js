document.addEventListener("DOMContentLoaded", function () {
  console.log("DOMContentLoaded event fired");
  
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

// Function to set up theme toggle
function setupThemeToggle() {
  const themeToggle = document.getElementById("themeToggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function() {
      const currentTheme = document.documentElement.getAttribute("data-bs-theme");
      
      if (currentTheme === "dark") {
        // Switch to light theme
        document.documentElement.setAttribute("data-bs-theme", "light");
        // Set cookie via server
        fetch('/set_theme/flatly');
      } else {
        // Switch to dark theme
        document.documentElement.setAttribute("data-bs-theme", "dark");
        // Set cookie via server
        fetch('/set_theme/darkly');
      }
      
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
  
  if (currentTheme === "dark") {
    themeToggle.className = "btn btn-light";
    themeToggle.innerHTML = '<i class="fas fa-sun"></i> Light';
  } else {
    themeToggle.className = "btn btn-dark";
    themeToggle.innerHTML = '<i class="fas fa-moon"></i> Dark';
  }
}

function updateButtonStates(isBotRunning) {
  const messageButtons = document.querySelectorAll(".send-message-btn");
  messageButtons.forEach(button => {
    if (!button.classList.contains('in-countdown')) {
      button.disabled = !isBotRunning;
    }
  });
}

function fetchBotStatusAndUpdateUI() {
  fetch("/bot_status")
    .then(response => response.json())
    .then(data => updateButtonStates(data.running))
    .catch(error => console.error("Error fetching bot status:", error));
}

setInterval(fetchBotStatusAndUpdateUI, 30000); // 30 seconds

var startBotButton = document.getElementById("startBotButton");

if (startBotButton) {
  startBotButton.addEventListener("click", function () {
    // Make an asynchronous POST request to start the bot
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
        // Handle successful response
        console.log("Bot started successfully");
      })
      .catch((error) => {
        // Handle error
        console.error("There was a problem with the fetch operation:", error);
      });
  });
}

const autoplayElement = document.getElementById("autoplay");
const muteIcon = document.getElementById("muteIcon");
const unmuteIcon = document.getElementById("unmuteIcon");

// Set the UI based on stored preferences
const isMuted = localStorage.getItem("muteStatus") === "true";
autoplayElement.checked = !isMuted;
updateIcons(isMuted);

autoplayElement.addEventListener("change", function () {
  const autoplayEnabled = this.checked;
  updateIcons(!autoplayEnabled);
  localStorage.setItem("muteStatus", !autoplayEnabled);
});

function updateIcons(isMuted) {
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
    window.socket = io.connect(
      location.protocol + "//" + document.domain + ":" + location.port
    );

    socket.on("connect", function () {
      console.log("WebSocket connected!");
    });

    socket.on("connect_error", function(error) {
      console.error("WebSocket connection error:", error);
    });

    socket.on("refresh_table", function () {
      addLatestRow();
    });
    
    socket.on("bot_status_change", function(data) {
      updateBotStatusUI(data.status);
    });
  } catch (error) {
    console.error("Error initializing WebSocket:", error);
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

  fetch("/api/stats")
    .then((response) => response.json())
    .then((data) => {
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
        let cacheSizeCell = createCell(formatFileSize(stat.cache_size));
        let lineCountCell = createCell(stat.line_count.toString());
        let actionsCell = document.createElement("td");

        // Append existing Rebuild Cache button
        if (stat.channel !== "General Model") {
          let rebuildCacheButton = createActionButton(
            "btn-warning rebuild-cache-btn",
            "Rebuild",
            stat.channel,
            rebuildCacheForChannel
          );
          actionsCell.appendChild(rebuildCacheButton);
        }

        // Append new Send Message button
        if (stat.channel !== "General Model") {
          let sendMessageButton = createActionButton(
            "btn-success send-message-btn ml-2" ,
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
      if (statsContainer) statsContainer.innerHTML = "Failed to load data.";
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

if (botControlTab && mainContent && mainTab) {
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
  fetch('/get-available-models')
    .then(response => response.json())
    .then(models => {
      const selector = document.getElementById('modelSelector');
      if (selector) {
        // Clear existing options
        selector.innerHTML = '';
        
        // Add default "General" model
        const generalOption = document.createElement('option');
        generalOption.value = 'general';
        generalOption.textContent = 'General Model';
        selector.appendChild(generalOption);
        
        // Add channel-specific models
        models.forEach(model => {
          const option = document.createElement('option');
          option.value = model;
          option.textContent = model;
          selector.appendChild(option);
        });
        
        console.log(`Populated model selector with ${models.length + 1} options`);
      } else {
        console.warn("Model selector element not found");
      }
    })
    .catch(error => console.error('Error loading models:', error));
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
  const muteIcon = document.getElementById("muteIcon");
  const unmuteIcon = document.getElementById("unmuteIcon");

  if (!autoplayElement || !muteIcon || !unmuteIcon) return;

  // Set the UI based on stored preferences
  const isMuted = localStorage.getItem("muteStatus") === "true";
  autoplayElement.checked = !isMuted;
  updateAudioIcons(isMuted);

  autoplayElement.addEventListener("change", function () {
    const autoplayEnabled = this.checked;
    updateAudioIcons(!autoplayEnabled);
    localStorage.setItem("muteStatus", !autoplayEnabled);
  });

  function updateAudioIcons(isMuted) {
    if (isMuted) {
      muteIcon.classList.remove("d-none");
      unmuteIcon.classList.add("d-none");
    } else {
      muteIcon.classList.add("d-none");
      unmuteIcon.classList.remove("d-none");
    }
  }
}
