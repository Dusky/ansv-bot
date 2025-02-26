// This file handles settings including themes and channel settings
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

// Function to change theme
function changeTheme() {
    const themeName = document.getElementById('themeSelect').value;
    
    // Show loading indicator
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
    
    // Handle custom ANSV theme
    if (themeName === 'ansv') {
        // Apply custom theme classes
        document.body.classList.add('theme-ansv');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
        
        // Set CSS variables
        document.documentElement.setAttribute('data-theme', 'ansv');
        
        // Hide loading immediately after applying local styles
        fetch(`/set_theme/${themeName}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('Theme set to ANSV Custom');
        })
        .catch(error => {
            console.error('Error setting theme:', error);
            showToast('Error changing theme. Please try again.', 'error');
        })
        .finally(() => {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        });
    } else {
        // For Bootswatch themes, remove custom theme class
        document.body.classList.remove('theme-ansv');
        document.documentElement.removeAttribute('data-theme');
        
        // Set dark/light mode based on theme
        const darkThemes = ['darkly', 'cyborg', 'slate', 'solar', 'superhero', 'vapor'];
        document.documentElement.setAttribute('data-bs-theme', darkThemes.includes(themeName) ? 'dark' : 'light');
        
        // Update Bootstrap CSS
        const bootstrapCSS = document.getElementById('bootstrapCSS');
        if (bootstrapCSS) {
            bootstrapCSS.href = `https://bootswatch.com/5/${themeName}/bootstrap.min.css`;
        }
        
        // Save theme preference on server
        fetch(`/set_theme/${themeName}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log(`Theme set to ${themeName}`);
        })
        .catch(error => {
            console.error('Error setting theme:', error);
            showToast('Error changing theme. Please try again.', 'error');
        })
        .finally(() => {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        });
    }
}

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

// Function to check if the current theme is the custom ANSV theme
function isAnsvTheme() {
    const currentTheme = document.cookie
        .split('; ')
        .find(row => row.startsWith('theme='))
        ?.split('=')[1];
    
    return currentTheme === 'ansv';
}

// Initialize the theme on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if using ANSV theme
    if (isAnsvTheme()) {
        document.body.classList.add('theme-ansv');
        document.documentElement.setAttribute('data-theme', 'ansv');
    }
});