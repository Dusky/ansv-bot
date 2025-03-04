/**
 * Enhanced notification system for ANSV Bot
 * Handles toast notifications, confirmation modals, and status indicators
 */

// Show a toast notification
function showToast(message, type = 'info', duration = 5000) {
    // Get or create toast container
    let container = document.getElementById('toastContainer');
    if (!container) return;
    
    // Create unique ID for this toast
    const toastId = 'toast-' + Date.now();
    
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
    const toast = new bootstrap.Toast(toastElement, { 
        autohide: true, 
        delay: duration 
    });
    toast.show();
    
    // Remove the toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
    
    return toastId;
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