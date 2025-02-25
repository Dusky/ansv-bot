// Show a toast notification
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  
  const toastId = 'toast-' + Date.now();
  const bgClass = type === 'error' ? 'bg-danger' : 
                 type === 'success' ? 'bg-success' : 'bg-info';
  
  const toastHTML = `
    <div id="${toastId}" class="toast align-items-center ${bgClass} text-white border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  
  container.insertAdjacentHTML('beforeend', toastHTML);
  
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
  toast.show();
  
  // Remove the toast from DOM after it's hidden
  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.remove();
  });
} 