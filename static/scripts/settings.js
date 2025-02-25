// This file will handle channel settings only
document.addEventListener('DOMContentLoaded', function() {
    // Initialize channel settings functionality if on the settings page
    const channelSelect = document.getElementById('channelSelect');
    if (channelSelect) {
        // Load channels for selection
        loadChannelList();
        
        // Set up event listeners
        channelSelect.addEventListener('change', function() {
            checkForAddChannelOption(this);
        });
        
        // Handle save button for channel config
        const saveChannelBtn = document.getElementById('saveChannelConfig');
        if (saveChannelBtn) {
            saveChannelBtn.addEventListener('click', saveChannelSettings);
        }
        
        // Handle add channel button
        const addChannelBtn = document.getElementById('addChannelSave');
        if (addChannelBtn) {
            addChannelBtn.addEventListener('click', addNewChannel);
        }
    }
});

// Function to load channel list
function loadChannelList() {
    const channelSelect = document.getElementById('channelSelect');
    if (!channelSelect) return;
    
    fetch('/api/channels')
        .then(response => response.json())
        .then(data => {
            // Clear previous options except the "Add Channel" option
            channelSelect.innerHTML = '<option value="" disabled selected>Select a channel...</option>';
            channelSelect.innerHTML += '<option value="add_channel">Add Channel</option>';
            
            // Add channels from API
            if (data && data.length > 0) {
                data.forEach(channel => {
                    const option = document.createElement('option');
                    option.value = channel.name || channel;
                    option.textContent = channel.name || channel;
                    channelSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading channels:', error);
        });
} 