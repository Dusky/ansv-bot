function loadStatistics() {
  // Only log in development environment
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  
  const statsContainer = document.getElementById('statsContainer');
  const loadingIndicator = document.getElementById('loadingIndicator');
  const totalLinesElement = document.getElementById('totalLines');
  const totalCacheSizeElement = document.getElementById('totalCacheSize');
  const channelCountElement = document.getElementById('channelCount');
  const lastRebuildElement = document.getElementById('lastRebuild');
  
  // Show loading indicator
  if (loadingIndicator) loadingIndicator.style.display = 'block';
  
  // Let the global status checker handle this - it should already be running
  
  fetch('/get-stats')
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load stats data');
      }
      return response.json();
    })
    .then(data => {
      if (isDev) console.log("Stats data:", data);
      
      // Update summary metrics
      updateStatsSummary(data);
      
      // Handle table if it exists
      if (statsContainer) {
        // Clear existing rows
        statsContainer.innerHTML = '';
        
        // Calculate max line count for relative scaling (exclude General Model)
        let maxLineCount = 0;
        let totalLineCount = 0;
        
        data.forEach(channel => {
          if (channel.name !== 'General Model' && channel.name !== 'general_markov') {
            const lineCount = parseInt(channel.line_count || 0);
            totalLineCount += lineCount;
            maxLineCount = Math.max(maxLineCount, lineCount);
          }
        });
        
        if (isDev) console.log(`Max line count: ${maxLineCount}, Total line count: ${totalLineCount}`);
        
        // Add rows for each channel
        if (data.length === 0) {
          const emptyRow = document.createElement('tr');
          emptyRow.innerHTML = '<td colspan="7" class="text-center">No channel data available</td>';
          statsContainer.appendChild(emptyRow);
        } else {
          data.forEach(channel => {
            const lineCount = parseInt(channel.line_count || 0);
            
            // Calculate the baseline progress (0-100 messages, minimum 5% for visibility)
            const baselineProgress = Math.min(100, Math.max(5, lineCount / 100));
            
            // Calculate the relative progress based on total messages
            // We'll use this for models with >100 messages
            const relativeProgress = totalLineCount > 0 ? (lineCount / totalLineCount) * 100 : 0;
            
            const row = document.createElement('tr');
            
            // Create the layered progress bar HTML
            let progressBarHtml = '';
            
            if (channel.name === 'General Model' || channel.name === 'general_markov') {
              // For General Model, we show a different style progress bar
              progressBarHtml = `
                <div class="progress" style="height: 8px;">
                  <div class="progress-bar bg-info" style="width: 100%"></div>
                </div>
                <small class="text-muted">Combined model</small>
              `;
            } else {
              // For regular channels, show the two-layer progress bar
              progressBarHtml = `
                <div class="progress mb-1" style="height: 6px;" data-bs-toggle="tooltip" title="${lineCount} messages (threshold: 100)">
                  <div class="progress-bar bg-success" style="width: ${baselineProgress}%"></div>
                </div>
                <div class="progress" style="height: 4px;" data-bs-toggle="tooltip" title="${(relativeProgress).toFixed(1)}% of all messages">
                  <div class="progress-bar bg-info" style="width: ${relativeProgress}%"></div>
                </div>
                <small class="text-muted" style="font-size: 0.75rem;">${lineCount > 100 ? 
                  `${(relativeProgress).toFixed(1)}% of total` : 
                  `${Math.floor(baselineProgress)}% of min`}</small>
                <div class="mt-1">
                  <span class="badge ${lineCount < 50 ? 'bg-warning' : lineCount > 1000 ? 'bg-success' : 'bg-info'}" style="font-size: 0.7rem;">
                    ${lineCount < 50 ? 'Needs training' : lineCount > 1000 ? 'Well-trained' : 'Adequate'}
                  </span>
                </div>
              `;
            }
            
            // Check if General Model for special styling
            const isGeneralModel = (channel.name === 'General Model' || channel.name === 'general_markov');
            
            // Define content rows with styling
            const channelCell = `<td class="${isGeneralModel ? 'fw-bold' : ''}">${channel.name}</td>`;
            const cacheFileCell = `<td>${channel.cache_file || 'N/A'}</td>`;
            const logFileCell = `<td>${channel.log_file || 'N/A'}</td>`;
            const cacheSizeCell = `<td>${channel.cache_size || '0 KB'}</td>`;
            const lineCountCell = `<td>${lineCount || '0'}</td>`;
            const progressCell = `<td>${progressBarHtml}</td>`;
            
            // Create action buttons with conditional initial state
            const actionButtons = `
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-warning btn-sm rebuild-btn" 
                          data-channel="${channel.name}" 
                          data-action="rebuild"
                          title="Rebuild model">
                    <i class="fas fa-tools me-1"></i>Rebuild
                  </button>
                </div>
              </td>
            `;
            
            // Combine all cells
            row.innerHTML = channelCell + cacheFileCell + logFileCell + cacheSizeCell + 
                          lineCountCell + progressCell + actionButtons;
            statsContainer.appendChild(row);
          });
          
          // Initialize tooltips after adding rows
          try {
            const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
            if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
              tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
            }
          } catch (e) {
            console.warn('Could not initialize tooltips:', e);
          }
        }
      }
      
      // Load build times
      try {
        loadBuildTimes();
      } catch (e) {
        if (isDev) console.error('Error loading build times:', e);
      }
    })
    .catch(error => {
      if (isDev) console.error('Error loading stats:', error);
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
  const healthStatusElement = document.getElementById('healthStatus');
  const lastUpdateTimeElement = document.getElementById('lastUpdateTime');
  const timeSinceRebuildElement = document.getElementById('timeSinceRebuild');
  const modelStatusInfoElement = document.getElementById('modelStatusInfo');
  const modelStatusMessageElement = document.getElementById('modelStatusMessage');
  const totalCountElement = document.getElementById('totalCount');
  const filteredCountElement = document.getElementById('filteredCount');
  
  // Progress bar elements
  const cacheSizeProgressElement = document.getElementById('cacheSizeProgress');
  const messagesProgressElement = document.getElementById('messagesProgress');
  const channelsProgressElement = document.getElementById('channelsProgress');
  
  // If hero elements don't exist, skip summary
  if (!totalLinesElement && !totalCacheSizeElement && !channelCountElement) {
    return;
  }
  
  let totalLines = 0;
  let totalCacheSize = 0;
  
  // Count all real channels - excluding only the general model
  const channelModels = data.filter(channel => 
    channel.name !== 'general_markov' && 
    channel.name !== 'General Model'
  );
  
  // Set the count
  const channelCount = channelModels.length;
  
  // Update filtered/total counters
  if (totalCountElement) {
    totalCountElement.textContent = channelCount;
  }
  if (filteredCountElement) {
    filteredCountElement.textContent = channelCount; // Will be updated by filter function
  }
  
  // Calculate model health metrics
  let smallModelsCount = 0;
  let healthyModelsCount = 0;
  let largeModelsCount = 0;
  
  data.forEach(channel => {
    if (channel.line_count) {
      const lineCount = parseInt(channel.line_count);
      totalLines += lineCount;
      
      // Skip general model for health metrics
      if (channel.name !== 'general_markov' && channel.name !== 'General Model') {
        if (lineCount < 50) {
          smallModelsCount++;
        } else if (lineCount > 1000) {
          largeModelsCount++;
        } else {
          healthyModelsCount++;
        }
      }
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
  
  // Set progress bars (with reasonable max values)
  if (messagesProgressElement) {
    // 50,000 messages is considered "full" for visualization purposes
    const messagesPercent = Math.min(100, (totalLines / 50000) * 100);
    messagesProgressElement.style.width = `${messagesPercent}%`;
  }
  
  if (channelsProgressElement) {
    // 10 channels is considered "full" for visualization
    const channelsPercent = Math.min(100, (channelCount / 10) * 100);
    channelsProgressElement.style.width = `${channelsPercent}%`;
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
    
    if (cacheSizeProgressElement) {
      // 10MB is considered "full" for visualization
      const cacheSizePercent = Math.min(100, (totalCacheSize / (10 * 1024)) * 100);
      cacheSizeProgressElement.style.width = `${cacheSizePercent}%`;
    }
  }
  
  if (channelCountElement) {
    channelCountElement.textContent = channelCount;
  }
  
  if (lastRebuildElement) {
    const today = new Date().toLocaleDateString();
    lastRebuildElement.textContent = today;
    
    // Update time since rebuild
    if (timeSinceRebuildElement) {
      timeSinceRebuildElement.textContent = "Today";
    }
  }
  
  // Update health status
  if (healthStatusElement) {
    let healthClass = "bg-success";
    let healthText = "Healthy";
    
    if (smallModelsCount > healthyModelsCount) {
      healthClass = "bg-warning";
      healthText = "Needs Training";
    } else if (channelCount === 0) {
      healthClass = "bg-danger";
      healthText = "No Models";
    } else if (Date.now() - new Date() > 30 * 24 * 60 * 60 * 1000) {
      // If last rebuild was over 30 days ago
      healthClass = "bg-warning";
      healthText = "Needs Rebuild";
    }
    
    healthStatusElement.className = `badge ${healthClass} me-2`;
    healthStatusElement.textContent = healthText;
  }
  
  // Update last update time
  if (lastUpdateTimeElement) {
    lastUpdateTimeElement.textContent = new Date().toLocaleTimeString();
  }
  
  // Show model status info if needed
  if (modelStatusInfoElement && modelStatusMessageElement) {
    if (smallModelsCount > 0 && channelCount > 0) {
      modelStatusInfoElement.classList.remove('d-none');
      modelStatusMessageElement.innerHTML = `
        <strong>${smallModelsCount}</strong> ${smallModelsCount === 1 ? 'model needs' : 'models need'} more training data
        ${largeModelsCount > 0 ? ` • <strong>${largeModelsCount}</strong> well-trained ${largeModelsCount === 1 ? 'model' : 'models'}` : ''}
      `;
    } else if (channelCount === 0) {
      modelStatusInfoElement.classList.remove('d-none');
      modelStatusMessageElement.innerHTML = 'No channel models found. Add channels to start training models.';
    } else {
      modelStatusInfoElement.classList.add('d-none');
    }
  }
}

// DIRECT IMPLEMENTATION: Instead of delegating, we'll use a direct implementation
// We keep this function signature for backward compatibility with existing onclick handlers
function rebuildCacheForChannel(channel) {
  console.log(`Stats.js: Directly rebuilding cache for channel: ${channel}`);
  
  // Use the globally defined rebuildCacheDirectly function if available
  if (typeof window.rebuildCacheDirectly === 'function') {
    window.rebuildCacheDirectly(channel);
    return;
  }
  
  // If not available, implement directly here as a fallback
  const button = document.querySelector(`button[data-channel="${channel}"][data-action="rebuild"]`);
  const originalText = button ? button.textContent : "Rebuild";
  
  if (button) {
    button.textContent = "Building...";
    button.disabled = true;
  }
  
  // Call the server API directly for reliability
  fetch(`/rebuild-cache/${channel}`, {
    method: 'POST'
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showToast(`Model for ${channel} rebuilt successfully`, 'success');
      // Refresh stats
      if (typeof loadStatistics === 'function') {
        loadStatistics();
      }
    } else {
      showToast(`Failed to rebuild model: ${data.message}`, 'error');
    }
  })
  .catch(error => {
    console.error('Error rebuilding cache:', error);
    showToast(`Error rebuilding model: ${error.message}`, 'error');
  })
  .finally(() => {
    // Restore button state
    if (button) {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
}

// Function signature remains for compatibility but ensures proper delegation
function sendMarkovMessage(channel) {
  console.log("stats.js: Delegating to implementation in markov.js");
  
  // First check if markov module is available
  if (typeof window.markovModule !== 'undefined' && window.markovModule.sendMarkovMessage) {
    window.markovModule.sendMarkovMessage(channel);
    return;
  }
  
  // If markov module is not available yet, we'll retry after a short delay
  // This helps with race conditions when scripts are still loading
  console.warn("Markov module not immediately available, retrying after delay...");
  setTimeout(() => {
    if (typeof window.markovModule !== 'undefined' && window.markovModule.sendMarkovMessage) {
      window.markovModule.sendMarkovMessage(channel);
    } else {
      // If still not available after delay, show a more helpful error
      console.error("Markov module not available - check script loading order");
      showToast("Error: Message generation module not properly loaded. Please refresh the page.", "error");
    }
  }, 500);
}

// Remove local implementation - we'll use the global functions from event_listener.js
// NOTE: This relies on event_listener.js being loaded before stats.js in every page

// Make loadStatistics and loadBuildTimes available globally
window.loadStatistics = loadStatistics;
window.loadBuildTimes = loadBuildTimes;

// Function to load and display cache build performance data
function loadBuildTimes() {
  // Only log in development environment
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isDev) console.log("Loading build times data...");
  
  const buildTimesContainer = document.getElementById('buildTimesContainer');
  if (!buildTimesContainer) {
    if (isDev) console.warn("buildTimesContainer element not found in the DOM");
    return;
  }
  
  // First try the preferred API endpoint
  fetch('/api/cache-build-performance')
    .then(response => {
      if (!response.ok) {
        // If the preferred endpoint fails, try fallback
        if (isDev) console.log("Preferred endpoint failed, trying fallback...");
        return fetch('/api/build-times');
      }
      return response;
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load build times data');
      }
      return response.json();
    })
    .then(data => {
      if (isDev) console.log("Received build times data:", data);
      if (!data || data.length === 0) {
        buildTimesContainer.innerHTML = '<tr><td colspan="4" class="text-center py-3">No build data available</td></tr>';
        return;
      }
      
      buildTimesContainer.innerHTML = '';
      
      // Sort by timestamp descending to show newest first
      data.sort((a, b) => b.timestamp - a.timestamp);
      
      // Process build times data - take only the 10 most recent
      const recentData = data.slice(0, 10);
      recentData.forEach(item => {
        const row = document.createElement('tr');
        const timestamp = item.timestamp ? new Date(item.timestamp * 1000).toLocaleString() : 'Unknown';
        const status = item.success ? 
          '<span class="badge bg-success">Success</span>' : 
          '<span class="badge bg-danger">Failed</span>';
        
        row.innerHTML = `
          <td>${item.channel || 'Unknown'}</td>
          <td>${timestamp}</td>
          <td>${item.duration ? (item.duration.toFixed(2) + 's') : 'N/A'}</td>
          <td>${status}</td>
        `;
        buildTimesContainer.appendChild(row);
      });
    })
    .catch(error => {
      if (isDev) console.error('Error loading build times:', error);
      buildTimesContainer.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error loading build data</td></tr>';
    });
}

// Load stats when the page loads
document.addEventListener('DOMContentLoaded', function() {
  // Only log in development environment
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isDev) console.log("Stats.js loaded and initializing...");
  
  // Execute after a small delay to ensure all scripts are loaded
  setTimeout(function() {
    // Initialize stats loading
    if (typeof window.loadStatistics === 'function') {
      if (isDev) console.log("Loading statistics from stats.js...");
      window.loadStatistics();
      
      // Load build times data after statistics are loaded
      if (isDev) console.log("Loading build times data...");
      loadBuildTimes();
    } else {
      console.error("loadStatistics is not available as a function");
    }
    
    // Setup refresh button event listener
    const refreshStatsBtn = document.getElementById('refreshStatsBtn');
    if (refreshStatsBtn) {
      refreshStatsBtn.addEventListener('click', function() {
        if (typeof window.loadStatistics === 'function') {
          window.loadStatistics();
          loadBuildTimes(); // Also refresh build times
        }
      });
    }
    
    // Update stats when bot status changes
    window.addEventListener('botstatus', function(e) {
      console.log("Received bot status update event:", e.detail);
      // Refresh stats when bot status changes - specifically when it starts running
      if (e.detail.running && typeof window.loadStatistics === 'function') {
        window.loadStatistics();
      }
    });
    
    // Setup rebuild all button with direct implementation
    const rebuildAllBtn = document.getElementById('rebuildAllCachesBtn');
    if (rebuildAllBtn) {
      // Remove any existing event listeners
      rebuildAllBtn.replaceWith(rebuildAllBtn.cloneNode(true));
      
      // Get the fresh reference after replacement
      const freshBtn = document.getElementById('rebuildAllCachesBtn');
      
      // Add our own direct implementation
      freshBtn.addEventListener('click', function(event) {
        // Stop any other handlers
        event.preventDefault();
        event.stopPropagation();
        
        // Create confirmation locally to avoid conflicts
        const confirmRebuild = confirm('Are you sure you want to rebuild all brains? This may take a while.');
        if (!confirmRebuild) return;
        
        // Show feedback
        showToast('Rebuilding all brains...', 'info');
        
        // Disable button and show loading state
        this.disabled = true;
        const originalText = this.textContent;
        this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rebuilding...';
        
        // Make direct API call
        fetch('/rebuild-all-caches', {
          method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            showToast('Successfully started rebuilding all brains', 'success');
            // Refresh after a delay to allow rebuild to complete
            setTimeout(function() {
              if (typeof window.loadStatistics === 'function') {
                window.loadStatistics();
              }
            }, 5000);
          } else {
            showToast(`Failed to rebuild brains: ${data.message}`, 'error');
          }
        })
        .catch(error => {
          console.error('Error rebuilding all caches:', error);
          showToast('Error rebuilding brains', 'error');
        })
        .finally(() => {
          // Restore button state
          this.disabled = false;
          this.textContent = originalText;
        });
      });
      
      // Make rebuild function globally available
      window.rebuildAllCachesDirectly = function() {
        freshBtn.click();
      };
    }
  }, 500);  // 500ms delay to ensure DOM is ready and other scripts are loaded
  
  // Setup general model rebuild button with direct implementation
  const rebuildGeneralBtn = document.getElementById('rebuildGeneralCacheBtn');
  if (rebuildGeneralBtn) {
    // Remove any existing event listeners
    rebuildGeneralBtn.replaceWith(rebuildGeneralBtn.cloneNode(true));
    
    // Get the fresh reference after replacement
    const freshBtn = document.getElementById('rebuildGeneralCacheBtn');
    
    // Add our own direct implementation
    freshBtn.addEventListener('click', function(event) {
      // Stop any other handlers
      event.preventDefault();
      event.stopPropagation();
      
      // Create confirmation locally to avoid conflicts
      const confirmRebuild = confirm('Are you sure you want to rebuild the general brain?');
      if (!confirmRebuild) return;
      
      // Show feedback
      showToast('Rebuilding general brain...', 'info');
      
      // Disable button and show loading state
      this.disabled = true;
      const originalText = this.textContent;
      this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Rebuilding...';
      
      // Make direct API call
      fetch('/rebuild-general-cache', {
        method: 'POST'
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showToast('Successfully rebuilt general brain', 'success');
          // Refresh stats
          if (typeof window.loadStatistics === 'function') {
            window.loadStatistics();
          }
        } else {
          showToast(`Failed to rebuild general brain: ${data.message}`, 'error');
        }
      })
      .catch(error => {
        console.error('Error rebuilding general cache:', error);
        showToast('Error rebuilding general brain', 'error');
      })
      .finally(() => {
        // Restore button state
        this.disabled = false;
        this.textContent = originalText;
      });
    });
    
    // Make function globally available
    window.rebuildGeneralCacheDirectly = function() {
      freshBtn.click();
    };
  }
}); 