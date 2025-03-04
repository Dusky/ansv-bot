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
        
        // No event listeners for buttons - using onclick handlers directly
    }
});

// Function to change theme - making global so it's accessible from other scripts
window.changeTheme = function() {
    const themeName = document.getElementById('themeSelect').value;
    
    // Show loading indicator
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
    
    console.log("Changing theme to:", themeName);
    
    // First, set a local cookie to ensure it works even if the fetch fails
    document.cookie = `theme=${themeName}; path=/; max-age=${30*24*60*60}`;
    
    // Apply some immediate visual changes
    applyThemeChanges(themeName);
    
    // Save theme preference on server
    fetch(`/set_theme/${themeName}?nocache=${Date.now()}`, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log(`Theme saved as ${themeName}`);
        
        // Only show the toast if this was triggered by a user action, not by a background check
        const isUserAction = document.activeElement && 
                            (document.activeElement.id === 'themeSelect' || 
                             document.activeElement.classList.contains('theme-card'));
        if (isUserAction) {
            showToast('Theme updated successfully', 'success');
        }
        
        // After success, reload the page to fully apply the theme
        setTimeout(() => {
            window.location.href = window.location.pathname + '?refresh=' + Date.now();
        }, 500); // Short delay to allow the toast to be seen
    })
    .catch(error => {
        console.error('Error setting theme:', error);
        showToast('Error changing theme. Reloading to apply local changes.', 'warning');
        
        // Even if server request fails, try to reload with the cookie we set
        setTimeout(() => {
            window.location.href = window.location.pathname + '?refresh=' + Date.now();
        }, 1000);
    })
    .finally(() => {
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
    });
}

// Function to select and apply a theme via the new UI
window.selectAndApplyTheme = function(themeName) {
    // Update the hidden select element
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        themeSelect.value = themeName;
        
        // Update active state on theme cards
        const allThemeCards = document.querySelectorAll('.theme-card');
        allThemeCards.forEach(card => {
            card.classList.remove('active');
        });
        
        // Find the clicked card and make it active
        const selectedCard = document.querySelector(`.theme-card[onclick*="${themeName}"]`);
        if (selectedCard) {
            selectedCard.classList.add('active');
        }
        
        // Apply the theme
        window.changeTheme();
    } else {
        console.error("Theme select element not found!");
    }
}

// Use the global showToast function if available, or provide our own
function showToast(message, type = 'info') {
    // Check if the notification.js showToast function exists
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`Toast (${type}): ${message}`);
        // Simple alert fallback if toast function not available
        if (type === 'error') {
            alert(`Error: ${message}`);
        }
    }
}

// Function to apply theme changes locally before reload
function applyThemeChanges(themeName) {
    // First remove any existing theme class
    document.body.classList.remove('theme-ansv');
    document.documentElement.removeAttribute('data-theme');
    
    if (themeName === 'ansv') {
        // Apply custom ANSV theme
        document.body.classList.add('theme-ansv');
        document.documentElement.setAttribute('data-theme', 'ansv');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    } else {
        // For Bootswatch themes
        const darkThemes = ['darkly', 'cyborg', 'slate', 'solar', 'superhero', 'vapor'];
        document.documentElement.setAttribute('data-bs-theme', 
            darkThemes.includes(themeName) ? 'dark' : 'light');
            
        // Try to update Bootstrap CSS
        const bootstrapCSS = document.getElementById('bootstrapCSS');
        if (bootstrapCSS) {
            bootstrapCSS.href = `https://bootswatch.com/5/${themeName}/bootstrap.min.css`;
        }
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
    
    // UI Preferences initialization
    initUIPreferences();
});

// Function to select theme from visual previews - making global
window.selectTheme = function(theme) {
    console.log("Setting theme select to:", theme);
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        themeSelect.value = theme;
        window.changeTheme(); // Call the global version
    } else {
        console.error("Theme select element not found!");
    }
}

// Initialize UI preferences 
function initUIPreferences() {
    // Only proceed if we're on the settings page
    if (!document.getElementById('enableAnimations')) return;
    
    // Load saved preferences
    const enableAnimations = localStorage.getItem('enableAnimations') !== 'false';
    const enableToasts = localStorage.getItem('enableToasts') !== 'false';
    const compactMode = localStorage.getItem('compactMode') === 'true';
    
    // Set checkboxes
    document.getElementById('enableAnimations').checked = enableAnimations;
    document.getElementById('enableToasts').checked = enableToasts;
    document.getElementById('compactMode').checked = compactMode;
    
    // Apply preferences to the UI
    document.body.classList.toggle('disable-animations', !enableAnimations);
    document.body.classList.toggle('compact-mode', compactMode);
    
    // Set up change listeners
    document.getElementById('enableAnimations').addEventListener('change', function() {
        localStorage.setItem('enableAnimations', this.checked);
        document.body.classList.toggle('disable-animations', !this.checked);
    });
    
    document.getElementById('enableToasts').addEventListener('change', function() {
        localStorage.setItem('enableToasts', this.checked);
    });
    
    document.getElementById('compactMode').addEventListener('change', function() {
        localStorage.setItem('compactMode', this.checked);
        document.body.classList.toggle('compact-mode', this.checked);
    });
}