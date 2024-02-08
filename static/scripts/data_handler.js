let lastId = 0;

function updateTable(data) {
  console.log("Updating table with data:", data);
  let tableBody = document.getElementById("ttsFilesBody");
  let isNewData = false;

  data.forEach((file) => {
    let messageIdInt = parseInt(file[1]);
    console.log(`Processing messageIdInt: ${messageIdInt}, lastId: ${lastId}`);
    if (messageIdInt > lastId) {
      addRowToTable(file, true);
      isNewData = true;
    }
  });

  if (isNewData) {
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
  let autoplayEnabled = document.getElementById("autoplay").checked;

  if (autoplayEnabled && data.length > 0) {
    let latestAudioId = `audio-${data[0][1]}`;
    let latestAudio = document.getElementById(latestAudioId);

    if (latestAudio) {
      latestAudio.muted = true; // Start muted to comply with autoplay policies
      latestAudio
        .play()
        .then(() => {
          console.log("Autoplay started for", latestAudioId);
          latestAudio.muted = false; // Unmute after starting playback
        })
        .catch((error) => {
          console.error("Autoplay failed for", latestAudioId, ":", error);
        });
    } else {
    }
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


