function fetchAvailableModels() {
  fetch("/available-models")
      .then((response) => response.json())
      .then((models) => {
          const modelSelector = document.getElementById("modelSelector");
          models.forEach((model) => {
              const option = document.createElement("option");
              option.value = model;
              option.textContent = model;
              modelSelector.appendChild(option);
          });
      })
      .catch((error) => console.error("Error fetching models:", error));
}

function generateMessage() {
  const selectedModel = document.getElementById("modelSelector").value;
  const messageContainer = document.getElementById("generatedMessageContainer");
  fetch(`/generate-message/${selectedModel}`)
      .then((response) => {
          if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.json();
      })
      .then((data) => {
          if (data.message) {
              document.getElementById("generatedMessage").textContent = data.message;
              messageContainer.classList.remove("d-none");
          } else {
              alert("Failed to generate message. No message returned from server.");
          }
      })
      .catch((error) => {
          console.error("Error generating message:", error);
          alert(`Error generating message: ${error}`);
      });
}

function rebuildCacheForChannel(channelName) {
    const rebuildButton = document.querySelector(`button[data-channel="${channelName}"]`);
    if (rebuildButton) {
        rebuildButton.disabled = true;
        rebuildButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rebuilding...';

        fetch(`/rebuild-cache/${channelName}`, { method: 'POST' })
            .then(response => {
                console.log('Response received:', response); // Added for debugging
                if (!response.ok) {
                    throw new Error(`Failed to rebuild cache: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Data:', data); // Added for debugging
                alert(data.success ? `Cache rebuilt successfully for ${channelName}` : `Failed to rebuild cache for ${channelName}: ${data.message}`);
            })
            .catch(error => {
                console.error('Error:', error);
                alert(`Error rebuilding cache for ${channelName}: ${error}`);
            })
            .finally(() => {
                rebuildButton.disabled = false;
                rebuildButton.textContent = 'Rebuild Cache';
            });
    } else {
        console.error(`Rebuild button not found for channel: ${channelName}`);
    }
}

function sendMarkovMessageToChannel(channelName) {
    const sendMessageButton = document.querySelector(`button.send-message-btn[data-channel="${channelName}"]`);
    if (sendMessageButton) {
        sendMessageButton.disabled = true;
        sendMessageButton.innerText = 'Sending...';
        sendMessageButton.classList.add('countdown-active'); // Mark button as in countdown

        fetch(`/send_markov_message/${channelName}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ channelName: channelName }),
        })
        .then(response => {
            if (!response.ok) { throw new Error("Network response was not ok"); }
            return response.json();
        })
        .then(data => {
            let countdown = 5;
            const intervalId = setInterval(() => {
                if (countdown === 0) {
                    clearInterval(intervalId);
                    sendMessageButton.disabled = false;
                    sendMessageButton.innerText = 'Send Message';
                    sendMessageButton.classList.remove('countdown-active'); // Remove countdown mark
                } else {
                    sendMessageButton.innerText = `Sent! (${countdown}s)`;
                    countdown--;
                }
            }, 1000);
        })
        .catch(error => {
            console.error(`There was a problem sending message to channel ${channelName}:`, error);
            sendMessageButton.disabled = false;
            sendMessageButton.innerText = 'Send Message';
            sendMessageButton.classList.remove('countdown-active'); // Ensure to remove countdown mark on error
        });
    }
}


function rebuildAllCaches() {
  const rebuildAllButton = document.getElementById('rebuildAllCachesBtn');
  if (rebuildAllButton) {
      rebuildAllButton.disabled = true;
      rebuildAllButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> In Surgery';

      fetch('/rebuild-all-caches', { method: 'POST' })
          .then(response => {
              if (!response.ok) {
                  throw new Error('Failed to rebuild all caches');
              }
              return response.json();
          })
          .then(data => {
              if (data.success) {
                  alert('All caches rebuilt successfully');
              } else {
                  alert('Failed to rebuild all caches');
              }
          })
          .catch(error => {
              console.error('Error:', error);
              alert(`Error rebuilding all caches: ${error}`);
          })
          .finally(() => {
              rebuildAllButton.disabled = false;
              rebuildAllButton.textContent = 'Rebuild All Caches';
          });
  }
}
function rebuildGeneralCache() {
    const rebuildGeneralCacheBtn = document.getElementById('rebuildGeneralCacheBtn');
    rebuildGeneralCacheBtn.disabled = true;
    rebuildGeneralCacheBtn.textContent = 'Rebuilding...';

    fetch('/rebuild-general-cache', { method: 'POST' })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to rebuild general cache');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert('General cache rebuilt successfully');
            } else {
                alert('Failed to rebuild general cache');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert(`Error rebuilding general cache: ${error}`);
        })
        .finally(() => {
            rebuildGeneralCacheBtn.disabled = false;
            rebuildGeneralCacheBtn.textContent = 'Rebuild General Cache';
        });
}