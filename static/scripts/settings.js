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
    
    // Predefined preview colors for themes
    themePreviewColors: {
        // Dark Themes
        'darkly': { header: '#375a7f', body: '#22252a' }, // Default Darkly
        'cyborg': { header: '#2A9FD6', body: '#060606' }, // Cyborg Primary Blue, Dark Background
        'slate': { header: '#7A8288', body: '#272B30' },  // Slate Primary Gray, Dark Background
        'solar': { header: '#B58900', body: '#002B36' },  // Solar Primary Yellow, Dark Background
        'superhero': { header: '#DF691A', body: '#2B3E50' },// Superhero Primary Orange, Dark Background
        'vapor': { header: '#AE4FD5', body: '#1A1A2E' },  // Vapor Primary Pink/Purple, Dark Background
        'ansv': { header: 'var(--ansv-primary, #4d37bf)', body: 'var(--ansv-card-bg, #242424)' }, // ANSV specific

        // Light Themes
        'flatly': { header: '#2C3E50', body: '#ECF0F1' }, // Flatly Primary Dark Blue/Gray, Light Background
        'cerulean': { header: '#2FA4E7', body: '#FFFFFF' },// Cerulean Primary Blue, White Background
        'cosmo': { header: '#2780E3', body: '#FFFFFF' },   // Cosmo Primary Blue, White Background
        'journal': { header: '#EB6864', body: '#FFFFFF' }, // Journal Primary Red, White Background
        'litera': { header: '#378B29', body: '#FFFFFF' },  // Litera Primary Green, White Background
        'lumen': { header: '#158CBA', body: '#FFFFFF' },   // Lumen Primary Blue, White Background
        'minty': { header: '#78C2AD', body: '#F8F9FA' },  // Minty Primary Teal, Light Gray Background
        'pulse': { header: '#FF758C', body: '#F8F9FA' },   // Pulse Primary Pink, Light Gray Background
        'sandstone': { header: '#93C54B', body: '#F8F5F0' },// Sandstone Primary Green, Off-White Background
        'simplex': { header: '#D9230F', body: '#FFFFFF' }, // Simplex Primary Red, White Background
        'sketchy': { header: '#333333', body: '#FFFFFF' }, // Sketchy Primary Black, White Background (border is key)
        'spacelab': { header: '#446E9B', body: '#EEEEEE' },// Spacelab Primary Blue/Gray, Light Gray Background
        'united': { header: '#E95420', body: '#FFFFFF' },  // United Primary Orange, White Background
        'yeti': { header: '#008CBA', body: '#FFFFFF' },    // Yeti Primary Blue, White Background
        'zephyr': { header: '#F4A460', body: '#FFFFFF' }   // Zephyr Primary Sandy Brown, White Background
    },
    
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
        fetch(`/set-theme/${themeName}?nocache=${Date.now()}`, { // Changed to use hyphen
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
        container.innerHTML = ''; // Clear existing content

        const createSection = (title, themes, isDarkSection) => {
            const sectionTitle = document.createElement('h5');
            sectionTitle.className = 'mt-4 mb-3 fw-bold'; // Added fw-bold
            sectionTitle.textContent = title;
            container.appendChild(sectionTitle);

            const themesRow = document.createElement('div');
            themesRow.className = 'row g-3'; // Simpler row, column widths defined on children
            container.appendChild(themesRow);

            themes.forEach(themeName => {
                const colDiv = document.createElement('div');
                // Explicit column sizing for Bootstrap 5 grid
                colDiv.className = 'col-6 col-sm-4 col-lg-3 mb-3'; 

                const cardDiv = document.createElement('div');
                cardDiv.className = 'card theme-card h-100 text-center';
                cardDiv.setAttribute('data-theme', themeName);
                cardDiv.style.cursor = 'pointer';
                cardDiv.setAttribute('role', 'button');
                cardDiv.setAttribute('tabindex', '0');
                cardDiv.setAttribute('aria-label', `Select ${themeName} theme`);

                // Simplified single preview block
                const singlePreview = document.createElement('div');
                singlePreview.className = 'theme-preview-single my-3 mx-auto';
                singlePreview.style.width = '85%'; // Adjusted width
                singlePreview.style.height = '50px';
                singlePreview.style.borderRadius = '0.25rem';
                singlePreview.style.border = '1px solid rgba(0,0,0,0.1)';
                singlePreview.style.display = 'flex';
                singlePreview.style.alignItems = 'center';
                singlePreview.style.justifyContent = 'center';

                const previewColors = this.themePreviewColors[themeName];
                let bgColorToTest = '';

                if (previewColors) {
                    singlePreview.style.backgroundColor = previewColors.body; // Use body color for the preview
                    bgColorToTest = previewColors.body;
                    if (themeName === 'ansv') { // ANSV uses CSS variables
                        singlePreview.style.backgroundColor = 'var(--ansv-card-bg, #242424)';
                        bgColorToTest = '#242424'; // Use actual color for contrast test
                    }
                } else {
                    // Fallback colors
                    if (isDarkSection) {
                        singlePreview.style.backgroundColor = '#212529'; // Generic dark body
                        bgColorToTest = '#212529';
                    } else {
                        singlePreview.style.backgroundColor = '#f8f9fa'; // Generic light body
                        bgColorToTest = '#f8f9fa';
                    }
                }

                // Text contrast preview
                const textPreview = document.createElement('small');
                textPreview.textContent = 'Aa';
                
                // Determine text color based on background for preview
                let isDarkBgForText = isDarkSection; // Initial assumption
                if (bgColorToTest.startsWith('#')) {
                    const r = parseInt(bgColorToTest.substring(1, 3), 16);
                    const g = parseInt(bgColorToTest.substring(3, 5), 16);
                    const b = parseInt(bgColorToTest.substring(5, 7), 16);
                    isDarkBgForText = (r * 0.299 + g * 0.587 + b * 0.114) < 140;
                } else if (bgColorToTest.startsWith('var(--ansv-card-bg')) {
                     isDarkBgForText = true; // ANSV is dark
                }
                textPreview.style.color = isDarkBgForText ? '#f8f9fa' : '#212529';
                singlePreview.appendChild(textPreview);

                // Special handling for Sketchy theme's border
                if (themeName === 'sketchy') {
                    cardDiv.style.borderStyle = 'solid';
                    cardDiv.style.borderWidth = '2px';
                    cardDiv.style.borderColor = '#333333';
                    singlePreview.style.border = '2px dashed #333';
                } else {
                     // Ensure default card border for non-sketchy themes if needed,
                     // but Bootstrap classes usually handle this.
                }

                cardDiv.appendChild(singlePreview);

                const cardBodyDiv = document.createElement('div');
                cardBodyDiv.className = 'card-body p-2';
                const titleH6 = document.createElement('h6');
                titleH6.className = 'card-title mb-0 theme-name-display text-capitalize small';
                titleH6.textContent = themeName;
                cardBodyDiv.appendChild(titleH6);
                cardDiv.appendChild(cardBodyDiv);

                colDiv.appendChild(cardDiv);
                themesRow.appendChild(colDiv);

                cardDiv.addEventListener('keypress', function(event) {
                    if (event.key === 'Enter' || event.keyCode === 13) {
                        this.click();
                    }
                });
            });
        };

        // Create Light Themes Section
        createSection('Light Themes', this.lightThemes, false);

        // Create Dark Themes Section (includes 'ansv')
        createSection('Dark Themes', this.darkThemes, true);
        
        console.log(`Populated theme cards into Light and Dark sections.`);
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
