document.addEventListener('DOMContentLoaded', function() {
    const logContainer = document.getElementById('logContainer');
    const logLoadingSpinner = document.getElementById('logLoadingSpinner');
    const noLogDataMessage = document.getElementById('noLogData');
    
    const channelFilter = document.getElementById('channelFilter');
    const refreshLogsBtn = document.getElementById('refreshLogsBtn');
    
    const prevLogPageBtn = document.getElementById('prevLogPageBtn');
    const nextLogPageBtn = document.getElementById('nextLogPageBtn');
    const currentLogPageSpan = document.getElementById('currentLogPage');
    const totalLogPagesSpan = document.getElementById('totalLogPages');
    const prevLogPageContainer = document.getElementById('prevLogPageContainer');
    const nextLogPageContainer = document.getElementById('nextLogPageContainer');

    let currentPage = 1;
    const perPage = 50; // Number of log entries per page

    // Helper function to generate a color from a string (e.g., username, channel)
    function stringToHslColor(str, s = 70, l = 65, a = 1) {
        if (!str) return `hsla(0, 0%, 70%, ${a})`; // Default grey for empty strings
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
            hash = hash & hash; // Convert to 32bit integer
        }
        const hue = hash % 360;
        // Adjust lightness for dark themes to ensure visibility
        const isDarkTheme = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        const effectiveLightness = isDarkTheme ? Math.min(l + 15, 85) : l; // Brighter on dark themes
        return `hsla(${hue}, ${s}%, ${effectiveLightness}%, ${a})`;
    }

    function fetchChannelsForFilter() {
        if (!channelFilter) return;

        fetch('/api/channels')
            .then(response => response.json())
            .then(data => {
                // Clear existing options except "All Channels"
                while (channelFilter.options.length > 1) {
                    channelFilter.remove(1);
                }
                if (data && Array.isArray(data)) {
                    data.forEach(channel => {
                        const option = document.createElement('option');
                        option.value = channel.name;
                        option.textContent = channel.name;
                        channelFilter.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Error fetching channels for filter:', error);
                if (window.notificationSystem && window.notificationSystem.showToast) {
                    window.notificationSystem.showToast('Error loading channel filter.', 'error');
                }
            });
    }

    function loadLogs(page = 1, channel = '') {
        if (!logContainer || !logLoadingSpinner || !noLogDataMessage) {
            console.warn('Log display elements not found, skipping log load.');
            return;
        }

        logLoadingSpinner.style.display = 'block';
        logContainer.innerHTML = ''; // Clear previous logs
        noLogDataMessage.style.display = 'none';

        const params = new URLSearchParams({
            page: page,
            per_page: perPage
        });
        if (channel) {
            params.append('channel', channel);
        }

        fetch(`/api/chat-logs?${params.toString()}`, { cache: 'no-store' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                logLoadingSpinner.style.display = 'none';
                if (data.error || !data.logs || data.logs.length === 0) {
                    noLogDataMessage.style.display = 'block';
                    if (data.error) {
                        console.error('Error fetching logs:', data.error);
                        noLogDataMessage.innerHTML = `<div class="empty-state-content"><i class="fas fa-exclamation-triangle empty-state-icon text-danger"></i><h4>Error Loading Logs</h4><p class="text-muted">${data.error}</p></div>`;
                    } else {
                         noLogDataMessage.innerHTML = '<div class="empty-state-content"><i class="fas fa-comment-slash empty-state-icon"></i><h4>No Log Messages</h4><p class="text-muted">There are no chat messages matching your criteria.</p></div>';
                    }
                    updateLogPagination(data.page || 0, data.total_pages || 0);
                    return;
                }

                displayLogs(data.logs);
                updateLogPagination(data.page, data.total_pages);
                currentPage = data.page;
            })
            .catch(error => {
                console.error('Error loading logs:', error);
                logLoadingSpinner.style.display = 'none';
                noLogDataMessage.style.display = 'block';
                noLogDataMessage.innerHTML = `<div class="empty-state-content"><i class="fas fa-exclamation-triangle empty-state-icon text-danger"></i><h4>Error Loading Logs</h4><p class="text-muted">${error.message}</p></div>`;
                updateLogPagination(0, 0);
            });
    }

    function displayLogs(logs) {
        if (!logContainer) return;
        logContainer.innerHTML = ''; // Clear previous logs or loading message

        logs.forEach(log => {
            const logEntryDiv = document.createElement('div');
            logEntryDiv.className = 'log-entry mb-1'; // Add some bottom margin

            const timestampSpan = document.createElement('span');
            timestampSpan.className = 'log-timestamp text-muted me-2';
            try {
                // More concise timestamp
                const date = new Date(log.timestamp);
                timestampSpan.textContent = `[${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}]`;
            } catch (e) {
                timestampSpan.textContent = `[${log.timestamp}]`; // Fallback
            }
            
            const channelSpan = document.createElement('span');
            channelSpan.className = 'log-channel fw-bold me-1';
            const channelName = log.channel || 'unknown';
            channelSpan.textContent = `#${channelName}:`;
            channelSpan.style.color = stringToHslColor(channelName, 70, 55);


            const userSpan = document.createElement('span');
            userSpan.className = 'log-user me-1';
            const userName = log.username || 'system';
            userSpan.textContent = `<${userName}>`;
            userSpan.style.color = stringToHslColor(userName, 60, 60);


            const messageSpan = document.createElement('span');
            messageSpan.className = 'log-message';
            // For messages, use the default text color of the log container for theme consistency
            // messageSpan.style.color = 'var(--bs-body-color)'; // Example, or let it inherit
            messageSpan.textContent = log.message;

            logEntryDiv.appendChild(timestampSpan);
            logEntryDiv.appendChild(channelSpan);
            logEntryDiv.appendChild(userSpan);
            logEntryDiv.appendChild(messageSpan);
            
            logContainer.appendChild(logEntryDiv);
        });
        logContainer.scrollTop = 0; // Scroll to top to see newest logs if prepending, or keep as is for appending.
    }

    function updateLogPagination(page, totalPages) {
        if (currentLogPageSpan) currentLogPageSpan.textContent = page;
        if (totalLogPagesSpan) totalLogPagesSpan.textContent = totalPages;

        if (prevLogPageContainer) prevLogPageContainer.classList.toggle('disabled', page <= 1);
        if (nextLogPageContainer) nextLogPageContainer.classList.toggle('disabled', page >= totalPages);
    }

    if (refreshLogsBtn) {
        refreshLogsBtn.addEventListener('click', () => {
            const selectedChannel = channelFilter ? channelFilter.value : '';
            loadLogs(currentPage, selectedChannel);
        });
    }

    if (channelFilter) {
        channelFilter.addEventListener('change', () => {
            currentPage = 1; // Reset to first page on filter change
            loadLogs(currentPage, channelFilter.value);
        });
    }

    if (prevLogPageBtn) {
        prevLogPageBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (currentPage > 1) {
                const selectedChannel = channelFilter ? channelFilter.value : '';
                loadLogs(currentPage - 1, selectedChannel);
            }
        });
    }

    if (nextLogPageBtn) {
        nextLogPageBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const currentTotalPages = parseInt(totalLogPagesSpan.textContent, 10);
            if (currentPage < currentTotalPages) {
                const selectedChannel = channelFilter ? channelFilter.value : '';
                loadLogs(currentPage + 1, selectedChannel);
            }
        });
    }

    // Initial load
    fetchChannelsForFilter();
    loadLogs(1, ''); // Load first page, all channels
});
