/**
 * Centralized settings management
 * Handles theme switching and settings page functionality
 */

// Create a centralized theme management system
window.ThemeManager = {
    // Current theme
    currentTheme: 'flatly', // Default bootstrap theme
    
    // Available themes
    darkThemes: ['darkly', 'cyborg', 'slate', 'solar', 'superhero', 'vapor', 'ansv'],
    lightThemes: ['flatly', 'cerulean', 'cosmo', 'journal', 'litera', 'lumen', 'minty', 'pulse', 'sandstone', 'simplex', 'sketchy', 'spacelab', 'united', 'yeti', 'zephyr'],
    
    // Initialize theme system
    init: function() {
        console.log("ThemeManager initializing");
        
        // Get current theme from cookie
        this.currentTheme = this.getThemeFromCookie() || 'flatly';
        
        // Apply theme immediately
        this.applyTheme(this.currentTheme, false);
        
        // Set up theme toggle button if it exists
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-bs-theme');
                if (currentTheme === 'dark') {
                    // Switch to light theme
                    this.switchToDarkMode(false);
                } else {
                    // Switch to dark theme
                    this.switchToDarkMode(true);
                }
            });
            
            // Initialize button state
            this.updateThemeToggleButton();
        }
        
        // Set up theme selectors
        const themeSelect = document.getElementById('themeSelect');
        if (themeSelect) {
            themeSelect.value = this.currentTheme;
            themeSelect.addEventListener('change', () => {
                this.changeTheme(themeSelect.value);
            });
        }
        
        // Set up visual theme cards
        this.setupThemeCards();
    },
    
    // Get theme from cookie
    getThemeFromCookie: function() {
        return document.cookie
            .split('; ')
            .find(row => row.startsWith('theme='))
            ?.split('=')[1];
    },
    
    // Change theme with visual feedback
    changeTheme: function(themeName) {
        if (!themeName) return;
        
        // Show loading indicator
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
        }
        
        console.log("Changing theme to:", themeName);
        
        // First, set a local cookie to ensure it works even if the fetch fails
        document.cookie = `theme=${themeName}; path=/; max-age=${30*24*60*60}`;
        
        // Apply visual changes immediately
        this.applyTheme(themeName, true);
        
        // Update theme cards if on settings page
        this.updateActiveThemeCard(themeName);
        
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
            
            // Only show toast if this was triggered by a user action
            const isUserAction = document.activeElement && 
                               (document.activeElement.id === 'themeSelect' || 
                                document.activeElement.classList.contains('theme-card'));
            if (isUserAction) {
                window.notificationSystem.showToast('Theme updated successfully', 'success');
            }
            
            // After success, reload the page to fully apply the theme
            setTimeout(() => {
                window.location.href = window.location.pathname + '?refresh=' + Date.now();
            }, 500); // Short delay to allow the toast to be seen
        })
        .catch(error => {
            console.error('Error setting theme:', error);
            window.notificationSystem.showToast('Error changing theme. Reloading to apply local changes.', 'warning');
            
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
    },
    
    // Apply theme changes locally
    applyTheme: function(themeName, isTransition = false) {
        // Update the current theme
        this.currentTheme = themeName;
        
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
            const isDarkTheme = this.darkThemes.includes(themeName);
            document.documentElement.setAttribute('data-bs-theme', isDarkTheme ? 'dark' : 'light');
                
            // Try to update Bootstrap CSS if not during initial load
            if (isTransition) {
                const bootstrapCSS = document.getElementById('bootstrapCSS');
                if (bootstrapCSS) {
                    bootstrapCSS.href = `https://bootswatch.com/5/${themeName}/bootstrap.min.css`;
                }
            }
        }
        
        // Update theme toggle button
        this.updateThemeToggleButton();
    },
    
    // Switch between light and dark mode
    switchToDarkMode: function(darkMode) {
        // Pick a theme from either dark or light list
        const themeList = darkMode ? this.darkThemes : this.lightThemes;
        const newTheme = themeList[0]; // Just pick the first one for simplicity
        
        // Apply the new theme
        this.changeTheme(newTheme);
    },
    
    // Update theme toggle button appearance
    updateThemeToggleButton: function() {
        const themeToggle = document.getElementById('themeToggle');
        if (!themeToggle) return;
        
        const isDarkTheme = this.darkThemes.includes(this.currentTheme);
        
        // Update button appearance
        if (isDarkTheme) {
            themeToggle.className = "btn btn-sm btn-outline-light";
            themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            themeToggle.setAttribute('title', 'Switch to Light Theme');
        } else {
            themeToggle.className = "btn btn-sm btn-outline-light";
            themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            themeToggle.setAttribute('title', 'Switch to Dark Theme');
        }
    },
    
    // Set up theme cards for visual selection
    setupThemeCards: function() {
        const themeCards = document.querySelectorAll('.theme-card');
        if (themeCards.length === 0) return;
        
        // Add click handlers
        themeCards.forEach(card => {
            card.addEventListener('click', (e) => {
                // Extract theme name from onClick attribute or data attribute
                let themeName = card.getAttribute('data-theme');
                if (!themeName) {
                    // Try to extract from onClick attribute as fallback
                    const onClickAttr = card.getAttribute('onClick');
                    if (onClickAttr) {
                        const match = onClickAttr.match(/selectTheme\(['"](.+?)['"]\)/);
                        if (match && match[1]) {
                            themeName = match[1];
                        }
                    }
                }
                
                if (themeName) {
                    this.changeTheme(themeName);
                }
            });
        });
        
        // Mark the active theme card
        this.updateActiveThemeCard(this.currentTheme);
    },
    
    // Update which theme card is active
    updateActiveThemeCard: function(themeName) {
        const themeCards = document.querySelectorAll('.theme-card');
        if (themeCards.length === 0) return;
        
        // Remove active class from all cards
        themeCards.forEach(card => {
            card.classList.remove('active');
        });
        
        // Add active class to selected card
        themeCards.forEach(card => {
            const cardTheme = card.getAttribute('data-theme');
            if (cardTheme === themeName) {
                card.classList.add('active');
            } else {
                // Try to extract from onClick attribute as fallback
                const onClickAttr = card.getAttribute('onClick');
                if (onClickAttr && onClickAttr.includes(`"${themeName}"`) || onClickAttr.includes(`'${themeName}'`)) {
                    card.classList.add('active');
                }
            }
        });
    }
};

// Legacy support for older code that might use these functions
window.changeTheme = function() {
    const themeName = document.getElementById('themeSelect').value;
    window.ThemeManager.changeTheme(themeName);
};

window.selectAndApplyTheme = function(themeName) {
    window.ThemeManager.changeTheme(themeName);
};

// Helper for displaying notifications
function displayNotification(message, type = 'info') {
    // Always use the global notification system when available
    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
        window.notificationSystem.showToast(message, type);
    } 
    // Fall back to global showToast
    else if (typeof window.showToast === 'function') {
        // Only call if it's not this same function
        window.showToast(message, type);
    } 
    // Use console and alert as a final fallback
    else {
        console.log(`Toast (${type}): ${message}`);
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