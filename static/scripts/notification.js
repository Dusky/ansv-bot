/**
 * Centralized notification system for ANSV Bot
 * Provides a single implementation for toast notifications, confirmations, status updates, etc.
 * Other files should use these functions instead of implementing their own.
 */

// Create a namespace for notification functions to avoid global conflicts
window.notificationSystem = window.notificationSystem || {};

// Track recently shown toasts to prevent duplicates
window.notificationSystem.recentToasts = [];

/**
 * Primary toast notification function with enhanced user experience
 * @param {string} message - The message to display
 * @param {string} type - The type of notification: 'success', 'error', 'warning', or 'info'
 * @param {number} duration - How long to show the toast in milliseconds
 * @param {Object} options - Additional options for enhanced UX
 * @param {string} options.action - Optional action button text
 * @param {Function} options.actionCallback - Callback for action button
 * @param {boolean} options.persistent - Whether the toast should stay until dismissed
 * @returns {string} The ID of the created toast element
 */
window.notificationSystem.showToast = function(message, type = 'info', duration = 5000, options = {}) {
    console.log(`Showing toast: ${message} (${type})`);
    
    // DUPLICATE PREVENTION: Check if we've shown this message recently
    const now = Date.now();
    const toastSignature = `${message}|${type}`;
    
    // Filter out old toasts (older than 1 second)
    window.notificationSystem.recentToasts = window.notificationSystem.recentToasts.filter(
        toast => now - toast.timestamp < 1000
    );
    
    // Check for duplicate
    const isDuplicate = window.notificationSystem.recentToasts.some(
        toast => toast.signature === toastSignature
    );
    
    if (isDuplicate) {
        console.log(`Suppressing duplicate toast: ${message}`);
        return null;
    }
    
    // Add this toast to recent toasts
    window.notificationSystem.recentToasts.push({
        signature: toastSignature,
        timestamp: now
    });
    
    // Get or create toast container
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }
    
    // Create unique ID for this toast
    const toastId = 'toast-' + now;
    
    // Set color and icon based on type
    let bgClass = 'bg-primary';
    let icon = 'info-circle';
    
    switch (type) {
        case 'success':
            bgClass = 'bg-success';
            icon = 'check-circle';
            break;
        case 'error':
            bgClass = 'bg-danger';
            icon = 'exclamation-circle';
            break;
        case 'warning':
            bgClass = 'bg-warning';
            icon = 'exclamation-triangle';
            break;
        case 'info':
        default:
            bgClass = 'bg-info';
            icon = 'info-circle';
    }
    
    // Create toast HTML
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center ${bgClass} text-white border-0 fade-in" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${icon} me-2"></i> ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    // Add to container
    container.insertAdjacentHTML('beforeend', toastHTML);
    
    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    
    try {
        // Use Bootstrap's Toast if available
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(toastElement, { 
                autohide: true, 
                delay: duration 
            });
            toast.show();
        } else {
            // Fallback for when Bootstrap isn't available
            console.log(`Toast (${type}): ${message}`);
            if (type === 'error') {
                alert(`Error: ${message}`);
            }
        }
        
        // Remove the toast from DOM after it's hidden or after timeout
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
        
        // Backup timeout in case the hidden event doesn't fire
        setTimeout(() => {
            if (document.getElementById(toastId)) {
                toastElement.remove();
            }
        }, duration + 1000);
    } catch (e) {
        console.error('Error showing toast:', e);
        // Fallback if something goes wrong with Bootstrap
        console.log(`Toast (${type}): ${message}`);
        if (type === 'error') {
            alert(`Error: ${message}`);
        }
    }
    
    return toastId;
};

/**
 * Enhanced error handling with user-friendly messages and actionable advice
 * @param {Error|string} error - The error object or message
 * @param {string} context - Context where the error occurred (e.g., 'bot_control', 'tts_generation')
 * @param {Object} options - Additional options for error handling
 */
window.notificationSystem.handleError = function(error, context = 'general', options = {}) {
    let userMessage = '';
    let technicalMessage = '';
    let actionButton = null;
    
    // Extract error message
    if (typeof error === 'string') {
        technicalMessage = error;
    } else if (error?.message) {
        technicalMessage = error.message;
    } else {
        technicalMessage = 'An unknown error occurred';
    }
    
    // Context-specific user-friendly messages
    switch (context) {
        case 'bot_control':
            if (technicalMessage.includes('not running')) {
                userMessage = 'Bot is not currently running. ';
                actionButton = {
                    text: 'Start Bot',
                    callback: () => window.BotControl?.startBot?.()
                };
            } else if (technicalMessage.includes('connection')) {
                userMessage = 'Connection issue detected. Check your internet connection and try again.';
            } else {
                userMessage = 'Bot control operation failed. ';
            }
            break;
            
        case 'tts_generation':
            if (technicalMessage.includes('model')) {
                userMessage = 'TTS model not loaded. This may take a moment to download.';
                actionButton = {
                    text: 'Download Models',
                    callback: () => fetch('/download-models', {method: 'POST'})
                };
            } else {
                userMessage = 'Voice generation failed. ';
            }
            break;
            
        case 'api_request':
            if (technicalMessage.includes('404')) {
                userMessage = 'Requested resource not found. Please refresh the page.';
                actionButton = {
                    text: 'Refresh',
                    callback: () => window.location.reload()
                };
            } else if (technicalMessage.includes('500')) {
                userMessage = 'Server error occurred. Please try again in a moment.';
            } else if (technicalMessage.includes('network')) {
                userMessage = 'Network connection problem. Check your internet connection.';
            } else {
                userMessage = 'Request failed. ';
            }
            break;
            
        case 'markov_generation':
            userMessage = 'Message generation failed. The bot may need more training data.';
            break;
            
        default:
            userMessage = 'An error occurred. ';
    }
    
    // Append suggestion to check logs for technical users
    if (!actionButton) {
        userMessage += 'Check the browser console for technical details.';
    }
    
    // Show the error with enhanced options
    const toastOptions = {
        persistent: true, // Errors should stay visible
        ...options
    };
    
    if (actionButton) {
        toastOptions.action = actionButton.text;
        toastOptions.actionCallback = actionButton.callback;
    }
    
    console.error(`Error in ${context}:`, technicalMessage);
    return this.showToast(userMessage, 'error', 10000, toastOptions);
};

/**
 * Show success message with optional next steps
 * @param {string} message - Success message
 * @param {Object} options - Additional options
 */
window.notificationSystem.showSuccess = function(message, options = {}) {
    return this.showToast(message, 'success', 5000, options);
};

/**
 * Show loading state notification
 * @param {string} message - Loading message
 * @returns {string} Toast ID for updating/dismissing
 */
window.notificationSystem.showLoading = function(message) {
    return this.showToast(`⏳ ${message}`, 'info', 0, { persistent: true });
};

/**
 * Update existing loading notification with completion
 * @param {string} toastId - ID of loading toast to update
 * @param {string} message - Completion message
 * @param {string} type - Type of completion ('success' or 'error')
 */
window.notificationSystem.completeLoading = function(toastId, message, type = 'success') {
    // Remove the loading toast
    const loadingToast = document.getElementById(toastId);
    if (loadingToast) {
        loadingToast.remove();
    }
    
    // Show completion message
    return this.showToast(message, type, 5000);
};

// Export enhanced functions to global window object for backward compatibility
window.showToast = window.notificationSystem.showToast;
window.handleError = window.notificationSystem.handleError;
window.showSuccess = window.notificationSystem.showSuccess;
window.showLoading = window.notificationSystem.showLoading;
window.completeLoading = window.notificationSystem.completeLoading;

// Local function for internal use
function showToast(message, type = 'info', duration = 5000) {
    return window.notificationSystem.showToast(message, type, duration);
}

// Enhanced confirmation modal
function showConfirmation(title, message, confirmCallback, cancelCallback = null) {
    // Check if modal already exists, create if not
    let modal = document.getElementById('confirmationModal');
    
    if (!modal) {
        console.warn('Confirmation modal not found in DOM. Will use simple confirm() instead.');
        if (confirm(message)) {
            if (typeof confirmCallback === 'function') {
                confirmCallback();
            }
        } else {
            if (typeof cancelCallback === 'function') {
                cancelCallback();
            }
        }
        return;
    }
    
    // Set content
    const titleEl = modal.querySelector('.modal-title');
    const messageEl = modal.querySelector('.modal-body');
    
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;
    
    // Create new Bootstrap modal
    const modalInstance = new bootstrap.Modal(modal);
    
    // Handle confirm button
    const confirmButton = modal.querySelector('#confirmButton');
    const cancelButton = modal.querySelector('button[data-bs-dismiss="modal"]');
    
    if (confirmButton) {
        // Remove any existing event listeners
        const newConfirmButton = confirmButton.cloneNode(true);
        confirmButton.parentNode.replaceChild(newConfirmButton, confirmButton);
        
        // Add new confirm event listener
        newConfirmButton.addEventListener('click', function() {
            modalInstance.hide();
            if (typeof confirmCallback === 'function') {
                confirmCallback();
            }
        });
    }
    
    if (cancelButton) {
        // Remove any existing event listeners
        const newCancelButton = cancelButton.cloneNode(true);
        cancelButton.parentNode.replaceChild(newCancelButton, cancelButton);
        
        // Add new cancel event listener
        newCancelButton.addEventListener('click', function() {
            if (typeof cancelCallback === 'function') {
                cancelCallback();
            }
        });
    }
    
    // Show modal
    modalInstance.show();
    
    return modalInstance;
}

// Status indicator updater
function updateStatusIndicator(elementId, status, message = null) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    // Remove all status classes
    element.classList.remove('text-success', 'text-danger', 'text-warning', 'text-info', 'text-muted');
    
    // Add appropriate class
    switch (status) {
        case 'success':
            element.classList.add('text-success');
            break;
        case 'error':
            element.classList.add('text-danger');
            break;
        case 'warning':
            element.classList.add('text-warning');
            break;
        case 'info':
            element.classList.add('text-info');
            break;
        default:
            element.classList.add('text-muted');
    }
    
    // Update text if message provided
    if (message) {
        element.textContent = message;
    }
}

// Initialize tooltips on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Initialize theme toggle functionality
    initThemeToggle();
    
    // Initialize audio toggle
    initAudioToggle();
});

// Theme toggle functionality - DEPRECATED
// Now handled by event_listener.js and settings.js - keeping this stub for backward compatibility
function initThemeToggle() {
    console.log("DEPRECATED: initThemeToggle in notification.js is no longer used");
    // Do nothing - theme toggle is now handled by event_listener.js
}

// Update theme toggle button appearance - DEPRECATED
function updateThemeToggle() {
    console.log("DEPRECATED: updateThemeToggle in notification.js is no longer used");
    // Do nothing - theme toggle is now handled by event_listener.js
}

// Initialize audio toggle
function initAudioToggle() {
    const autoplayCheckbox = document.getElementById('autoplay');
    const muteIcon = document.getElementById('muteIcon');
    const unmuteIcon = document.getElementById('unmuteIcon');
    
    if (!autoplayCheckbox || !muteIcon || !unmuteIcon) return;
    
    // Get stored preference
    const autoplayEnabled = localStorage.getItem('audioAutoplay') !== 'false';
    autoplayCheckbox.checked = autoplayEnabled;
    
    // Update UI
    if (autoplayEnabled) {
        muteIcon.classList.add('d-none');
        unmuteIcon.classList.remove('d-none');
    } else {
        muteIcon.classList.remove('d-none');
        unmuteIcon.classList.add('d-none');
    }
    
    // Add change handler
    autoplayCheckbox.addEventListener('change', function() {
        localStorage.setItem('audioAutoplay', this.checked);
        
        if (this.checked) {
            muteIcon.classList.add('d-none');
            unmuteIcon.classList.remove('d-none');
        } else {
            muteIcon.classList.remove('d-none');
            unmuteIcon.classList.add('d-none');
        }
    });
}