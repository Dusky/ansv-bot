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
              if (!response.ok) {
                  throw new Error('Failed to rebuild cache');
              }
              return response.json();
          })
          .then(data => {
              if (data.success) {
                  alert(`Cache rebuilt successfully for ${channelName}`);
              } else {
                  alert(`Failed to rebuild cache for ${channelName}`);
              }
          })
          .catch(error => {
              console.error('Error:', error);
              alert(`Error rebuilding cache for ${channelName}: ${error}`);
          })
          .finally(() => {
              rebuildButton.disabled = false;
              rebuildButton.textContent = 'Rebuild Cache';
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