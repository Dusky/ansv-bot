/**
 * Compatibility and Error Handling Fix
 * This script adds error handling and fixes inconsistencies across the UI
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Compatibility fix loaded');
    
    // Add global error handler
    window.addEventListener('error', function(event) {
        console.error('Global error caught:', event.error);
        showToast('An error occurred: ' + event.error?.message || 'Unknown error', 'error');
    });
    
    // Create notification namespace if it doesn't exist
    window.notificationSystem = window.notificationSystem || {};
    
    // Add showToast function to namespace if it doesn't exist
    if (typeof window.notificationSystem.showToast !== 'function') {
        window.notificationSystem.showToast = function(message, type = 'info') {
            console.log(`Toast (${type}): ${message}`);
            
            // Check if Bootstrap is available
            if (typeof bootstrap !== 'undefined') {
                const toast = document.createElement('div');
                toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type}`;
                toast.setAttribute('role', 'alert');
                toast.setAttribute('aria-live', 'assertive');
                toast.setAttribute('aria-atomic', 'true');
                
                toast.innerHTML = `
                    <div class="d-flex">
                        <div class="toast-body">${message}</div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                `;
                
                // Create toast container if it doesn't exist
                let toastContainer = document.getElementById('toastContainer');
                if (!toastContainer) {
                    toastContainer = document.createElement('div');
                    toastContainer.id = 'toastContainer';
                    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                    document.body.appendChild(toastContainer);
                }
                
                toastContainer.appendChild(toast);
                
                const bsToast = new bootstrap.Toast(toast, {
                    autohide: true,
                    delay: 3000
                });
                bsToast.show();
            } else {
                // Fallback to alert for notifications
                if (type === 'error') {
                    console.error(message);
                } else {
                    alert(message);
                }
            }
        };
        
        // Also set window.showToast to point to our implementation in the namespace
        window.showToast = window.notificationSystem.showToast;
    }
    
    // Fix endpoint inconsistencies in all fetch calls
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        // Normalize endpoint naming conventions
        if (url === '/start-bot') url = '/start_bot';
        if (url === '/stop-bot') url = '/stop_bot';
        if (url === '/get-channels') url = '/api/channels';  // Redirect to the better endpoint
        
        console.log(`Fetch request to: ${url}`);
        return originalFetch(url, options)
            .catch(error => {
                console.error(`Fetch error for ${url}:`, error);
                throw error;
            });
    };
}); 