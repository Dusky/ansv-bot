/**
 * Health Monitoring Dashboard
 * Real-time health monitoring with SocketIO, Chart.js, and browser notifications
 */

class HealthMonitor {
    constructor() {
        this.socket = io();
        this.charts = {};
        this.notificationsEnabled = false;
        this.pollingInterval = null;
        this.connectionChart = null;
        this.errorChart = null;
        this.init();
    }

    init() {
        console.log('Initializing Health Monitor...');
        this.setupSocketListeners();
        this.loadInitialData();
        this.setupNotifications();
        this.startPolling();
        this.setupEventListeners();
    }

    setupSocketListeners() {
        // Connection state changes
        this.socket.on('connection_state_changed', (data) => {
            console.log('Connection state changed:', data);
            this.updateConnectionCard(data);
            this.showBrowserNotification('Connection Status', `Bot is ${data.state}`);
        });

        // Error logged
        this.socket.on('error_logged', (data) => {
            console.log('Error logged:', data);
            this.updateErrorCard(data);
            if (data.level === 'error' || data.level === 'twitchio_error') {
                this.showBrowserNotification('Error Detected', data.message);
            }
            // Add to recent errors table
            this.prependError(data);
        });

        // Health updates
        this.socket.on('health_update', (data) => {
            console.log('Health update:', data);
            this.updateAllCards(data);
        });

        // Task status changes
        this.socket.on('task_status_changed', (data) => {
            console.log('Task status changed:', data);
            this.updateTaskCard(data);
        });
    }

    async loadInitialData() {
        try {
            const response = await fetch('/api/admin/health');
            const data = await response.json();

            if (data.success) {
                this.updateDashboard(data);
            } else {
                this.showError('Failed to load health data: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to connect to health API');
        }
    }

    updateDashboard(data) {
        // Update all status cards
        this.updateConnectionCard(data.connection);
        this.updateErrorsCard(data.errors);
        this.updatePerformanceCard(data.performance);
        this.updateTasksCard(data.background_tasks);

        // Update charts
        this.updateConnectionChart(data.connection_history);
        this.updateErrorChart(data.errors);
        this.updateErrorsTable(data.errors.recent);

        // Update last message info
        this.updateLastMessage(data.last_message_sent);

        // Update uptime
        this.updateUptime(data.uptime_seconds);
    }

    updateConnectionCard(connectionData) {
        const card = document.getElementById('connectionCard');
        const statusEl = document.getElementById('connectionStatus');
        const detailEl = document.getElementById('connectionDetail');

        if (!card || !statusEl) return;

        const state = connectionData.state || 'unknown';
        const botRunning = connectionData.bot_running !== undefined ? connectionData.bot_running : false;

        // Update status text and styling
        let statusText = 'Unknown';
        let statusClass = 'status-unknown';

        if (!botRunning) {
            statusText = 'Bot Offline';
            statusClass = 'status-error';
        } else if (state === 'connected') {
            statusText = 'Connected';
            statusClass = 'status-success';
        } else if (state === 'reconnecting') {
            statusText = 'Reconnecting...';
            statusClass = 'status-warning';
        } else if (state === 'disconnected') {
            statusText = 'Disconnected';
            statusClass = 'status-error';
        }

        statusEl.textContent = statusText;
        statusEl.className = `status-value ${statusClass}`;

        // Update detail
        if (detailEl) {
            if (state === 'reconnecting' && connectionData.attempts) {
                detailEl.textContent = `Attempt ${connectionData.attempts}`;
            } else if (state === 'connected' && connectionData.last_heartbeat) {
                const timeSince = this.getTimeSince(connectionData.last_heartbeat);
                detailEl.textContent = `Last heartbeat: ${timeSince}`;
            } else {
                detailEl.textContent = '';
            }
        }

        // Update card styling
        card.className = `status-card ${statusClass}`;
    }

    updateErrorsCard(errorsData) {
        const card = document.getElementById('errorsCard');
        const statusEl = document.getElementById('errorsStatus');
        const detailEl = document.getElementById('errorsDetail');

        if (!statusEl) return;

        const errors1h = errorsData.last_hour || 0;
        const errors24h = errorsData.last_24_hours || 0;

        statusEl.textContent = errors1h;

        if (detailEl) {
            detailEl.textContent = `${errors24h} in last 24h`;
        }

        // Update card styling based on error count
        if (card) {
            if (errors1h === 0) {
                card.className = 'status-card status-success';
            } else if (errors1h < 5) {
                card.className = 'status-card status-warning';
            } else {
                card.className = 'status-card status-error';
            }
        }
    }

    updatePerformanceCard(performanceData) {
        const statusEl = document.getElementById('performanceStatus');
        const detailEl = document.getElementById('performanceDetail');

        if (!statusEl) return;

        if (performanceData && performanceData.cpu_percent !== undefined) {
            statusEl.textContent = `${performanceData.cpu_percent}%`;

            if (detailEl) {
                detailEl.textContent = `Memory: ${performanceData.memory_mb}MB (${performanceData.memory_percent}%)`;
            }

            // Update card styling based on CPU usage
            const card = document.getElementById('performanceCard');
            if (card) {
                if (performanceData.cpu_percent < 50) {
                    card.className = 'status-card status-success';
                } else if (performanceData.cpu_percent < 80) {
                    card.className = 'status-card status-warning';
                } else {
                    card.className = 'status-card status-error';
                }
            }
        } else {
            statusEl.textContent = 'N/A';
            if (detailEl) detailEl.textContent = 'Not available';
        }
    }

    updateTasksCard(tasksData) {
        const statusEl = document.getElementById('tasksStatus');
        const detailEl = document.getElementById('tasksDetail');

        if (!statusEl) return;

        const heartbeat = tasksData.heartbeat || 'unknown';
        const messageChecker = tasksData.message_request_checker || 'unknown';

        const allHealthy = heartbeat === 'healthy' && messageChecker === 'healthy';
        const anyUnhealthy = heartbeat === 'unhealthy' || messageChecker === 'unhealthy';

        if (allHealthy) {
            statusEl.textContent = 'All Healthy';
            statusEl.className = 'status-value status-success';
        } else if (anyUnhealthy) {
            statusEl.textContent = 'Issues Detected';
            statusEl.className = 'status-value status-error';
        } else {
            statusEl.textContent = 'Unknown';
            statusEl.className = 'status-value status-warning';
        }

        if (detailEl) {
            detailEl.textContent = `Heartbeat: ${heartbeat}, Checker: ${messageChecker}`;
        }
    }

    updateConnectionChart(historyData) {
        const ctx = document.getElementById('connectionChart');
        if (!ctx) return;

        // Prepare data for Chart.js
        const sortedHistory = (historyData || []).reverse(); // Oldest first
        const labels = sortedHistory.map(h => {
            const date = new Date(h.timestamp);
            return date.toLocaleTimeString();
        });

        const data = sortedHistory.map(h => {
            // Map event types to numeric values for visualization
            if (h.event_type === 'connected') return 1;
            if (h.event_type === 'reconnect_attempt') return 0.5;
            if (h.event_type === 'reconnect_success') return 1;
            if (h.event_type === 'reconnect_failed') return 0;
            if (h.event_type === 'disconnected') return 0;
            return 0.5;
        });

        if (this.connectionChart) {
            this.connectionChart.destroy();
        }

        this.connectionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Connection State',
                    data: data,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            callback: function(value) {
                                if (value === 1) return 'Connected';
                                if (value === 0.5) return 'Attempting';
                                if (value === 0) return 'Disconnected';
                                return '';
                            }
                        }
                    }
                }
            }
        });
    }

    updateErrorChart(errorsData) {
        const ctx = document.getElementById('errorChart');
        if (!ctx) return;

        // Simple bar chart showing error count
        if (this.errorChart) {
            this.errorChart.destroy();
        }

        this.errorChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Last Hour', 'Last 24 Hours'],
                datasets: [{
                    label: 'Errors',
                    data: [errorsData.last_hour || 0, errorsData.last_24_hours || 0],
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(255, 159, 64, 0.5)'
                    ],
                    borderColor: [
                        'rgb(255, 99, 132)',
                        'rgb(255, 159, 64)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    updateErrorsTable(recentErrors) {
        const tableEl = document.getElementById('errorsTable');
        if (!tableEl) return;

        if (!recentErrors || recentErrors.length === 0) {
            tableEl.innerHTML = '<p class="text-muted">No recent errors</p>';
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-sm"><thead><tr>';
        html += '<th>Time</th><th>Level</th><th>Message</th><th>Source</th>';
        html += '</tr></thead><tbody>';

        recentErrors.forEach(error => {
            const date = new Date(error.timestamp);
            const timeStr = date.toLocaleString();
            const levelClass = error.level === 'error' || error.level === 'twitchio_error' ? 'danger' : 'warning';

            html += `<tr>
                <td class="text-nowrap">${timeStr}</td>
                <td><span class="badge bg-${levelClass}">${error.level}</span></td>
                <td>${this.escapeHtml(error.message)}</td>
                <td>${error.source || 'unknown'}</td>
            </tr>`;
        });

        html += '</tbody></table></div>';
        tableEl.innerHTML = html;
    }

    prependError(errorData) {
        // Add new error to the top of the table
        const tableEl = document.getElementById('errorsTable');
        if (!tableEl) return;

        const table = tableEl.querySelector('table tbody');
        if (!table) {
            // Table doesn't exist yet, reload data
            this.loadInitialData();
            return;
        }

        const date = new Date(errorData.timestamp);
        const timeStr = date.toLocaleString();
        const levelClass = errorData.level === 'error' || errorData.level === 'twitchio_error' ? 'danger' : 'warning';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="text-nowrap">${timeStr}</td>
            <td><span class="badge bg-${levelClass}">${errorData.level}</span></td>
            <td>${this.escapeHtml(errorData.message)}</td>
            <td>${errorData.source || 'bot'}</td>
        `;

        table.insertBefore(row, table.firstChild);

        // Keep only last 10 rows
        while (table.children.length > 10) {
            table.removeChild(table.lastChild);
        }
    }

    updateLastMessage(messageData) {
        const el = document.getElementById('lastMessageInfo');
        if (!el) return;

        if (!messageData) {
            el.innerHTML = '<p class="text-muted">No messages sent yet</p>';
            return;
        }

        const date = new Date(messageData.timestamp);
        const timeStr = date.toLocaleString();

        el.innerHTML = `
            <p><strong>Channel:</strong> ${messageData.channel}</p>
            <p><strong>Time:</strong> ${timeStr}</p>
            <p><strong>Message:</strong> ${this.escapeHtml(messageData.preview)}</p>
        `;
    }

    updateUptime(uptimeSeconds) {
        const el = document.getElementById('uptimeInfo');
        if (!el) return;

        if (!uptimeSeconds || uptimeSeconds === 0) {
            el.textContent = 'N/A';
            return;
        }

        const hours = Math.floor(uptimeSeconds / 3600);
        const minutes = Math.floor((uptimeSeconds % 3600) / 60);
        const seconds = Math.floor(uptimeSeconds % 60);

        el.textContent = `${hours}h ${minutes}m ${seconds}s`;
    }

    async setupNotifications() {
        if ('Notification' in window) {
            const permission = await Notification.requestPermission();
            this.notificationsEnabled = (permission === 'granted');

            const button = document.getElementById('enableNotifications');
            if (button) {
                if (this.notificationsEnabled) {
                    button.textContent = 'Notifications Enabled';
                    button.className = 'btn btn-success btn-sm';
                    button.disabled = true;
                } else {
                    button.addEventListener('click', async () => {
                        const perm = await Notification.requestPermission();
                        if (perm === 'granted') {
                            this.notificationsEnabled = true;
                            button.textContent = 'Notifications Enabled';
                            button.className = 'btn btn-success btn-sm';
                            button.disabled = true;
                        }
                    });
                }
            }
        }
    }

    showBrowserNotification(title, message) {
        if (this.notificationsEnabled && document.hidden) {
            new Notification(title, {
                body: message,
                icon: '/static/images/logo.png',
                tag: 'health-alert'
            });
        }
    }

    startPolling() {
        // Fallback polling every 30 seconds
        this.pollingInterval = setInterval(() => {
            this.loadInitialData();
        }, 30000);
    }

    setupEventListeners() {
        // Auto-refresh toggle
        const toggleBtn = document.getElementById('toggleAutoRefresh');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                if (this.pollingInterval) {
                    clearInterval(this.pollingInterval);
                    this.pollingInterval = null;
                    toggleBtn.textContent = 'Enable Auto-Refresh';
                    toggleBtn.className = 'btn btn-outline-secondary btn-sm';
                } else {
                    this.startPolling();
                    toggleBtn.textContent = 'Disable Auto-Refresh';
                    toggleBtn.className = 'btn btn-secondary btn-sm';
                }
            });
        }

        // Manual refresh button
        const refreshBtn = document.getElementById('manualRefresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadInitialData();
            });
        }
    }

    getTimeSince(timestamp) {
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);

            if (seconds < 60) return `${seconds}s ago`;
            if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
            if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
            return `${Math.floor(seconds / 86400)}d ago`;
        } catch {
            return 'Unknown';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        console.error(message);
        // You could show a toast or alert here
    }

    updateAllCards(data) {
        // Convenience method to update all cards at once
        if (data.connection) this.updateConnectionCard(data.connection);
        if (data.errors) this.updateErrorsCard(data.errors);
        if (data.performance) this.updatePerformanceCard(data.performance);
        if (data.background_tasks) this.updateTasksCard(data.background_tasks);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new HealthMonitor();
});
