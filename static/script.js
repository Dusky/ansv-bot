let lastId = 0;

// Function to initialize the table with first page of data

function updateTable(data) {
    let tableBody = document.getElementById("ttsFilesBody");
    let isNewData = false;

    data.forEach((file) => {
        let messageIdInt = parseInt(file[1]);
        if (messageIdInt > lastId) {
            addRowToTable(file, true); // Add new row at the beginning
            lastId = messageIdInt; // Update lastId to the latest
            isNewData = true;
        }
    });

    return isNewData;
}

// Function to add a row to the table
function addRowToTable(file, prepend = false) {
    let tableBody = document.getElementById("ttsFilesBody");
    let audioSrc = `/static/${file[4]}`;
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
}

// Function to play audio
function playAudio(src) {
    let audio = new Audio(src);
    audio.play().catch(error => console.error("Play error:", error));
}

// Function to check if autoplay is enabled and play the latest file
function checkAutoplay(data) {
    let autoplayEnabled = document.getElementById("autoplay").checked;

    if (autoplayEnabled && data.length > 0) {
        let latestAudioId = `audio-${data[0][1]}`;
        let latestAudio = document.getElementById(latestAudioId);

        if (latestAudio) {
            // Wait for the audio to be ready to play
            latestAudio.addEventListener("canplay", function () {
                // Attempt to play the audio
                latestAudio
                    .play()
                    .then(() => {
                        console.log("Autoplay started for", latestAudioId);
                    })
                    .catch((error) => {
                        console.error("Autoplay failed for", latestAudioId, ":", error);
                        // Handle autoplay rejection, e.g., by showing a play button
                    });
            });

            // If the audio is already in a state where it can start playing, play it
            if (latestAudio.readyState >= 3) {
                latestAudio.play().catch((error) => {
                    console.error("Autoplay failed for", latestAudioId, ":", error);
                    // Handle autoplay rejection
                });
            }
        } else {
            console.error("No audio element found for", latestAudioId);
        }
    }
}

function checkForNewAudio() {
    fetch("/check-new-audio")
        .then((response) => response.json())
        .then((data) => {
            if (data.newAudioAvailable) {
                checkForUpdates(); // Fetch new rows and update the table
            }
        })
        .catch((error) => console.error("Error checking for new audio:", error));
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

function refreshTable() {
    // Reset the currentPage to 1
    currentPage = 1;

    // Clear only the table body (rows with data) before loading new data
    const tableBody = document.getElementById("ttsFilesBody");
    tableBody.innerHTML = "";

    // Fetch the first page of data again
    loadMoreData();
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

document.addEventListener("DOMContentLoaded", function () {
    console.log("DOMContentLoaded event fired");
    var mainTab = document.getElementById("mainTab");
    var settingsTab = document.getElementById("settingsTab");
    var mainContent = document.getElementById("mainContent");
    var settingsContent = document.getElementById("settingsContent"); // Ensure you have a corresponding element with this ID
    var themeToggle = document.getElementById("themeToggle");

    var channelSelect = document.getElementById("channelSelect");
    channelSelect.addEventListener("change", function () {
        checkForAddChannelOption(this);
    });

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

    mainTab.addEventListener("click", function () {
        setActiveTab(this);
    });

    settingsTab.addEventListener("click", function () {
        setActiveTab(this);
    });


    var saveSettingsButton = document.getElementById("saveSettings");
    saveSettingsButton.addEventListener("click", function (event) {
        event.preventDefault(); // Prevent the default form submission
        saveChannelSettings(); // Call the saveChannelSettings function
    });

    var addChannelSaveButton = document.getElementById("addChannelSave");
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
            addNewChannel(newChannelData); // Call addNewChannel instead of saveOrUpdateChannel
        } else {
            alert("Please enter a channel name.");
        }
    });

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

    document.getElementById("refreshTable").addEventListener("click", function () {
        refreshTable();
    });

    var settingsTab = document.getElementById("settingsTab");

    const loadMoreButton = document.getElementById("loadMore");
    if (loadMoreButton) {
        loadMoreButton.addEventListener("click", loadMoreData);
    } else {
        console.error("Load More button not found");
    }

    // Load initial data
    setInterval(checkForNewAudio, 3000);
    loadMoreData();

});


