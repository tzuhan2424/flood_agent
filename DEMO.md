# Flood Detection System - Demo Guide

## Quick Start

### Prerequisites
- Python 3.14+
- API Keys:
  - Sentinel Hub (https://www.sentinel-hub.com/)
  - Google AI Studio (Gemini API)

### Installation

```bash
# Clone repository
cd flood_agent

# Create .env file
cat > .env << EOF
SENTINEL_HUB_CLIENT_ID=your_client_id
SENTINEL_HUB_CLIENT_SECRET=your_client_secret
GEMINI_API_KEY=your_gemini_api_key
EOF

# Install dependencies (using UV)
uv venv .venv
source .venv/bin/activate  # or `.venv\Scriptsctivate` on Windows
uv pip install -e "."
```

### Running the System

**Option 1: Web Interface** (Recommended)

```bash
# Start the FastAPI server
python -m uvicorn server.main:app --host 127.0.0.1 --port 8766

# Open browser
http://127.0.0.1:8766
```

**Option 2: CLI** (For testing)

```bash
# Interactive mode
adk run agents

# Direct query
adk run agents --prompt "Show me flooding in Cedar Key on September 27, 2024"
```

---

## Web Interface Demo

### 1. Launch the Application

```bash
# Start server
python -m uvicorn server.main:app --host 127.0.0.1 --port 8766 --reload

# You should see:
INFO:     Uvicorn running on http://127.0.0.1:8766
INFO:     Application startup complete
```

Open browser: **http://127.0.0.1:8766**

### 2. UI Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│ Flood Agent                                   🟢 Connected           │
│ Multi-Agent Flood Detection System                                  │
├────────────────────────────┬─────────────────────────────────────────┤
│ CHAT PANEL (Left 50%)      │ DATA PANEL (Right 50%)                  │
│                            │                                         │
│ ┌────────────────────────┐ │ ┌──────────────────────────────────┐   │
│ │ Messages               │ │ │ Satellite Imagery [Load Latest]  │   │
│ │                        │ │ │ ┌──────────┐ ┌──────────┐        │   │
│ │ Welcome! Ask about     │ │ │ │   RGB    │ │   MASK   │ (2/3)  │   │
│ │ flood detection...     │ │ │ └──────────┘ └──────────┘        │   │
│ │                        │ │ │ ┌───────────────────────┐        │   │
│ └────────────────────────┘ │ │ │      OVERLAY          │        │   │
│                            │ │ └───────────────────────┘        │   │
│ ┌────────────────────────┐ │ └──────────────────────────────────┘   │
│ │ Agent Activity         │ │                                         │
│ │ • Agent: (idle)        │ │ ┌──────────────────────────────────┐   │
│ │ • Tool: (none)         │ │ │ Water Gauge Data                 │   │
│ │ • Progress: [      ]   │ │ │ ┌────────────────────────────┐   │   │
│ └────────────────────────┘ │ │ │ Line Chart                 │ (1/3) │
│                            │ │ │ (Date vs Water Level)      │   │   │
│ ┌────────────────────────┐ │ │ └────────────────────────────┘   │   │
│ │ [Type your question]   │ │ └──────────────────────────────────┘   │
│ │ [Send]                 │ │                                         │
│ └────────────────────────┘ │                                         │
└────────────────────────────┴─────────────────────────────────────────┘
```

### 3. Example Queries

#### Query 1: Single-Date Analysis

**Input:**
```
Show me flooding in Cedar Key, Florida on September 27, 2024
```

**What Happens:**

1. **Status Updates** (in Activity Panel):
```
🟦 FloodAnalysisOrchestrator is analyzing...
   ├─ Geocoding Cedar Key, Florida...
   ├─ DataCollectionAgent: Searching satellite imagery...
   ├─ Tool: segment_flood_area [████░░░░░░] 40%
   │   Status: Running Prithvi water segmentation...
   ├─ Tool: search_gauges [██████████] 100%
   └─ FloodDetectionAgent: Analyzing results...
```

2. **Images Appear** (auto-populated):
```
Row 1:  [RGB Original]     [Water Mask]
Row 2:  [Overlay]
```

3. **Gauge Chart Appears**:
```
Cedar Key, FL (CDRF1)
Action: 1.5 ft | Major: 4.0 ft

  4 ft ┤━━━━━━━━━━━━━━━━━━━━━━ Major
  3 ft ┤━━━━━━━━━━━━━━━━━━━━━━ Moderate
  2 ft ┤━━━━━━━━●━━━━━━━━━━━━━ Minor
  1 ft ┤━━━━━━━━━━━━━━━━━━━━━━ Action
       └────────────────────────
           2024-09-27

  Point: 2.54 ft (Minor Flood)
```

4. **Final Response** (in Chat):
```
Minor flooding detected in Cedar Key on September 27, 2024.

SATELLITE ANALYSIS:
- Water coverage: 45.3%
- Cloud cover: 3%
- Image quality: Excellent

GAUGE VALIDATION:
- Cedar Key gauge (CDRF1): 2.54 ft
- Flood category: MINOR
- Above minor flood stage (2.0 ft)

CONCLUSION:
High confidence flood event. Satellite imagery and gauge data
both confirm minor flooding.
```

---

#### Query 2: Time Series Analysis

**Input:**
```
Analyze flooding in Cedar Key from September 20-30, 2024
```

**What Happens:**

1. **More Processing Time** (~3-5 minutes):
   - Fetches 10+ dates
   - Processes each via Prithvi
   - Computes statistics

2. **Auto-Cycling Images**:
```
Row 1:  [RGB: 2024-09-22 (1/4)]  [MASK: 2024-09-22 (1/4)]
Row 2:  [OVERLAY: 2024-09-22 (1/4)]

(Auto-switches to next date every 2 seconds)
→ 2024-09-24 → 2024-09-27 → 2024-09-29 → back to 2024-09-22...
```

3. **Multi-Point Gauge Chart**:
```
Cedar Key, FL (CDRF1)
Action: 1.5 ft | Major: 4.0 ft

  4 ft ┤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Major
  3 ft ┤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Moderate
  2 ft ┤━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━ Minor
  1 ft ┤━━━━●━━━━━━●━━━━━━━━━━●━━━━━━━━ Action
       └───────────────────────────────────
         9/22  9/24  9/27  9/29

  Peak: 2.54 ft on 9/27 (Minor Flood)
  Baseline: 1.1 ft (Normal)
```

4. **Statistical Analysis** (in Chat):
```
Time Series Flood Analysis: Cedar Key (Sept 20-30, 2024)

BASELINE PERIOD:
- Mean water coverage: 15.2% ± 3.1%
- Normal gauge readings: ~1.1 ft

ANOMALY DETECTION:
- Sept 27: 45.3% water coverage (z-score: 9.7) ⚠️ OUTLIER
- Sept 27: Gauge 2.54 ft (Minor Flood)

FLOOD EVENT CONFIRMED:
- Duration: Single-day spike
- Severity: Minor
- Confidence: HIGH (satellite + gauge agreement)

INTERPRETATION:
Rapid flooding on Sept 27, likely from storm surge.
Water levels returned to normal by Sept 29.
```

---

### 4. Testing Without Agent (Load Latest Button)

**Purpose**: Test frontend display without running full agent pipeline

**Steps**:
1. Click **"Load Latest"** button (top-right of Satellite Imagery section)
2. Fetches most recent outputs from `outputs/` directory
3. Displays images and gauges instantly

**Use Case**: Frontend development/debugging

---

## Example Scenarios

### Scenario 1: Hurricane Helene Impact

**Query:**
```
What was the impact of Hurricane Helene on Cedar Key, Florida?
```

**Agent Workflow:**
1. Geocode "Cedar Key"
2. Search historical weather data (find Helene landfall: Sept 26-27, 2024)
3. Fetch satellite imagery for Sept 20-30 (before/during/after)
4. Run time series analysis
5. Fetch gauge data for validation
6. Compare baseline vs event

**Expected Output:**
- Multi-date images showing water extent
- Gauge chart with clear spike on Sept 27
- Statistical analysis with z-scores
- Damage severity assessment

---

### Scenario 2: Real-Time Monitoring

**Query:**
```
Check current flooding status at Cedar Key
```

**Agent Workflow:**
1. Geocode location
2. Fetch latest Sentinel-2 image (within last 5 days)
3. Segment with Prithvi
4. Get current gauge status (real-time)
5. Compare to historical baseline

**Expected Output:**
- Most recent satellite imagery
- Current gauge reading
- Trend analysis (rising/falling/stable)
- Alert if above flood stage

---

### Scenario 3: Historical Research

**Query:**
```
Find all flooding events in Cedar Key during 2024
```

**Agent Workflow:**
1. Fetch satellite imagery for entire year (365 days)
2. Smart sampling: evenly_spaced → ~12 dates
3. Run time series analysis
4. Identify statistical outliers (z-score > 2)
5. Cross-reference with gauge data

**Expected Output:**
- List of flood dates with severity
- Time series chart showing annual trend
- Images for each detected event
- Statistical summary

---

## CLI Demo

### Basic Usage

```bash
# Start interactive session
adk run agents

# Chat prompt appears
You> Show me flooding in Cedar Key on Sept 27, 2024

# Agent responds with text-only output
Agent> Minor flooding detected. Satellite shows 45.3% water coverage...

# Outputs saved to: outputs/20240927_HHMMSS/
```

### Direct Command

```bash
adk run agents --prompt "Analyze flooding in Cedar Key Sept 20-30, 2024"
```

### Debug Mode

```bash
# See all agent reasoning steps
adk run agents --debug

# Shows:
[FloodAnalysisOrchestrator] Routing to DataCollectionAgent...
[DataCollectionAgent] Calling search_sentinel_images()...
[MCP Tool] segment_flood_area starting...
[Prithvi AI] Processing 6-band TIFF...
```

---

## Testing MCP Tools Directly

You can test individual MCP tools without running the full agent:

### Test Sentinel Search

```python
# In Python shell
from mcp_server.server import search_sentinel_images

result = await search_sentinel_images(
    start_date="2024-09-27",
    end_date="2024-09-27",
    bbox=[-83.05, 29.12, -82.95, 29.18],
    max_cloud_cover=10.0,
    limit=10
)

print(f"Found {result['total_found']} images")
print(f"Dates: {result['dates']}")
```

### Test Flood Segmentation

```python
from mcp_server.server import segment_flood_area

result = await segment_flood_area(
    date="2024-09-27",
    location="Cedar Key, FL"
)

print(f"Water coverage: {result['water_coverage']}%")
print(f"Outputs saved to: {result['parent_dir']}")
```

### Test Gauge Search

```python
from mcp_server.server import search_gauges, get_gauge_status

# Find gauges
gauges = await search_gauges(
    location="Cedar Key, FL",
    radius=25
)

print(f"Found {len(gauges['gauges'])} gauges")

# Get status
status = await get_gauge_status(lid="CDRF1")
print(f"Water level: {status['gauges'][0]['peak_observation']['stage_ft']} ft")
print(f"Flood category: {status['gauges'][0]['flood_status']['current_category']}")
```

---

## Output Files

All analysis results are saved to `outputs/{run_id}/{date}/`:

```
outputs/
└── timeseries_20240920_to_20240930_205617/  # Run ID (timestamp)
    ├── 20240922/                             # Date subdirectories
    │   ├── original_viz.webp                 # RGB composite
    │   ├── water_mask.webp                   # Binary water mask
    │   ├── overlay.webp                      # Water overlay on RGB
    │   ├── sentinel_image.tif                # Raw 6-band GeoTIFF
    │   └── gauge_data.json                   # Gauge readings
    ├── 20240924/
    ├── 20240927/
    └── 20240929/
```

### Opening Outputs

**Images**: View directly in browser
```
http://127.0.0.1:8766/api/outputs/{run_id}/{date}/original_viz.webp
```

**GeoTIFF**: Open in QGIS/ArcGIS for spatial analysis

**Gauge Data**: JSON file with structure:
```json
{
  "gauges": [
    {
      "lid": "CDRF1",
      "name": "Cedar Key, FL",
      "peak_observation": {
        "stage_ft": 2.54,
        "date": "2024-09-27T12:00:00Z"
      },
      "flood_status": {
        "current_category": "minor"
      },
      "flood_categories": {
        "action": 1.5,
        "minor": 2.0,
        "moderate": 3.0,
        "major": 4.0
      }
    }
  ]
}
```

---

## Troubleshooting

### Issue: "No images found"

**Cause**: Cloud cover too high or no satellite pass

**Solution**:
```
Try wider date range or higher max_cloud_cover:
"Search from Sept 20-30 with up to 30% cloud cover"
```

### Issue: "Gauge not found"

**Cause**: No NOAA/USGS gauge near location

**Solution**:
```
Use satellite-only analysis:
"Show satellite flooding in [location] on [date]"
```

### Issue: WebSocket disconnects

**Cause**: Long processing time (>5 min)

**Solution**:
- Increase WebSocket timeout
- Or refresh and click "Load Latest" to see results

### Issue: "API rate limit exceeded"

**Cause**: Sentinel Hub free tier limit

**Solution**:
- Wait 24 hours (daily quota resets)
- Or upgrade to paid plan

---

## Performance Notes

### Processing Times

| Operation | Time | Notes |
|-----------|------|-------|
| Geocoding | <1s | Gemini API |
| Sentinel search | 2-3s | Catalog query |
| Prithvi segmentation | ~35s | Per image |
| Gauge fetch | 1-2s | NWPS API |
| Agent reasoning | 3-5s | Gemini API |

**Total for single date**: ~45 seconds  
**Total for 10-day time series**: ~6 minutes (10 images × 35s + overhead)

### Optimization Tips

1. **Use smart sampling** for large time ranges
   ```
   "Analyze 2024 flooding with evenly spaced samples"
   (Returns 12 images instead of 365)
   ```

2. **Specify cloud cover**
   ```
   "Use images with less than 5% clouds"
   (Faster Prithvi processing with clear images)
   ```

3. **Request specific dates**
   ```
   "Show Sept 27, 2024 only"
   (Single image instead of time series)
   ```

---

## API Reference

### REST Endpoints

**POST /api/chat/message**
```json
Request:
{
  "message": "Show me flooding...",
  "session_id": "session_123"  // Optional
}

Response:
{
  "session_id": "session_123",
  "status": "started",
  "message": "Agent is processing..."
}
```

**GET /api/outputs/latest**
```json
Response:
{
  "run_id": "timeseries_20240920_to_20240930_205617",
  "images": [
    "/api/outputs/{run_id}/{date}/original_viz.webp",
    ...
  ],
  "gauges": [
    {"date": "2024-09-27", "data": {...}},
    ...
  ]
}
```

### WebSocket Events

**Connect**: `ws://127.0.0.1:8766/ws/{session_id}`

**Event Types**:
- `connected` - Connection established
- `agent_thought` - Agent reasoning
- `tool_start` - Tool execution begins
- `tool_progress` - Progress update (0-100%)
- `tool_complete` - Tool finished
- `complete` - Analysis done (includes all outputs)
- `error` - Error occurred

---

## Next Steps

1. **Try different locations**:
   - "Miami Beach, FL"
   - "Houston, TX"
   - "New Orleans, LA"

2. **Experiment with date ranges**:
   - Single day (fast)
   - Week (moderate)
   - Month (slow but comprehensive)

3. **Explore outputs**:
   - Open GeoTIFF in GIS software
   - Analyze gauge data trends
   - Compare water masks over time

4. **Extend the system**:
   - Add new MCP tools (weather data, elevation)
   - Create new agents (predictive modeling)
   - Integrate with external systems (alerts, dashboards)

---

## Demo Video Script

**[0:00-0:30] Introduction**
"This is a real-time flood detection system using AI, satellite imagery, and ground sensors."

**[0:30-1:00] Show UI**
"The interface has a chat panel on the left and data visualization on the right."

**[1:00-2:00] Example Query**
Type: "Show me flooding in Cedar Key on Sept 27, 2024"
Watch activity panel update in real-time.

**[2:00-3:00] Results**
Images appear auto-cycling through RGB, water mask, and overlay.
Gauge chart shows water level spike.

**[3:00-4:00] Explain Technology**
"Behind the scenes: Gemini AI routes to specialist agents, fetches Sentinel-2 satellite data,
processes with Prithvi AI, validates with NOAA gauges, all in real-time."

**[4:00-4:30] Conclusion**
"This combines the best of satellite imagery, AI, and sensor networks for
accurate flood detection and analysis."
