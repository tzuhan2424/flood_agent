/**
 * Gauge data display controller
 */
class GaugeController {
    constructor(wsClient) {
        this.wsClient = wsClient;
        this.container = document.getElementById('gauges-container');
        this.gaugeCount = document.getElementById('gauge-count');
        this.gauges = [];

        this.setupWebSocketListeners();
    }

    setupWebSocketListeners() {
        this.wsClient.on('gauge_data', (data) => {
            this.displayGaugeData(data.data);
        });
    }

    displayGaugeData(gaugeData) {
        // Remove placeholder
        const placeholder = this.container.querySelector('.placeholder');
        if (placeholder) placeholder.remove();

        if (!gaugeData.gauges || gaugeData.gauges.length === 0) {
            return;
        }

        for (const gauge of gaugeData.gauges) {
            this.addGauge(gauge);
        }

        this.updateGaugeCount();
    }

    addGaugeCard(gaugeInfo) {
        /**
         * Display a single gauge with basic info (for backward compatibility)
         */
        this.addGauge(gaugeInfo);
    }

    addGauge(gaugeInfo) {
        // Check if gauge already exists
        const existing = this.container.querySelector(`[data-lid="${gaugeInfo.lid}"]`);
        if (existing) {
            existing.remove();
        }

        this.gauges.push(gaugeInfo);

        const category = gaugeInfo.flood_status?.current_category || 'normal';
        const stageFt = gaugeInfo.peak_observation?.stage_ft || gaugeInfo.current_observation?.stage_ft || 0;

        const gaugeCard = document.createElement('div');
        gaugeCard.className = `gauge-card ${category}`;
        gaugeCard.dataset.lid = gaugeInfo.lid;

        gaugeCard.innerHTML = `
            <div class="gauge-header">
                <div>
                    <div class="gauge-name">${gaugeInfo.name}</div>
                    <div class="gauge-id">${gaugeInfo.lid}</div>
                </div>
                <div class="flood-badge ${category}">${category.toUpperCase()}</div>
            </div>

            <div class="gauge-reading">${stageFt.toFixed(2)} ft</div>

            <div class="gauge-metadata">
                <div class="metadata-item">
                    <span class="metadata-label">Location</span>
                    <span class="metadata-value">
                        ${gaugeInfo.location?.latitude?.toFixed(4) || 'N/A'},
                        ${gaugeInfo.location?.longitude?.toFixed(4) || 'N/A'}
                    </span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Date</span>
                    <span class="metadata-value">${gaugeInfo.observation_date || 'N/A'}</span>
                </div>
            </div>
        `;

        this.container.appendChild(gaugeCard);
    }

    displayTimeSeriesChart(gaugeDatasets) {
        /**
         * Display gauge time series with line chart
         * @param {Array} gaugeDatasets - Array of {date, data: {gauges: [...]}}
         */
        console.log('[Gauges] Displaying time series chart:', gaugeDatasets);

        // Clear container
        this.container.innerHTML = '';

        if (!gaugeDatasets || gaugeDatasets.length === 0) {
            this.container.innerHTML = '<p class="placeholder">No gauge data available</p>';
            return;
        }

        // Extract data for chart (assuming first gauge in each dataset)
        const chartData = gaugeDatasets.map(ds => {
            const gauge = ds.data.gauges?.[0];
            return {
                date: ds.date,
                value: gauge?.peak_observation?.stage_ft || 0,
                category: gauge?.flood_status?.current_category || 'normal',
                gauge: gauge
            };
        }).filter(d => d.gauge);

        if (chartData.length === 0) {
            this.container.innerHTML = '<p class="placeholder">No gauge measurements found</p>';
            return;
        }

        // Create chart container
        const chartContainer = document.createElement('div');
        chartContainer.className = 'gauge-chart-container';

        const firstGauge = chartData[0].gauge;
        chartContainer.innerHTML = `
            <div class="chart-header">
                <div>
                    <div class="chart-title">${firstGauge.name}</div>
                    <div class="chart-subtitle">${firstGauge.lid}</div>
                </div>
                <div class="chart-info">
                    Action: ${firstGauge.flood_categories?.action || 'N/A'} ft |
                    Major: ${firstGauge.flood_categories?.major || 'N/A'} ft
                </div>
            </div>
            <canvas id="gauge-chart" width="500" height="200"></canvas>
        `;

        this.container.appendChild(chartContainer);

        // Draw chart after DOM update
        setTimeout(() => this.drawChart(chartData, firstGauge.flood_categories), 0);

        this.updateGaugeCount();
    }

    drawChart(data, floodCategories) {
        const canvas = document.getElementById('gauge-chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        // Chart dimensions
        const padding = { top: 15, right: 35, bottom: 50, left: 50 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Find min/max values
        const values = data.map(d => d.value);
        const maxValue = Math.max(...values, floodCategories?.major || 0);
        const minValue = Math.min(...values, 0);

        // Scale functions
        const xScale = (i) => padding.left + (i / (data.length - 1)) * chartWidth;
        const yScale = (v) => padding.top + chartHeight - ((v - minValue) / (maxValue - minValue)) * chartHeight;

        // Draw flood category zones
        if (floodCategories) {
            const zones = [
                { level: floodCategories.action, color: '#FEF3C7', label: 'Action' },
                { level: floodCategories.minor, color: '#FED7AA', label: 'Minor' },
                { level: floodCategories.moderate, color: '#FCA5A5', label: 'Moderate' },
                { level: floodCategories.major, color: '#F87171', label: 'Major' }
            ];

            zones.forEach(zone => {
                if (zone.level) {
                    const y = yScale(zone.level);
                    ctx.strokeStyle = zone.color.replace('F', '8');
                    ctx.lineWidth = 1;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(padding.left, y);
                    ctx.lineTo(width - padding.right, y);
                    ctx.stroke();
                    ctx.setLineDash([]);

                    // Label
                    ctx.fillStyle = '#666';
                    ctx.font = '10px sans-serif';
                    ctx.textAlign = 'right';
                    ctx.fillText(zone.label, width - padding.right + 35, y + 3);
                }
            });
        }

        // Draw axes
        ctx.strokeStyle = '#666';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, height - padding.bottom);
        ctx.lineTo(width - padding.right, height - padding.bottom);
        ctx.stroke();

        // Draw line
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 3;
        ctx.beginPath();
        data.forEach((d, i) => {
            const x = xScale(i);
            const y = yScale(d.value);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Draw points
        data.forEach((d, i) => {
            const x = xScale(i);
            const y = yScale(d.value);

            // Point
            ctx.fillStyle = '#2563eb';
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fill();

            // Date label (x-axis)
            ctx.fillStyle = '#333';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.save();
            ctx.translate(x, height - padding.bottom + 15);
            ctx.rotate(-Math.PI / 4);
            ctx.fillText(d.date, 0, 0);
            ctx.restore();
        });

        // Y-axis labels
        const yTicks = 5;
        for (let i = 0; i <= yTicks; i++) {
            const value = minValue + (i / yTicks) * (maxValue - minValue);
            const y = yScale(value);
            ctx.fillStyle = '#666';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(value.toFixed(1) + ' ft', padding.left - 10, y + 4);
        }

        // Axis labels
        ctx.fillStyle = '#333';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Date', width / 2, height - 10);

        ctx.save();
        ctx.translate(15, height / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText('Water Level (ft)', 0, 0);
        ctx.restore();
    }

    updateGaugeCount() {
        this.gaugeCount.textContent = `${this.gauges.length} gauge${this.gauges.length !== 1 ? 's' : ''}`;
    }

    clear() {
        this.container.innerHTML = '<p class="placeholder">Gauge data will appear here</p>';
        this.gauges = [];
        this.updateGaugeCount();
    }
}

window.GaugeController = GaugeController;
