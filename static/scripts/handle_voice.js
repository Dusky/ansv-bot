function handleVoicePresetChange() {
    let voicePresetSelect = document.getElementById("voicePreset");
    let customVoiceRow = document.getElementById("customVoiceRow");

    if (voicePresetSelect && customVoiceRow) {
        if (voicePresetSelect.value === "custom") {
            customVoiceRow.style.display = "";
            fetchAndShowCustomVoices(); // Ensure this function is defined
        } else {
            customVoiceRow.style.display = "none";
        }
    } else {
        if (!voicePresetSelect) {
            console.error("voicePreset element not found");
        }
        if (!customVoiceRow) {
            console.error("customVoiceRow element not found");
        }
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
  fetch("/list-voices")
    .then((response) => response.json())
    .then((data) => {
      console.log("Voices data:", data); // Debugging line
      const customVoiceSelect = document.getElementById("customVoiceSelect");
      data.voices.forEach((voice) => {
        let option = document.createElement("option");
        option.value = voice.replace(".npz", ""); // Remove the .npz extension
        option.textContent = voice.replace(".npz", ""); // Display name without .npz
        customVoiceSelect.appendChild(option);
      });
    })
    .catch((error) => console.error("Error fetching custom voices:", error));
}

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
