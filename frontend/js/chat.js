/**
 * Chat interface controller
 */
class ChatController {
    constructor(wsClient, imageController = null, gaugeController = null) {
        this.wsClient = wsClient;
        this.imageController = imageController;
        this.gaugeController = gaugeController;
        this.messagesContainer = document.getElementById('messages');
        this.activityContainer = document.getElementById('activity-content');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');

        this.setupEventListeners();
        this.setupWebSocketListeners();
    }

    setupEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());

        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    setupWebSocketListeners() {
        // Agent thoughts
        this.wsClient.on('agent_thought', (data) => {
            this.addAgentMessage(data.agent_name, data.thought);
            this.addActivityItem('agent', data.agent_name, data.thought);
        });

        // Tool execution
        this.wsClient.on('tool_start', (data) => {
            this.addActivityItem('tool', data.tool_name, data.status, data.progress);
        });

        this.wsClient.on('tool_progress', (data) => {
            this.updateActivityProgress(data.tool_name, data.status, data.progress);
        });

        this.wsClient.on('tool_complete', (data) => {
            this.updateActivityProgress(data.tool_name, data.status, 100);
            setTimeout(() => {
                const item = this.activityContainer.querySelector(`[data-name="${data.tool_name}"]`);
                if (item) {
                    item.classList.remove('tool');
                    item.classList.add('complete');
                }
            }, 500);
        });

        this.wsClient.on('tool_error', (data) => {
            this.addActivityItem('error', data.tool_name, data.error || 'Error occurred');
        });

        // Complete
        this.wsClient.on('complete', (data) => {
            this.addAgentMessage('System', data.final_message || 'Analysis complete!');
            this.sendButton.disabled = false;

            // If data is provided with images/gauges, display them
            if (data.data) {
                console.log('[Chat] Complete event with data:', data.data);

                // Display images
                if (data.data.images && data.data.images.length > 0 && this.imageController) {
                    console.log(`[Chat] Displaying ${data.data.images.length} images`);
                    this.imageController.displayImages(data.data.images);
                }

                // Display gauges
                if (data.data.gauges && data.data.gauges.length > 0 && this.gaugeController) {
                    console.log(`[Chat] Displaying ${data.data.gauges.length} gauge datasets`);
                    // For time series, use chart display
                    this.gaugeController.displayTimeSeriesChart(data.data.gauges);
                }
            }
        });

        this.wsClient.on('error', (data) => {
            this.addAgentMessage('System', `Error: ${data.error}`, true);
            this.sendButton.disabled = false;
        });
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;

        // Add user message to UI
        this.addUserMessage(message);

        // Clear input
        this.chatInput.value = '';

        // Disable send button
        this.sendButton.disabled = true;

        // Clear activity
        this.activityContainer.innerHTML = '<p class="inactive">Processing...</p>';

        try {
            // Send to API
            const response = await fetch('/api/chat/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: this.wsClient.sessionId
                })
            });

            const data = await response.json();

            if (data.status === 'started') {
                // WebSocket will receive updates
                this.addActivityItem('agent', 'System', 'Agent processing your request...');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.addAgentMessage('System', 'Failed to send message', true);
            this.sendButton.disabled = false;
        }
    }

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `
            <div class="message-header">You</div>
            <div class="message-content">${this.escapeHtml(text)}</div>
        `;
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAgentMessage(agent, text, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message agent ${isError ? 'error' : ''}`;
        messageDiv.innerHTML = `
            <div class="message-header">${agent}</div>
            <div class="message-content">${this.escapeHtml(text)}</div>
        `;
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addActivityItem(type, name, text, progress = null) {
        // Remove inactive message
        const inactive = this.activityContainer.querySelector('.inactive');
        if (inactive) inactive.remove();

        const activityDiv = document.createElement('div');
        activityDiv.className = `activity-item ${type}`;
        activityDiv.dataset.name = name;

        let progressHtml = '';
        if (progress !== null) {
            progressHtml = `
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${progress}%"></div>
                </div>
            `;
        }

        activityDiv.innerHTML = `
            <div class="activity-timestamp">${new Date().toLocaleTimeString()}</div>
            <div class="activity-agent">${name}</div>
            <div class="activity-text">${this.escapeHtml(text)}</div>
            ${progressHtml}
        `;

        this.activityContainer.appendChild(activityDiv);
        this.activityContainer.scrollTop = this.activityContainer.scrollHeight;
    }

    updateActivityProgress(toolName, status, progress) {
        const existingItem = this.activityContainer.querySelector(`[data-name="${toolName}"]`);
        if (existingItem) {
            existingItem.querySelector('.activity-text').textContent = status;
            const progressBar = existingItem.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
            } else if (progress !== null) {
                // Add progress bar if it doesn't exist
                const progressHtml = `
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${progress}%"></div>
                    </div>
                `;
                existingItem.insertAdjacentHTML('beforeend', progressHtml);
            }
        } else {
            this.addActivityItem('tool', toolName, status, progress);
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

window.ChatController = ChatController;
