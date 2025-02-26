// Function to load stats data and update summary metrics
function loadStatistics() {
  const statsContainer = document.getElementById('statsContainer');
  const loadingIndicator = document.getElementById('loadingIndicator');
  const totalLinesElement = document.getElementById('totalLines');
  const totalCacheSizeElement = document.getElementById('totalCacheSize');
  const channelCountElement = document.getElementById('channelCount');
  const lastRebuildElement = document.getElementById('lastRebuild');
  
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
      
      // Update summary metrics
      updateStatsSummary(data);
      
      // Handle table if it exists
      if (statsContainer) {
        // Clear existing rows
        statsContainer.innerHTML = '';
        
        // Add rows for each channel
        if (data.length === 0) {
          const emptyRow = document.createElement('tr');
          emptyRow.innerHTML = '<td colspan="7" class="text-center">No channel data available</td>';
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
              <td><div class="progress" style="height: 6px;">
                    <div class="progress-bar bg-success" style="width: ${Math.min(100, Math.max(5, (channel.line_count || 0) / 100))}%"></div>
                  </div>
              </td>
              <td>
                <button class="btn btn-primary btn-sm me-1" data-channel="${channel.name}" onclick="sendMarkovMessage('${channel.name}')">
                  <i class="fas fa-comment-dots me-1"></i>Generate
                </button>
                <button class="btn btn-secondary btn-sm" data-channel="${channel.name}" data-action="rebuild" onclick="rebuildCacheForChannel('${channel.name}')">
                  <i class="fas fa-sync-alt me-1"></i>Rebuild
                </button>
              </td>
            `;
            statsContainer.appendChild(row);
          });
        }
      }
      
      // Load build times
      try {
        loadBuildTimes();
      } catch (e) {
        console.error('Error loading build times:', e);
      }
    })
    .catch(error => {
      console.error('Error loading stats:', error);
      if (statsContainer) {
        statsContainer.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load data.</td></tr>';
      }
    })
    .finally(() => {
      // Hide loading indicator
      if (loadingIndicator) loadingIndicator.style.display = 'none';
    });
}

// Update the summary statistics in hero section
function updateStatsSummary(data) {
  const totalLinesElement = document.getElementById('totalLines');
  const totalCacheSizeElement = document.getElementById('totalCacheSize');
  const channelCountElement = document.getElementById('channelCount');
  const lastRebuildElement = document.getElementById('lastRebuild');
  
  // If hero elements don't exist, skip summary
  if (!totalLinesElement && !totalCacheSizeElement && !channelCountElement) {
    return;
  }
  
  let totalLines = 0;
  let totalCacheSize = 0;
  
  // Debug logging
  console.log("Stats data for counting:", data.map(ch => ch.name));
  
  // Count all real channels - excluding only the general model
  const channelModels = data.filter(channel => 
    channel.name !== 'general_markov' && 
    channel.name !== 'General Model'
  );
  
  // Log the filtered channels
  console.log("Filtered channel models:", channelModels.map(ch => ch.name));
  
  // Set the count
  const channelCount = channelModels.length;
  
  data.forEach(channel => {
    if (channel.line_count) {
      totalLines += parseInt(channel.line_count);
    }
    
    // Extract numeric value from cache size string (e.g., "1.23 MB" -> 1.23)
    if (channel.cache_size) {
      const matches = channel.cache_size.match(/^([\d.]+)/);
      if (matches && matches[1]) {
        const size = parseFloat(matches[1]);
        const unit = channel.cache_size.split(' ')[1];
        
        // Convert to a common unit (KB) for summation
        let sizeInKB = 0;
        switch (unit) {
          case 'B': sizeInKB = size / 1024; break;
          case 'KB': sizeInKB = size; break;
          case 'MB': sizeInKB = size * 1024; break;
          case 'GB': sizeInKB = size * 1024 * 1024; break;
        }
        
        totalCacheSize += sizeInKB;
      }
    }
  });
  
  // Format and display statistics
  if (totalLinesElement) {
    totalLinesElement.textContent = totalLines.toLocaleString();
  }
  
  // Convert total cache size back to appropriate unit
  if (totalCacheSizeElement) {
    let formattedSize = '';
    if (totalCacheSize < 1024) {
      formattedSize = totalCacheSize.toFixed(2) + ' KB';
    } else if (totalCacheSize < 1024 * 1024) {
      formattedSize = (totalCacheSize / 1024).toFixed(2) + ' MB';
    } else {
      formattedSize = (totalCacheSize / (1024 * 1024)).toFixed(2) + ' GB';
    }
    
    totalCacheSizeElement.textContent = formattedSize;
  }
  
  if (channelCountElement) {
    console.log("Setting channel count to:", channelCount);
    console.log("Channel count element:", channelCountElement);
    channelCountElement.textContent = channelCount;
  }
  
  if (lastRebuildElement) {
    lastRebuildElement.textContent = new Date().toLocaleDateString();
  }
}

// Function to handle rebuild for a specific channel
function rebuildCacheForChannel(channel) {
  showConfirmation(
    'Rebuild Brain',
    `Are you sure you want to rebuild the brain for ${channel}?`,
    function() {
      showToast(`Rebuilding brain for ${channel}...`, 'info');
      
      fetch(`/rebuild-cache/${channel}`, {
        method: 'POST'
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showToast(`Successfully rebuilt brain for ${channel}`, 'success');
          // Refresh stats after rebuild
          loadStatistics();
        } else {
          showToast(`Failed to rebuild brain: ${data.message}`, 'error');
        }
      })
      .catch(error => {
        console.error('Error rebuilding cache:', error);
        showToast('Error rebuilding brain', 'error');
      });
    }
  );
}

// Function to send a Markov message for a channel
function sendMarkovMessage(channel) {
  fetch(`/send_markov_message/${channel}`, {
    method: 'POST'
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showToast(`Message sent to ${channel}: "${data.message}"`, 'success');
    } else {
      showToast(`Failed to send message: ${data.message || 'Unknown error'}`, 'error');
    }
  })
  .catch(error => {
    console.error('Error sending message:', error);
    showToast('Error sending message', 'error');
  });
}

// Load stats when the page loads
document.addEventListener('DOMContentLoaded', function() {
  // Initialize stats loading
  loadStatistics();
  
  // Setup refresh button event listener
  const refreshStatsBtn = document.getElementById('refreshStatsBtn');
  if (refreshStatsBtn) {
    refreshStatsBtn.addEventListener('click', loadStatistics);
  }
  
  // Setup rebuild all button
  const rebuildAllBtn = document.getElementById('rebuildAllCachesBtn');
  if (rebuildAllBtn) {
    rebuildAllBtn.addEventListener('click', function() {
      showConfirmation(
        'Rebuild All Brains',
        'Are you sure you want to rebuild all brains? This may take a while.',
        function() {
          showToast('Rebuilding all brains...', 'info');
          
          fetch('/rebuild-all-caches', {
            method: 'POST'
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              showToast('Successfully started rebuilding all brains', 'success');
              // Refresh after a delay to allow rebuild to complete
              setTimeout(loadStatistics, 5000);
            } else {
              showToast(`Failed to rebuild brains: ${data.message}`, 'error');
            }
          })
          .catch(error => {
            console.error('Error rebuilding all caches:', error);
            showToast('Error rebuilding brains', 'error');
          });
        }
      );
    });
  }
  
  // Setup general model rebuild button
  const rebuildGeneralBtn = document.getElementById('rebuildGeneralCacheBtn');
  if (rebuildGeneralBtn) {
    rebuildGeneralBtn.addEventListener('click', function() {
      showConfirmation(
        'Rebuild General Brain',
        'Are you sure you want to rebuild the general brain?',
        function() {
          showToast('Rebuilding general brain...', 'info');
          
          fetch('/rebuild-general-cache', {
            method: 'POST'
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              showToast('Successfully rebuilt general brain', 'success');
              loadStatistics();
            } else {
              showToast(`Failed to rebuild general brain: ${data.message}`, 'error');
            }
          })
          .catch(error => {
            console.error('Error rebuilding general cache:', error);
            showToast('Error rebuilding general brain', 'error');
          });
        }
      );
    });
  }
}); 