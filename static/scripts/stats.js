// Helper function to format bytes into a human-readable string
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

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
  
  fetch('/get-stats')
    .then(response => {
      if (!response.ok) {
        // Throw a more detailed error to help diagnose
        throw new Error(`Failed to load stats data: ${response.status} ${response.statusText}`);
      }
      return response.json();
    })
    .then(data => {
      if (isDev) console.log("Stats data:", data);
      
      // Update summary metrics
      updateStatsSummary(data);
      
      // Handle table if it exists
      if (statsContainer) {
        statsContainer.innerHTML = ''; // Clear existing rows
        
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
        
        if (data.length === 0) {
          const emptyRow = document.createElement('tr');
          emptyRow.innerHTML = '<td colspan="7" class="text-center">No channel data available</td>';
          statsContainer.appendChild(emptyRow);
        } else {
          data.forEach(channel => {
            const lineCount = parseInt(channel.line_count || 0);
            const baselineProgress = Math.min(100, Math.max(5, lineCount / 100));
            const relativeProgress = totalLineCount > 0 ? (lineCount / totalLineCount) * 100 : 0;
            const row = document.createElement('tr');
            const isGeneralModel = (channel.name === 'General Model' || channel.name === 'general_markov');
            
            let progressBarHtml = '';
            if (isGeneralModel) {
              progressBarHtml = `
                <div class="progress" style="height: 8px;">
                  <div class="progress-bar bg-info" style="width: 100%"></div>
                </div>
                <small class="text-muted">Combined model</small>
              `;
            } else {
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
            
            const channelCell = `<td class="${isGeneralModel ? 'fw-bold' : ''}">${channel.name}</td>`;
            
            let cacheFileCellContent = 'N/A';
            if (channel.cache_file) {
                cacheFileCellContent = `<a href="/view-file/cache/${encodeURIComponent(channel.cache_file)}" target="_blank">${channel.cache_file}</a>`;
            }
            const cacheFileCell = `<td>${cacheFileCellContent}</td>`;

            let logFileCellContent = 'N/A';
            if (channel.log_file) {
                logFileCellContent = `<a href="/view-file/logs/${encodeURIComponent(channel.log_file)}" target="_blank">${channel.log_file}</a>`;
            }
            const logFileCell = `<td>${logFileCellContent}</td>`;
            
            const cacheSizeCell = `<td>${channel.cache_size_str || '0 B'}</td>`; // Use cache_size_str
            const lineCountCell = `<td>${lineCount || '0'}</td>`;
            const progressCell = `<td>${progressBarHtml}</td>`;
            
            const actionButtons = `
              <td>
                <div class="d-flex gap-1">
                  <button class="btn btn-warning btn-sm rebuild-btn" 
                          data-channel="${channel.name}" 
                          data-action="rebuild"
                          title="Rebuild model for ${channel.name}">
                    <i class="fas fa-tools me-1"></i>Rebuild
                  </button>
                  ${isGeneralModel ? '' : `
                  <button class="btn btn-success btn-sm send-message-stats-btn"
                          data-channel="${channel.name}"
                          data-action="send"
                          title="Generate and send a message to ${channel.name}">
                    <i class="fas fa-comment-dots me-1"></i>Send
                  </button>
                  `}
                </div>
              </td>
            `;
            
            row.innerHTML = channelCell + cacheFileCell + logFileCell + cacheSizeCell + 
                          lineCountCell + progressCell + actionButtons;
            statsContainer.appendChild(row);
          });
          
          // Initialize tooltips and attach event listeners after adding rows
          initializeDynamicElements();
        }
      }
      
      try {
        loadBuildTimes();
      } catch (e) {
        if (isDev) console.error('Error loading build times:', e);
      }
    })
    .catch(error => {
      if (isDev) console.error('Error loading stats:', error.message); // Log the more detailed error message
      if (statsContainer) {
        // Display the more detailed error message in the table
        statsContainer.innerHTML = `<tr><td colspan="7" class="text-center text-danger">${error.message}</td></tr>`;
      }
    })
    .finally(() => {
      if (loadingIndicator) loadingIndicator.style.display = 'none';
    });
}

function initializeDynamicElements() {
    // Initialize tooltips
    try {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
        }
    } catch (e) {
        console.warn('Could not initialize tooltips:', e);
    }

    // Attach event listeners for rebuild buttons
    document.querySelectorAll('button.rebuild-btn[data-action="rebuild"]').forEach(button => {
        // Remove existing listener before adding a new one to prevent duplicates
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        
        newButton.addEventListener('click', function() {
            const channelName = this.getAttribute('data-channel');
            if (window.markovModule && typeof window.markovModule.rebuildChannelModel === 'function') {
                window.markovModule.rebuildChannelModel(channelName);
            } else if (typeof window.rebuildCacheForChannelGlobal === 'function') { // Fallback
                window.rebuildCacheForChannelGlobal(channelName);
            } else {
                console.error('Rebuild function not found for channel:', channelName);
                safeShowToast('Error: Rebuild functionality not available.', 'error');
            }
        });
    });

    // Attach event listeners for send message buttons
    document.querySelectorAll('button.send-message-stats-btn[data-action="send"]').forEach(button => {
        // Remove existing listener
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);

        newButton.addEventListener('click', function() {
            const channelName = this.getAttribute('data-channel');
            if (window.markovModule && typeof window.markovModule.sendMarkovMessage === 'function') {
                window.markovModule.sendMarkovMessage(channelName, this); // Pass button for UI updates
            } else {
                console.error('Send message function not found for channel:', channelName);
                safeShowToast('Error: Send message functionality not available.', 'error');
            }
        });
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
  let totalCacheSizeBytes = 0; // Use this for summing raw bytes
  
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
    
    // Sum raw cache_size_bytes
    if (typeof channel.cache_size_bytes === 'number') {
        totalCacheSizeBytes += channel.cache_size_bytes;
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
  
  // Format and display total cache size using the new helper
  if (totalCacheSizeElement) {
    totalCacheSizeElement.textContent = formatBytes(totalCacheSizeBytes);
    
    if (cacheSizeProgressElement) {
      // 10MB (10 * 1024 * 1024 bytes) is considered "full" for visualization
      const maxBytesForProgress = 10 * 1024 * 1024; 
      const cacheSizePercent = Math.min(100, (totalCacheSizeBytes / maxBytesForProgress) * 100);
      cacheSizeProgressElement.style.width = `${cacheSizePercent}%`;
    }
  }
  
  if (channelCountElement) {
    channelCountElement.textContent = channelCount;
  }
  
  if (lastRebuildElement) {
    // This will be updated by loadBuildTimes if a more specific date is available
    lastRebuildElement.textContent = "Recent"; 
    if (timeSinceRebuildElement) {
      timeSinceRebuildElement.textContent = "Just now";
    }
  }
  
  // Update health status
  if (healthStatusElement) {
    let healthClass = "bg-success";
    let healthText = "Healthy";
    
    if (smallModelsCount > healthyModelsCount && channelCount > 0) { // only if there are channels
      healthClass = "bg-warning";
      healthText = "Needs Training";
    } else if (channelCount === 0) {
      healthClass = "bg-danger";
      healthText = "No Models";
    }
    // Note: Stale rebuild check will be handled by loadBuildTimes
    
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

// Make loadStatistics and loadBuildTimes available globally
window.loadStatistics = loadStatistics;
window.loadBuildTimes = loadBuildTimes;

// Function to load and display cache build performance data
function loadBuildTimes() {
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isDev) console.log("Loading build times data...");
  
  const buildTimesContainer = document.getElementById('buildTimesContainer');
  const lastRebuildElement = document.getElementById('lastRebuild'); // For summary
  const timeSinceRebuildElement = document.getElementById('timeSinceRebuild'); // For summary
  const healthStatusElement = document.getElementById('healthStatus'); // For summary health update

  if (!buildTimesContainer && !lastRebuildElement) {
    if (isDev) console.warn("Build times UI elements not found in the DOM");
    return;
  }
  
  fetch('/api/cache-build-performance')
    .then(response => {
      if (!response.ok) {
        if (isDev) console.log("Preferred build times endpoint failed, trying fallback...");
        return fetch('/api/build-times'); // Fallback
      }
      return response;
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load build times data from all endpoints');
      }
      return response.json();
    })
    .then(data => {
      if (isDev) console.log("Received build times data:", data);
      if (!data || data.length === 0) {
        if(buildTimesContainer) buildTimesContainer.innerHTML = '<tr><td colspan="4" class="text-center py-3">No build data available</td></tr>';
        if(lastRebuildElement) lastRebuildElement.textContent = "Never";
        if(timeSinceRebuildElement) timeSinceRebuildElement.textContent = "N/A";
        return;
      }
      
      // Sort by timestamp descending to show newest first
      data.sort((a, b) => b.timestamp - a.timestamp);
      
      if (buildTimesContainer) {
        buildTimesContainer.innerHTML = ''; // Clear existing
        const recentData = data.slice(0, 10); // Show 10 most recent
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
      }

      // Update summary last rebuild time
      const mostRecentSuccessfulBuild = data.find(item => item.success);
      if (mostRecentSuccessfulBuild && mostRecentSuccessfulBuild.timestamp) {
          const lastBuildDate = new Date(mostRecentSuccessfulBuild.timestamp * 1000);
          if (lastRebuildElement) lastRebuildElement.textContent = lastBuildDate.toLocaleDateString();
          
          if (timeSinceRebuildElement) {
              const now = new Date();
              const diffMs = now - lastBuildDate;
              const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
              if (diffDays === 0) timeSinceRebuildElement.textContent = "Today";
              else if (diffDays === 1) timeSinceRebuildElement.textContent = "Yesterday";
              else timeSinceRebuildElement.textContent = `${diffDays} days ago`;

              // Update health status if rebuild is stale
              if (diffDays > 30 && healthStatusElement) {
                  if (!healthStatusElement.classList.contains('bg-danger')) { // Don't override more critical errors
                    healthStatusElement.className = 'badge bg-warning me-2';
                    healthStatusElement.textContent = "Needs Rebuild";
                  }
              }
          }
      } else {
          if (lastRebuildElement) lastRebuildElement.textContent = "Never";
          if (timeSinceRebuildElement) timeSinceRebuildElement.textContent = "N/A";
      }

    })
    .catch(error => {
      if (isDev) console.error('Error loading build times:', error);
      if (buildTimesContainer) buildTimesContainer.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error loading build data</td></tr>';
      if (lastRebuildElement) lastRebuildElement.textContent = "Error";
      if (timeSinceRebuildElement) timeSinceRebuildElement.textContent = "Error";
    });
}

// Helper function to safely show toast notifications
function safeShowToast(message, type = 'info') {
  try {
    if (window.notificationSystem && typeof window.notificationSystem.showToast === 'function') {
      window.notificationSystem.showToast(message, type);
    } else if (typeof window.showToast === 'function') {
      window.showToast(message, type);
    } else {
      console.log(`Toast (${type}): ${message}`);
      if (type === 'error') {
        alert(message);
      }
    }
  } catch (e) {
    console.error("Error showing toast:", e);
  }
}

// Load stats when the page loads
document.addEventListener('DOMContentLoaded', function() {
  // Check if we are on the stats page before doing anything
  if (!document.getElementById('statsContainer')) { // 'statsContainer' is unique to stats.html
    console.log("Not on stats page, stats.js will not initialize its main functions.");
    return; 
  }

  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isDev) console.log("Stats.js loaded and initializing on stats page...");
  
  // Initialize search and sort functionality for the channel table
  initSearch(); // Call the function to set up search/sort

  setTimeout(function() {
    if (typeof window.loadStatistics === 'function') {
      if (isDev) console.log("Loading statistics from stats.js...");
      window.loadStatistics(); // This will also call loadBuildTimes
    } else {
      console.error("loadStatistics is not available as a function");
    }
    
    const refreshStatsBtn = document.getElementById('refreshStatsBtn');
    if (refreshStatsBtn) {
      refreshStatsBtn.addEventListener('click', function() {
        if (typeof window.loadStatistics === 'function') {
          window.loadStatistics(); // This refreshes both stats and build times
        }
      });
    }
    
    window.addEventListener('botstatus', function(e) {
      if (isDev) console.log("Received bot status update event:", e.detail);
      if (e.detail.running && typeof window.loadStatistics === 'function') {
        window.loadStatistics();
      }
    });
    
    // Global rebuild buttons are now handled in markov.js
    // Ensure they are initialized if markov.js didn't do it (e.g. if stats.js loads first)
    const rebuildAllBtn = document.getElementById('rebuildAllCachesBtn');
    if (rebuildAllBtn && typeof window.rebuildAllCaches === 'function') {
        if (!rebuildAllBtn.getAttribute('listener-attached')) {
            rebuildAllBtn.addEventListener('click', window.rebuildAllCaches);
            rebuildAllBtn.setAttribute('listener-attached', 'true');
        }
    }
    const rebuildGeneralBtn = document.getElementById('rebuildGeneralCacheBtn');
    if (rebuildGeneralBtn && typeof window.rebuildGeneralCache === 'function') {
         if (!rebuildGeneralBtn.getAttribute('listener-attached')) {
            rebuildGeneralBtn.addEventListener('click', window.rebuildGeneralCache);
            rebuildGeneralBtn.setAttribute('listener-attached', 'true');
        }
    }

  }, 500);
});

// Function to initialize search and sort functionality for the channel table
function initSearch() {
    const searchInput = document.getElementById('channelSearch');
    const clearBtn = document.getElementById('clearSearchBtn');
    const sortSelector = document.getElementById('sortSelector');
    
    if (!searchInput || !clearBtn) {
        // console.warn("Stats page search or clear button not found.");
        return;
    }
    
    searchInput.addEventListener('input', function() {
        filterChannels(this.value.toLowerCase());
    });
    
    clearBtn.addEventListener('click', function() {
        searchInput.value = '';
        filterChannels('');
    });
    
    // Add sort selector functionality
    if (sortSelector) {
        sortSelector.addEventListener('change', function() {
            sortChannelTable(this.value);
        });
    } else {
        // console.warn("Stats page sort selector not found.");
    }
}

function filterChannels(query) {
    const rows = document.querySelectorAll('#statsContainer tr');
    const filteredCountElement = document.getElementById('filteredCount');
    let visibleCount = 0;
    
    rows.forEach(row => {
        // Ensure it's a data row (has td elements)
        const firstCell = row.querySelector('td:first-child');
        if (!firstCell) return; 

        const channelName = firstCell.textContent.toLowerCase();
        
        if (channelName.includes(query)) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update the filtered count
    if (filteredCountElement) {
        filteredCountElement.textContent = visibleCount;
    }
}

function sortChannelTable(sortBy) {
    const tbody = document.getElementById('statsContainer');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Skip if there are no rows or loading indicator is present
    if (rows.length === 0 || (rows.length === 1 && rows[0].querySelector('#loadingIndicator'))) return;
    
    // Sort the rows based on the selected criteria
    rows.sort((rowA, rowB) => {
        // Skip rows with no data cells (e.g., loading indicator row)
        if (!rowA.querySelector('td') || !rowB.querySelector('td')) return 0;
        
        // General model always at the top
        const channelA_Name = rowA.querySelector('td:first-child')?.textContent;
        const channelB_Name = rowB.querySelector('td:first-child')?.textContent;
        
        if (channelA_Name === 'General Model' || channelA_Name === 'general_markov') return -1;
        if (channelB_Name === 'General Model' || channelB_Name === 'general_markov') return 1;
        
        switch (sortBy) {
            case 'name':
                return (channelA_Name || '').localeCompare(channelB_Name || '');
                
            case 'size':
                // Extract cache size values
                const sizeA = extractNumericValue(rowA.querySelector('td:nth-child(4)')?.textContent);
                const sizeB = extractNumericValue(rowB.querySelector('td:nth-child(4)')?.textContent);
                return sizeB - sizeA; // Sort by size descending
                
            case 'messages':
                // Extract message count values
                const messagesA = parseInt(rowA.querySelector('td:nth-child(5)')?.textContent || '0', 10);
                const messagesB = parseInt(rowB.querySelector('td:nth-child(5)')?.textContent || '0', 10);
                return messagesB - messagesA; // Sort by message count descending
                
            case 'activity': // This is a proxy for model health/training status
                const activityA_raw = rowA.querySelector('td:nth-child(6) .badge')?.textContent.toLowerCase() || '';
                const activityB_raw = rowB.querySelector('td:nth-child(6) .badge')?.textContent.toLowerCase() || '';
                
                const score = (status) => {
                    if (status.includes('well-trained')) return 3;
                    if (status.includes('adequate')) return 2;
                    if (status.includes('needs training')) return 1;
                    return 0;
                };
                return score(activityB_raw) - score(activityA_raw); // Sort by activity descending
                
            default:
                return 0;
        }
    });
    
    // Reappend the sorted rows
    rows.forEach(row => tbody.appendChild(row));
}

// Helper function to extract numeric value from formatted strings like "1.23 MB"
function extractNumericValue(text) {
    if (!text) return 0;
    
    // Extract the number portion
    const matches = text.match(/^([\d.]+)/);
    if (!matches || !matches[1]) return 0;
    
    const value = parseFloat(matches[1]);
    const unit = text.trim().split(' ')[1];
    
    // Convert to a common unit (KB) for comparison
    switch (unit) {
        case 'B': return value / 1024;
        case 'KB': return value;
        case 'MB': return value * 1024;
        case 'GB': return value * 1024 * 1024;
        default: return value; // Assume KB if unit is unknown or missing
    }
}
