document.addEventListener("DOMContentLoaded", function () {
  console.log("DOMContentLoaded event fired");

  var mainTab = document.getElementById("mainTab");
  var settingsTab = document.getElementById("settingsTab");
  var mainContent = document.getElementById("mainContent");
  var settingsContent = document.getElementById("settingsContent");

  var modelSelector = document.getElementById("modelSelector");
  if (modelSelector) {
    fetchAvailableModels();
  } else {
  }

  function updateButtonStates(isBotRunning) {
    const messageButtons = document.querySelectorAll(".send-message-btn");
    messageButtons.forEach((button) => {
      button.disabled = !isBotRunning; // Disable if bot is not running
    });
  }

  // Function to fetch bot status and update UI
  function fetchBotStatusAndUpdateUI() {
    fetch("/bot_status")
      .then((response) => response.json())
      .then((data) => {
        updateButtonStates(data.is_running);
      })
      .catch((error) => console.error("Error fetching bot status:", error));
  }


  setInterval(fetchBotStatusAndUpdateUI, 30000); // 30 seconds

  var channelSelect = document.getElementById("channelSelect");
  if (channelSelect) {
    channelSelect.addEventListener("change", function () {
      checkForAddChannelOption(this);
    });
    fetchChannels(); // Populate the channels when the settings page loads
  }
  // Get the start bot button element
  var startBotButton = document.getElementById("startBotButton");

  // Add event listener to the start bot button
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

  function updateButtonTheme() {
    var currentTheme = document.documentElement.getAttribute("data-bs-theme");
    if (currentTheme === "dark") {
      themeToggle.className = "btn btn-light";
      themeToggle.textContent = "Light";
    } else {
      themeToggle.className = "btn btn-dark";
      themeToggle.textContent = "Dark";
    }
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

  themeToggle.addEventListener("click", function () {
    var currentTheme = document.documentElement.getAttribute("data-bs-theme");

    if (currentTheme === "dark") {
      document.documentElement.setAttribute("data-bs-theme", "light");
    } else {
      document.documentElement.setAttribute("data-bs-theme", "dark");
    }
    updateButtonTheme();
  });

  // Initialize button theme on load
  updateButtonTheme();

  try {
    var socket = io.connect(
      location.protocol + "//" + document.domain + ":" + location.port
    );

    socket.on("connect", function () {
      console.log("Websocket connected!");
    });

    socket.on("refresh_table", function () {
      loadLatestData();
    });
  } catch (error) {
    console.error("Error initializing WebSocket:", error);
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

  if (mainTab && mainContent && settingsContent && settingsTab) {
    mainTab.addEventListener("click", function () {
      mainContent.style.display = "block";
      settingsContent.style.display = "none";
      mainTab.classList.add("active");
      settingsTab.classList.remove("active");
    });
  }

  // Event listener for settingsTab
  if (settingsTab && settingsContent && mainContent && mainTab) {
    settingsTab.addEventListener("click", function () {
      mainContent.style.display = "none";
      settingsContent.style.display = "block";
      settingsTab.classList.add("active");
      mainTab.classList.remove("active");

      // Fetch channels only if channelSelect element is present
      var channelSelect = document.getElementById("channelSelect");
      if (channelSelect) {
        fetchChannels();
      }
    });
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
});

if (botControlTab && botControlContent && mainContent && mainTab) {
  botControlTab.addEventListener("click", function () {
    mainContent.style.display = "none";
    settingsContent.style.display = "none";
    botControlContent.style.display = "block";
    botControlTab.classList.add("active");
    mainTab.classList.remove("active");
    settingsTab.classList.remove("active");
  });
}
