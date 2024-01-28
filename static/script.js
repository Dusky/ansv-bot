let lastId = 0;

// Function to initialize the table with first page of data

function updateTable(data) {
    console.log("Updating table with data:", data);
    let tableBody = document.getElementById("ttsFilesBody");
    let isNewData = false;

    data.forEach((file) => {
        let messageIdInt = parseInt(file[1]);
        console.log(`Processing messageIdInt: ${messageIdInt}, lastId: ${lastId}`);
        if (messageIdInt > lastId) {
            addRowToTable(file, true); // Add new row at the beginning
            isNewData = true;
        }
    });

    if (isNewData) {
        lastId = parseInt(data[0][1]); // Update lastId to the latest messageId
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
    // Delay autoplay check to ensure DOM has been updated
    setTimeout(() => {
        checkAutoplay([file]);
    }, 100); // Adjust delay as needed
}
function addLatestRow() {
    fetch('/latest-messages')
        .then(response => response.json())
        .then(data => {
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
        .catch(error => console.error("Error fetching latest data:", error));
}

// Function to play audio
function playAudio(src) {
    let audio = new Audio(src);
    audio.play().catch(error => console.error("Play error:", error));
}

// Function to check if autoplay is enabled and play the latest file
function checkAutoplay(data) {
    console.log("checkAutoplay called with data:", data); // Debug log
    let autoplayEnabled = document.getElementById("autoplay").checked;
    console.log("Is autoplay enabled?", autoplayEnabled); // Debug log

    if (autoplayEnabled && data.length > 0) {
        let latestAudioId = `audio-${data[0][1]}`;
        let latestAudio = document.getElementById(latestAudioId);
        console.log(`Latest audio element:`, latestAudio); // Debug log

        if (latestAudio) {
            latestAudio.muted = true;  // Start muted to comply with autoplay policies
            latestAudio.play()
                .then(() => {
                    console.log("Autoplay started for", latestAudioId);
                    latestAudio.muted = false;  // Unmute after starting playback
                })
                .catch((error) => {
                    console.error("Autoplay failed for", latestAudioId, ":", error);
                    // You might want to show a manual play button here
                });
        } else {
            console.error("No audio element found for", latestAudioId);
        }
    }
}


function refreshTable() {
    currentPage = 1;
    const tableBody = document.getElementById("ttsFilesBody");
    tableBody.innerHTML = "";
    loadMoreData(); // Load the initial set of data
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
    fetch('/latest-messages')
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

function fetchAvailableModels() {
    fetch('/available-models')
        .then(response => response.json())
        .then(models => {
            const modelSelector = document.getElementById('modelSelector');
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelector.appendChild(option);
            });
        })
        .catch(error => console.error('Error fetching models:', error));
}

function generateMessage() {
    const selectedModel = document.getElementById('modelSelector').value;
    fetch(`/generate-message/${selectedModel}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if(data.message) {
                document.getElementById('generatedMessage').textContent = `${data.message}`;
            } else {
                alert('Failed to generate message. No message returned from server.');
            }
        })
        .catch(error => {
            console.error('Error generating message:', error);
            alert(`Error generating message: ${error}`);
        });
}


// function generateMessage() {
//     const selectedModel = document.getElementById('modelSelector').value;
//     const combineWithGeneral = document.getElementById('combineModelsCheckbox').checked;
//     const modelWeight = combineWithGeneral ? document.getElementById('modelWeight').value : undefined;
  
//     // Include the combineWithGeneral and modelWeight in the request
//     const queryParams = new URLSearchParams({ combineWithGeneral, modelWeight }).toString();
//     fetch(`/generate-message/${selectedModel}?${queryParams}`)
//       .then(response => response.json())
//       .then(data => {
//         // Handle the response
//       })
//       .catch(error => {
//         // Handle the error
//       });
//   }

document.addEventListener("DOMContentLoaded", function () {
    console.log("DOMContentLoaded event fired");
    fetchAvailableModels();
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

//   document.getElementById('combineModelsCheckbox').addEventListener('change', function() {
//     document.getElementById('modelWeight').disabled = !this.checked;
//   });

  document.getElementById('autoplay').addEventListener('change', function() {
    let autoplayEnabled = this.checked;
    let muteIcon = document.getElementById('muteIcon');
    let unmuteIcon = document.getElementById('unmuteIcon');

    if (autoplayEnabled) {
        muteIcon.classList.add('d-none');
        unmuteIcon.classList.remove('d-none');
    } else {
        muteIcon.classList.remove('d-none');
        unmuteIcon.classList.add('d-none');
    }
});
  
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
        var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    
        socket.on('connect', function() {
            console.log('Websocket connected!');
        });
    
        socket.on('refresh_table', function() {
            loadLatestData();
        });
    } catch (error) {
        console.error("Error initializing WebSocket:", error);
    }

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
            addNewChannel(newChannelData); 
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
    //loadMoreData();
    //loadLatestData();
    refreshTable();
     socket.on('refresh_table', function() {
         addLatestRow(); // or any other function that updates the table
     });
});


