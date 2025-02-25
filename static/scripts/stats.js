// Function to load stats data
function loadStats() {
  const statsContainer = document.getElementById('statsContainer');
  const loadingIndicator = document.getElementById('loadingIndicator');
  
  if (!statsContainer) {
    console.warn("Stats container not found");
    return;
  }
  
  // Show loading indicator
  if (loadingIndicator) loadingIndicator.style.display = 'block';
  
  fetch('/get-stats')
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load stats data');
      }
      return response.json();
    })
    .then(data => {
      console.log("Stats data:", data);
      
      // Clear existing rows
      statsContainer.innerHTML = '';
      
      // Add rows for each channel
      if (data.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = '<td colspan="6" class="text-center">No channel data available</td>';
        statsContainer.appendChild(emptyRow);
      } else {
        data.forEach(channel => {
          const row = document.createElement('tr');
          row.innerHTML = `
            <td>${channel.name}</td>
            <td>${channel.cache_file || 'N/A'}</td>
            <td>${channel.log_file || 'N/A'}</td>
            <td>${channel.cache_size || '0 KB'}</td>
            <td>${channel.line_count || '0'}</td>
            <td>
              <button class="btn btn-primary btn-sm me-1" data-channel="${channel.name}" onclick="sendMarkovMessage('${channel.name}')">
                Send Message
              </button>
              <button class="btn btn-secondary btn-sm" data-channel="${channel.name}" data-action="rebuild" onclick="rebuildCacheForChannel('${channel.name}')">
                Rebuild Model
              </button>
            </td>
          `;
          statsContainer.appendChild(row);
        });
      }
    })
    .catch(error => {
      console.error('Error loading stats:', error);
      statsContainer.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load data.</td></tr>';
    })
    .finally(() => {
      // Hide loading indicator
      if (loadingIndicator) loadingIndicator.style.display = 'none';
    });
}

// Load stats when the page loads
document.addEventListener('DOMContentLoaded', function() {
  loadStats();
}); 