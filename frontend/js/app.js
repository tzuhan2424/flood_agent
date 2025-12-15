/**
 * Main application entry point
 */
class FloodAgentApp {
    constructor() {
        this.wsClient = new WebSocketClient();

        // Create image and gauge controllers first
        this.imageGallery = new ImageGalleryController(this.wsClient);
        this.gaugeController = new GaugeController(this.wsClient);

        // Pass them to chat controller so it can trigger displays on complete
        this.chatController = new ChatController(this.wsClient, this.imageGallery, this.gaugeController);

        this.sessionId = this.generateSessionId();

        this.init();
    }

    init() {
        // Connect WebSocket
        this.wsClient.connect(this.sessionId);

        // Start heartbeat
        this.wsClient.startHeartbeat();

        // Setup "Load Latest" button
        const loadLatestBtn = document.getElementById('load-latest-button');
        if (loadLatestBtn) {
            loadLatestBtn.addEventListener('click', () => this.loadLatestOutputs());
        }

        console.log('Flood Agent App initialized with session:', this.sessionId);
    }

    async loadLatestOutputs() {
        try {
            console.log('[App] Loading latest outputs...');
            const response = await fetch('/api/outputs/latest');
            const data = await response.json();

            console.log('[App] Latest outputs:', data);

            // Display images
            if (data.images && data.images.length > 0) {
                console.log(`[App] Displaying ${data.images.length} images`);
                this.imageGallery.displayImages(data.images);
            } else {
                console.log('[App] No images found');
            }

            // Display gauges
            if (data.gauges && data.gauges.length > 0) {
                console.log(`[App] Displaying ${data.gauges.length} gauge datasets`);
                // For time series, use chart display
                this.gaugeController.displayTimeSeriesChart(data.gauges);
            } else {
                console.log('[App] No gauge data found');
            }
        } catch (error) {
            console.error('[App] Error loading latest outputs:', error);
        }
    }

    generateSessionId() {
        // Generate or retrieve session ID from localStorage
        let sessionId = localStorage.getItem('flood_agent_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('flood_agent_session_id', sessionId);
        }
        return sessionId;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new FloodAgentApp();
});
