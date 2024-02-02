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
  

  
  var channelSelect = document.getElementById("channelSelect");
  if (channelSelect) {
      channelSelect.addEventListener("change", function () {
          checkForAddChannelOption(this);
      });
      fetchChannels(); // Populate the channels when the settings page loads
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

  var autoplayElement = document.getElementById("autoplay");
  if (autoplayElement) {
      autoplayElement.addEventListener("change", function () {
          let autoplayEnabled = this.checked;
          let muteIcon = document.getElementById("muteIcon");
          let unmuteIcon = document.getElementById("unmuteIcon");
  
          if (autoplayEnabled) {
              muteIcon && muteIcon.classList.add("d-none");
              unmuteIcon && unmuteIcon.classList.remove("d-none");
          } else {
              muteIcon && muteIcon.classList.remove("d-none");
              unmuteIcon && unmuteIcon.classList.add("d-none");
          }
  
          // Save the mute status. Use 'localStorage' for persistence across sessions.
          localStorage.setItem('muteStatus', !autoplayEnabled);
      });
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


// var voicePreset = document.getElementById("voicePreset");
// if (voicePreset) {
//     voicePreset.addEventListener("change", function () {
//         const customVoiceRow = document.getElementById("customVoiceRow");
//         if (this.value === "custom") {
//             if (customVoiceRow) {
//                 customVoiceRow.style.display = "";
//                 fetchAndShowCustomVoices(); 
//             }
//         } else {
//             if (customVoiceRow) {
//                 customVoiceRow.style.display = "none";
//             }
//         }
//     });
// } else {
// }


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

    var statsContainer = document.getElementById('statsContainer');
    if (statsContainer) {
        statsContainer.addEventListener('click', function(event) {
            if (event.target && event.target.classList.contains('rebuild-cache-btn')) {
                const channelName = event.target.getAttribute('data-channel');
                if (channelName) {
                    rebuildCacheForChannel(channelName);
                }
            }
        });
    }
    if (statsContainer) {
        loadStats();
    }


    
    var rebuildAllCachesBtn = document.getElementById('rebuildAllCachesBtn');
    if (rebuildAllCachesBtn) {
        // If the button exists, add the event listener
        rebuildAllCachesBtn.addEventListener('click', function() {
            rebuildAllCaches();
        });
    }
    function loadStats() {
      let statsContainer = document.getElementById('statsContainer');
      if (!statsContainer) return;

      let loadingIndicator = document.getElementById('loadingIndicator');
      if (loadingIndicator) loadingIndicator.style.display = 'block';

      fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
          statsContainer.innerHTML = '';

          // Separate the general_markov stat from the others
          let generalMarkovStat = data.find(stat => stat.channel === 'general_markov');
          let otherStats = data.filter(stat => stat.channel !== 'general_markov');

          // Function to create a row for a stat
          const createStatRow = (stat) => {
            let row = document.createElement('tr');
          
            // Check if this is the General Model row
            if (stat.channel === 'General Model') {
              row.classList.add('table-primary'); // Apply Bootstrap class for the General Model row
            }
          
            let channelCell = document.createElement('th');
            channelCell.scope = 'row';
            channelCell.innerHTML = stat.channel === 'General Model' ? 'General Model' : `<a href="http://twitch.tv/${stat.channel}" target="_blank">${stat.channel}</a>`;
          
            let cacheCell = createCell(stat.cache);
            let logCell = createCell(stat.log);
            let cacheSizeCell = createCell(formatFileSize(stat.cache_size));
            let lineCountCell = createCell(stat.line_count.toString());
            let actionsCell = createCell(stat.channel === 'General Model' ? '' : createRebuildButton(stat.channel));
          
            row.append(channelCell, cacheCell, logCell, cacheSizeCell, lineCountCell, actionsCell);
            return row;
          }

          // If the general_markov stat exists, create a row for it and append it first
          if (generalMarkovStat) {
            let row = createStatRow(generalMarkovStat);
            statsContainer.appendChild(row);
          }

          // Create rows for the other stats
          otherStats.forEach(stat => {
            let row = createStatRow(stat);
            statsContainer.appendChild(row);
          });

          if (loadingIndicator) loadingIndicator.style.display = 'none';
        })
        .catch(error => {
          console.error('Error fetching stats:', error);
          if (statsContainer) statsContainer.innerHTML = 'Failed to load data.';
        });
    }
  
  function createCell(content) {
      let cell = document.createElement('td');
      cell.innerHTML = content;
      return cell;
  }
  
  function createRebuildButton(channelName) {
      let button = document.createElement('button');
      button.classList.add('btn', 'btn-primary', 'rebuild-cache-btn');
      button.setAttribute('data-channel', channelName);
      button.textContent = 'Rebuild Cache';
      button.addEventListener('click', function() {
          rebuildCacheForChannel(channelName);
      });
      return button.outerHTML;
  }
  
  function formatFileSize(bytes) {
      if (bytes < 1024) return bytes + ' Bytes';
      if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
      if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
      return (bytes / 1073741824).toFixed(1) + ' GB';
  }
  



const rebuildGeneralCacheBtn = document.getElementById('rebuildGeneralCacheBtn');
if (rebuildGeneralCacheBtn) {
    // If the button exists, add the event listener
    rebuildGeneralCacheBtn.addEventListener('click', function() {
        rebuildGeneralCache();
    });
}
});
