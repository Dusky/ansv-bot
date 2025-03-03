function handleVoicePresetChange() {
    let voicePresetSelect = document.getElementById("voicePreset");
    let customVoiceRow = document.getElementById("customVoiceRow");

    if (!voicePresetSelect) {
        console.error("Voice preset select element not found");
        return;
    }

    if (voicePresetSelect.value === "custom") {
        customVoiceRow.style.display = "";
        fetchAndShowCustomVoices(); // Ensure this function is defined
    } else {
        customVoiceRow.style.display = "none";
    }
}


function fetchAndShowVoices() {
  fetch("/list-voices")
    .then((response) => response.json())
    .then((data) => {
      const voiceSelect = document.getElementById("voiceSelect");
      data.voices.forEach((voice) => {
        let option = document.createElement("option");
        option.value = voice.replace(".npz", ""); // Remove the .npz extension
        option.textContent = voice.replace(".npz", ""); // Display name without .npz
        voiceSelect.appendChild(option);
      });
    })
    .catch((error) => console.error("Error fetching voices:", error));
}

function fetchAndShowCustomVoices() {
  // Safely check if element exists first
  const customVoiceSelect = document.getElementById("customVoiceSelect");
  if (!customVoiceSelect) {
    console.warn("Custom voice select not found in the DOM");
    return;
  }
  
  // Clear previous options
  customVoiceSelect.innerHTML = '';
  
  fetch("/list-voices")
    .then((response) => response.json())
    .then((data) => {
      console.log("Voices data:", data); // Debugging line
      
      if (data.voices && data.voices.length > 0) {
        data.voices.forEach((voice) => {
          let option = document.createElement("option");
          option.value = voice.replace(".npz", ""); // Remove the .npz extension
          option.textContent = voice.replace(".npz", ""); // Display name without .npz
          customVoiceSelect.appendChild(option);
        });
      } else {
        // Add a default option if no voices found
        let option = document.createElement("option");
        option.value = "default";
        option.text = "Default Voice";
        customVoiceSelect.appendChild(option);
      }
    })
    .catch((error) => {
      console.error("Error fetching custom voices:", error);
      // Add a default option in case of error
      let option = document.createElement("option");
      option.value = "default";
      option.text = "Default Voice";
      customVoiceSelect.appendChild(option);
    });
}

// Initialize on DOM ready if on settings page
document.addEventListener('DOMContentLoaded', function() {
  // Only run this if we're on the settings page with voice options
  if (document.getElementById('voicePreset')) {
    // Check if custom voice is selected
    if (document.getElementById('voicePreset').value === 'custom') {
      fetchAndShowCustomVoices();
    }
  }
});

function setVoice() {
  let selectedVoice;
  const voicePresetSelect = document.getElementById("voicePreset");
  const customVoiceSelect = document.getElementById("customVoiceSelect");

  if (voicePresetSelect.value === "custom") {
    selectedVoice = customVoiceSelect.value;
  } else {
    selectedVoice = voicePresetSelect.value;
  }

  console.log("Selected voice:", selectedVoice); // Add this line for debugging

  fetch("/set-voice", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ voice: selectedVoice }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        console.log("Voice set successfully");
      } else {
        console.error("Error setting voice:", data.error);
      }
    })
    .catch((error) => console.error("Error setting voice:", error));
}
