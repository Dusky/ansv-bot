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
        if (document.getElementById('themeCardContainer')) { // Check if we are on settings page
            this.populateThemeCards(); // Populate cards first
            this.setupThemeCards();    // Then attach listeners
            this.updateActiveThemeCard(this.currentTheme); // Then update active state
        }
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
            
            // Apply theme changes without page reload
            console.log("Theme change successful - applying without page reload");
        })
        .catch(error => {
            console.error('Error setting theme:', error);
            window.notificationSystem.showToast('Error changing theme. Reloading to apply local changes.', 'warning');
            
            // Apply theme changes without page reload
            console.log("Theme change failed but applying local changes without reload");
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
        
        // First remove any existing theme class from html element
        document.documentElement.classList.remove('theme-ansv');
        document.documentElement.removeAttribute('data-theme');
        
        if (themeName === 'ansv') {
            // Apply custom ANSV theme to html element
            document.documentElement.classList.add('theme-ansv');
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
            card.classList.remove('border-primary', 'shadow-sm'); // Remove visual cues
        });
        
        // Add active class to selected card
        themeCards.forEach(card => {
            const cardTheme = card.getAttribute('data-theme');
            if (cardTheme === themeName) {
                card.classList.add('active');
                card.classList.add('border-primary', 'shadow-sm'); // Add visual cues
            }
            // Removed the 'else' block that was causing the error by trying to read 'onClick' attribute
            // The data-theme attribute is now the sole source for identifying the active card.
        });
    },

    populateThemeCards: function() {
        const container = document.getElementById('themeCardContainer');
        if (!container) {
            console.warn("Theme card container 'themeCardContainer' not found on this page.");
            return;
        }

        container.innerHTML = ''; // Clear existing cards

        const allThemes = [...new Set([...this.lightThemes, ...this.darkThemes])];

        allThemes.forEach(themeName => {
            const colDiv = document.createElement('div');
            // Use Bootstrap's responsive column classes for better layout
            colDiv.className = 'col-6 col-md-4 col-lg-3 mb-3'; 

            const cardDiv = document.createElement('div');
            cardDiv.className = 'card theme-card h-100 text-center'; // Ensure consistent height and center text
            cardDiv.setAttribute('data-theme', themeName);
            cardDiv.style.cursor = 'pointer';
            cardDiv.setAttribute('role', 'button');
            cardDiv.setAttribute('tabindex', '0'); // Make it focusable
            cardDiv.setAttribute('aria-label', `Select ${themeName} theme`);

            // Visual preview block
            const previewBlock = document.createElement('div');
            previewBlock.className = 'theme-preview-block p-3'; // Added padding
            
            // Simulate card header
            const previewHeader = document.createElement('div');
            previewHeader.style.height = '20px';
            previewHeader.style.marginBottom = '5px';
            previewHeader.style.borderRadius = '0.2rem';
            
            // Simulate card body
            const previewBody = document.createElement('div');
            previewBody.style.height = '30px';
            previewBody.style.borderRadius = '0.2rem';

            // Basic color assignment for preview elements
            if (themeName === 'ansv') {
                previewHeader.style.backgroundColor = 'var(--ansv-primary, #4d37bf)';
                previewBody.style.backgroundColor = 'var(--ansv-card-bg, #242424)';
            } else if (this.darkThemes.includes(themeName)) {
                previewHeader.style.backgroundColor = '#375a7f'; // Example dark theme header
                previewBody.style.backgroundColor = '#22252a';   // Example dark theme body
            } else {
                previewHeader.style.backgroundColor = '#0d6efd'; // Example light theme header (Bootstrap primary)
                previewBody.style.backgroundColor = '#f8f9fa';   // Example light theme body
            }
            previewBlock.appendChild(previewHeader);
            previewBlock.appendChild(previewBody);

            const cardBodyDiv = document.createElement('div');
            cardBodyDiv.className = 'card-body p-2'; // Reduced padding for card body

            const titleH6 = document.createElement('h6');
            titleH6.className = 'card-title mb-0 theme-name-display text-capitalize small'; // Smaller text
            titleH6.textContent = themeName;
            
            cardDiv.appendChild(previewBlock);
            cardBodyDiv.appendChild(titleH6);
            cardDiv.appendChild(cardBodyDiv);
            colDiv.appendChild(cardDiv);
            container.appendChild(colDiv);

            // Add keypress event for accessibility (Enter key to select)
            cardDiv.addEventListener('keypress', function(event) {
                if (event.key === 'Enter' || event.keyCode === 13) {
                    this.click(); // Trigger the click event attached in setupThemeCards
                }
            });
        });
        console.log(`Populated ${allThemes.length} theme cards.`);
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
    // Check if using ANSV theme and apply if necessary (redundant if ThemeManager.init runs, but safe)
    if (isAnsvTheme()) {
        // Ensure this matches how ThemeManager.applyTheme does it
        document.documentElement.classList.add('theme-ansv');
        document.documentElement.setAttribute('data-theme', 'ansv');
        document.documentElement.setAttribute('data-bs-theme', 'dark'); // ANSV is a dark theme
    }
    
    // UI Preferences initialization
    initUIPreferences();

    // Initialize ThemeManager if it's present on the page (i.e., we are on settings.html or similar)
    if (window.ThemeManager && typeof window.ThemeManager.init === 'function') {
        // Only fully initialize (which includes populating cards) if the card container exists.
        // ThemeManager.applyTheme and toggle setup should run on all pages if ThemeManager is global.
        // However, settings.js is typically only loaded on settings.html.
        console.log("DOMContentLoaded: Initializing ThemeManager from settings.js");
        window.ThemeManager.init();
    } else {
        console.error("ThemeManager not found or init method is missing.");
    }
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
