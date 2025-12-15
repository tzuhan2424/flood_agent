# How the Flood Detection System Works

## Table of Contents
1. [System Purpose](#system-purpose)
2. [Technology Deep Dive](#technology-deep-dive)
3. [Multi-Agent Workflow](#multi-agent-workflow)
4. [Sentinel-2 Satellite Imagery](#sentinel-2-satellite-imagery)
5. [Prithvi AI Water Segmentation](#prithvi-ai-water-segmentation)
6. [NWPS Gauge Integration](#nwps-gauge-integration)
7. [Real-Time Web Interface](#real-time-web-interface)
8. [Complete Analysis Flow](#complete-analysis-flow)

---

## System Purpose

This system provides **real-time flood detection and analysis** by combining:
- **Satellite imagery** (visual evidence of flooding)
- **AI water segmentation** (automated flood boundary detection)
- **Ground sensors** (gauge data for validation)
- **Multi-agent AI** (intelligent analysis and reasoning)

**Use Cases**:
- Post-disaster damage assessment
- Historical flood analysis
- Real-time flood monitoring
- Research and climate studies

---

## Technology Deep Dive

### 1. Google ADK (Agent Development Kit)

**What is it?**  
Framework for building **multi-agent AI systems** using Gemini models. Agents can:
- Use tools (MCP, custom functions)
- Call other agents (AgentTool pattern)
- Maintain conversation state
- Reason about complex problems

**Why use it?**  
- Natural language interface (no rigid APIs)
- Intelligent routing (agents decide which tools to use)
- Extensible (easy to add new data sources)
- Conversational (maintains context across queries)

### 2. Model Context Protocol (MCP)

**What is it?**  
Standard protocol for exposing tools to AI models via stdio communication.

**How it works**:
1. MCP server starts as subprocess
2. Communicates via JSON-RPC over stdin/stdout
3. Exposes tools with structured schemas
4. Agent calls tools → server executes → returns results

**Why use it?**  
- Sandboxed execution (security)
- Language-agnostic (Python server, any client)
- Auto-discovery of tools
- Type-safe with JSON schemas

### 3. Gemini 2.0 Flash

**Model Capabilities**:
- **Context window**: 1M tokens (huge!)
- **Function calling**: Native tool use
- **Multimodal**: Text, images, code
- **Speed**: ~2 seconds per turn

**Why Gemini 2.0?**  
- Fast enough for real-time interaction
- Excellent at tool orchestration
- Good at spatial reasoning (coordinates, maps)
- Cost-effective for high-volume queries

---

## Multi-Agent Workflow

### Agent Roles

**FloodAnalysisOrchestrator** (Root Agent)
- **Role**: Router and coordinator
- **Decides**: Which specialist agent(s) to call
- **Synthesizes**: Final response from sub-agent results
- **Example**: User asks about "flooding in Cedar Key"
  - Recognizes need for satellite data → calls DataCollectionAgent
  - Recognizes need for analysis → calls FloodDetectionAgent
  - Combines results into coherent answer

**DataCollectionAgent**
- **Role**: Data fetcher
- **Tools**: MCP satellite and gauge tools
- **Output**: Raw imagery, gauge readings, metadata
- **Does NOT**: Analyze or interpret data

**FloodDetectionAgent**  
- **Role**: Statistical analyst
- **Input**: Imagery from DataCollectionAgent
- **Methods**:
  - Baseline comparison (pre-flood vs event)
  - Z-score anomaly detection
  - Gauge validation
- **Output**: Flood severity, confidence level

**ImpactAssessmentAgent**
- **Role**: Damage estimator
- **Input**: Flood extent from FloodDetectionAgent
- **Methods**: Population density analysis, infrastructure mapping
- **Output**: Evacuation plans, damage estimates

### AgentTool Pattern

```python
# Agents are wrapped as tools
data_tool = AgentTool(agent=data_collection_agent)
flood_tool = AgentTool(agent=flood_detection_agent)

# Orchestrator can call them like functions
root_agent = LlmAgent(
    tools=[data_tool, flood_tool, ...]
)
```

**Why this pattern?**  
- Orchestrator treats agents as high-level tools
- Agents can have their own sub-tools (MCP tools)
- Recursive composition (agents calling agents)
- Clear separation of concerns

---

## Sentinel-2 Satellite Imagery

### What is Sentinel-2?

**Satellite Program**: European Space Agency (ESA) Copernicus  
**Mission**: Land monitoring and emergency response  
**Constellation**: Sentinel-2A + Sentinel-2B  
**Launch**: 2015 (2A), 2017 (2B)

### Technical Specifications

| Parameter | Value |
|-----------|-------|
| Revisit Time | 5 days (both satellites) |
| Swath Width | 290 km |
| Resolution | 10m (visible), 20m (NIR/SWIR) |
| Spectral Bands | 13 bands (443nm - 2190nm) |
| Data Volume | ~1.6 TB/day |

### Six Bands Used by Prithvi

We use **6 out of 13 bands** for water detection:

| Band | Name | Wavelength | Resolution | Purpose |
|------|------|------------|------------|---------|
| B02 | Blue | 490nm | 10m | RGB visualization |
| B03 | Green | 560nm | 10m | RGB visualization |
| B04 | Red | 665nm | 10m | RGB visualization |
| B8A | Narrow NIR | 865nm | 20m | Vegetation vs water |
| B11 | SWIR 1 | 1610nm | 20m | Water absorption |
| B12 | SWIR 2 | 2190nm | 20m | Water detection |

**Why these bands?**
- **NIR (B8A)**: Water absorbs NIR → appears dark
- **SWIR (B11/B12)**: Even stronger water absorption → clearest signal
- **Combined**: Prithvi learned optimal weights from training data

### Sentinel Hub API

**Provider**: Sinergise (commercial Copernicus distributor)  
**Authentication**: OAuth2 client credentials  
**API Endpoints**:
- **Catalog API**: Search available imagery
- **Process API**: Fetch pixels for specific bands

**Example Request**:
```python
# Search for images
search_sentinel_images(
    start_date="2024-09-20",
    end_date="2024-09-30",
    bbox=[-83.05, 29.12, -82.95, 29.18],  # Cedar Key
    max_cloud_cover=10.0
)
# Returns: 47 images found, sampled to 12 evenly spaced
```

### Smart Sampling Strategies

When many images are found (e.g., 100+ for a year), we use strategies:

1. **lowest_cloud**: Best quality images (cloud cover < 5%)
2. **evenly_spaced**: Distributed across time range (for trends)
3. **most_recent**: Latest imagery first (for disasters)
4. **oldest_first**: Historical baseline
5. **all**: Return everything (up to 100 max)

**Why sampling?**  
Processing 100 images via Prithvi AI = 100 × 35s = ~1 hour!  
Sampling to 12 images = 12 × 35s = ~7 minutes ✓

---

## Prithvi AI Water Segmentation

### What is Prithvi?

**Model**: IBM + NASA Foundation Model for Earth Observation  
**Version**: Prithvi-EO-2.0-Sen1Floods11  
**Training Data**: Sen1Floods11 dataset (global flood events)  
**Architecture**: Vision Transformer (ViT) encoder + UNet decoder

### How It Works

**Input**: Sentinel-2 6-band GeoTIFF (shape: [6, H, W])  
**Processing**:
1. Normalize pixel values (0-10000 → 0-1)
2. Split into 224×224 patches
3. Encode with ViT (learned Earth features)
4. Decode with UNet (pixel-level segmentation)
5. Threshold at 0.5 → binary mask

**Output**: Binary mask (0 = land, 1 = water)

### Why Prithvi > Traditional Methods?

**Traditional (NDWI - Normalized Difference Water Index)**:
```python
NDWI = (Green - NIR) / (Green + NIR)
water_mask = NDWI > 0.3  # Fixed threshold
```
**Problems**:
- Misses clouds as water (both reflective)
- Struggles with shadows, vegetation
- Fixed threshold doesn't adapt

**Prithvi AI**:
- **Learned features**: Trained on 10,000+ flood images
- **Context-aware**: Considers surrounding pixels
- **Adaptive**: No fixed thresholds
- **Handles edge cases**: Clouds, shadows, urban areas

### Deployment via HuggingFace Spaces

**Why HuggingFace?**  
- Pre-deployed model (no local GPU needed)
- API access via HTTP POST
- Automatic scaling
- Free tier available

**API Call**:
```python
# Upload 6-band TIFF
files = {"image": open("sentinel.tif", "rb")}
response = requests.post(PRITHVI_API_URL, files=files)

# Get binary mask
mask = np.array(response.json()["mask"])  # Shape: [H, W]
```

**Processing Time**: ~35 seconds per image
- Upload: ~5s (2MB file)
- Inference: ~25s (GPU processing)
- Download: ~5s (mask result)

### Output Files Generated

1. **original_viz.webp**: RGB composite (B04/B03/B02)
2. **water_mask.webp**: Binary mask (blue = water)
3. **overlay.webp**: Water mask overlaid on RGB
4. **sentinel_image.tif**: Raw 6-band GeoTIFF (for GIS)

**Why WebP?**  
- 30% smaller than PNG
- Faster browser loading
- Lossless compression

---

## NWPS Gauge Integration

### What is NWPS?

**Full Name**: National Water Prediction Service  
**Agencies**: NOAA + USGS partnership  
**Purpose**: Real-time river/coastal monitoring  
**Coverage**: ~8,500 gauges across USA

### Gauge Data Available

**Measurements**:
- **Stage**: Water level (feet above datum)
- **Discharge**: Flow rate (cubic feet/second)
- **Flood Categories**: Normal/Action/Minor/Moderate/Major

**Flood Stage Thresholds** (example for Cedar Key, FL):
| Category | Stage (ft) | Description |
|----------|-----------|-------------|
| Normal | < 1.5 | No flooding |
| Action | 1.5 | Prepare for flooding |
| Minor | 2.0 | Low-lying roads flood |
| Moderate | 3.0 | Significant damage |
| Major | 4.0 | Severe flooding |

### API Integration

**Base URL**: `https://api.water.noaa.gov/nwps/v1`

**Endpoints Used**:

1. **Search Gauges**: Find nearest gauges to a location
```python
GET /gauges/search?lat=29.14&lon=-83.03&radius=50
# Returns: List of gauges within 50 miles
```

2. **Get Status**: Current readings
```python
GET /gauges/{lid}/status
# Returns: Current stage, flood category, last update
```

3. **Get Timeseries**: Historical data
```python
GET /gauges/{lid}/timeseries?start=2024-09-20&end=2024-09-30
# Returns: Hourly/daily readings
```

### Why Combine Satellite + Gauge Data?

**Satellite Alone**:
- ✓ Spatial coverage (see entire region)
- ✗ Cloud cover issues
- ✗ 5-day revisit (not real-time)

**Gauge Alone**:
- ✓ Real-time updates (every 15 min)
- ✓ Accurate water level
- ✗ Point measurements only
- ✗ Limited spatial context

**Combined**:
- **Validation**: Gauge confirms satellite-detected water
- **Temporal**: Gauge fills gaps between satellite passes
- **Spatial**: Satellite shows extent beyond gauge location
- **Confidence**: Agreement = high confidence, disagreement = investigate

### Cross-Validation Logic

```python
satellite_says_flood = water_coverage > 30%
gauge_says_flood = flood_category in ["minor", "moderate", "major"]

if satellite_says_flood and gauge_says_flood:
    confidence = "HIGH"
elif satellite_says_flood or gauge_says_flood:
    confidence = "MEDIUM"  # Investigate further
else:
    confidence = "LOW"  # Likely false alarm
```

---

## Real-Time Web Interface

### Architecture

**Frontend** (Vanilla JS)  
↕ (WebSocket)  
**Backend** (FastAPI)  
↕ (ADK Runner)  
**MCP Server** (Tools)

### WebSocket Event Flow

**Backend → Frontend Messages**:

1. **agent_thought**
```json
{
  "type": "agent_thought",
  "agent_name": "DataCollectionAgent",
  "thought": "Searching for Sentinel-2 imagery..."
}
```

2. **tool_start**
```json
{
  "type": "tool_start",
  "tool_name": "segment_flood_area",
  "status": "Starting flood segmentation...",
  "progress": 0
}
```

3. **tool_progress** (simulated for long operations)
```json
{
  "type": "tool_progress",
  "tool_name": "segment_flood_area",
  "status": "Running Prithvi AI...",
  "progress": 60
}
```

4. **tool_complete**
```json
{
  "type": "tool_complete",
  "tool_name": "segment_flood_area",
  "result": {"water_coverage": 45.3, "run_id": "..."}
}
```

5. **complete** (final event with all outputs)
```json
{
  "type": "complete",
  "data": {
    "images": ["/api/outputs/.../original_viz.webp", ...],
    "gauges": [{"date": "2024-09-27", "data": {...}}]
  }
}
```

### Frontend Components

**1. Chat Panel** (chat.js)
- Displays user messages (right-aligned, blue)
- Displays agent messages (left-aligned, gray)
- Activity panel shows current agent + tool status
- Progress bars animate during long operations

**2. Image Gallery** (images.js)
- **Row 1**: RGB + MASK side-by-side (auto-cycling)
- **Row 2**: OVERLAY full-width (auto-cycling)
- Auto-cycle every 2 seconds through dates
- Click for full-screen modal

**3. Gauge Chart** (gauges.js)
- Canvas-based line chart
- X-axis: Dates (rotated 45° for readability)
- Y-axis: Water level (ft)
- Data points: peak_observation
- Threshold lines: Action/Minor/Moderate/Major flood stages
- Color-coded by severity

### Why Auto-Cycling?

**Problem**: Time series query (30 days) generates:
- 12 dates × 3 image types = **36 images**
- Displaying all at once = overwhelming UI

**Solution**: Auto-cycle through dates
- Show 1 date at a time for each category
- User sees temporal evolution (like animation)
- Counter shows progress: "3 / 12"

---

## Complete Analysis Flow

### Example Query: "Show me flooding in Cedar Key on September 27, 2024"

**Step-by-Step Execution**:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER QUERY                                                   │
│    Frontend: User types query → Send button clicked             │
│    POST /api/chat/message {"message": "...", "session_id": "x"} │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. BACKEND RECEIVES                                             │
│    server/routers/chat.py                                       │
│    - Get/create ADK session                                     │
│    - Start async task: run_agent_background()                   │
│    - Return {"status": "started"}                               │
│    Frontend: Shows "Agent is processing..." in activity panel   │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. ADK ORCHESTRATOR STARTS                                      │
│    FloodAnalysisOrchestrator analyzes query                     │
│    Broadcast: agent_thought "Orchestrator analyzing query..."   │
│    Frontend: Activity panel updates                             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. GEOCODING                                                    │
│    Orchestrator calls: geocode_location("Cedar Key")            │
│    Returns: [-83.03, 29.13, -82.97, 29.19]                      │
│    Broadcast: tool_complete "Geocoding done"                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. DATA COLLECTION AGENT                                        │
│    Orchestrator routes to DataCollectionAgent                   │
│    Broadcast: agent_thought "DataCollectionAgent searching..."  │
│                                                                 │
│    Agent calls MCP tools:                                       │
│    a) search_sentinel_images(                                   │
│         start="2024-09-27", end="2024-09-27",                   │
│         bbox=[-83.03, 29.13, -82.97, 29.19]                     │
│       )                                                         │
│       → Returns: 2 images found                                 │
│       Broadcast: tool_complete "Found 2 images"                 │
│                                                                 │
│    b) segment_flood_area(                                       │
│         date="2024-09-27",                                      │
│         location="Cedar Key, FL"                                │
│       )                                                         │
│       Broadcast: tool_start "Starting segmentation..."          │
│       ┌─────────────────────────────────────────────┐          │
│       │ MCP Server Execution                        │          │
│       │ 1. Fetch Sentinel-2 6-band TIFF (5s)        │          │
│       │    Broadcast: progress 20% "Downloading..."  │          │
│       │ 2. Send to Prithvi API (25s)                │          │
│       │    Broadcast: progress 60% "Running AI..."   │          │
│       │ 3. Generate masks (5s)                      │          │
│       │    Broadcast: progress 95% "Saving..."       │          │
│       │ 4. Save to outputs/20240927_HHMMSS/         │          │
│       └─────────────────────────────────────────────┘          │
│       → Returns: {"water_coverage": 45.3, "run_id": "..."}      │
│       Broadcast: tool_complete "Segmentation done"              │
│       Frontend: Progress bar completes                          │
│                                                                 │
│    c) search_gauges(location="Cedar Key, FL", radius=25)        │
│       → Returns: [{"lid": "CDRF1", "name": "Cedar Key"}]        │
│                                                                 │
│    d) get_gauge_status(lid="CDRF1")                             │
│       → Returns: {                                              │
│           "stage_ft": 2.54,                                     │
│           "flood_category": "minor"                             │
│         }                                                       │
│       Broadcast: tool_complete "Gauge data retrieved"           │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. FLOOD DETECTION AGENT                                        │
│    Orchestrator routes to FloodDetectionAgent                   │
│    Broadcast: agent_thought "Analyzing flood extent..."         │
│                                                                 │
│    Agent analyzes:                                              │
│    - Water coverage: 45.3% (from satellite)                     │
│    - Gauge reading: 2.54 ft = Minor Flood                       │
│    - Conclusion: Flooding confirmed                             │
│                                                                 │
│    Returns: {                                                   │
│      "severity": "MINOR",                                       │
│      "confidence": "HIGH",                                      │
│      "reasoning": "Satellite and gauge agree"                   │
│    }                                                            │
│    Broadcast: tool_complete "Analysis complete"                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. ORCHESTRATOR SYNTHESIS                                       │
│    Combines DataCollection + FloodDetection results             │
│    Generates final response:                                    │
│    "Minor flooding detected in Cedar Key on Sept 27.            │
│     Satellite shows 45.3% water coverage. Gauge at Cedar Key    │
│     measured 2.54 ft (Minor Flood stage). High confidence."     │
│                                                                 │
│    Broadcast: agent_thought "Synthesizing final answer..."      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. OUTPUT PACKAGING                                             │
│    server/adk_wrapper.py scans outputs/ directory               │
│    Finds: outputs/20240927_HHMMSS/                              │
│      ├── original_viz.webp                                      │
│      ├── water_mask.webp                                        │
│      ├── overlay.webp                                           │
│      └── gauge_data.json                                        │
│                                                                 │
│    Broadcast: complete {                                        │
│      "images": ["/api/outputs/.../original_viz.webp", ...],     │
│      "gauges": [{"date": "2024-09-27", "data": {...}}]          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 9. FRONTEND DISPLAY                                             │
│    WebSocket receives "complete" event                          │
│                                                                 │
│    Chat Panel:                                                  │
│    - Shows final agent message                                  │
│    - "Send" button re-enabled                                   │
│                                                                 │
│    Image Gallery:                                               │
│    - Row 1 Left: original_viz.webp (RGB)                        │
│    - Row 1 Right: water_mask.webp (MASK)                        │
│    - Row 2: overlay.webp (OVERLAY)                              │
│                                                                 │
│    Gauge Chart:                                                 │
│    - Single data point plotted                                  │
│    - Minor flood threshold line shown                           │
└─────────────────────────────────────────────────────────────────┘
```

**Total Time**: ~45 seconds
- Geocoding: <1s
- Sentinel search: ~2s
- Prithvi segmentation: ~35s
- Gauge fetch: ~2s
- Agent reasoning: ~5s

---

## Key Insights

### Why This Architecture Works

1. **Multi-Agent = Modularity**
   - Easy to add new data sources (new MCP tools)
   - Easy to add new analysis methods (new agents)
   - Agents can be tested independently

2. **MCP = Security + Isolation**
   - Tools run in separate process
   - No direct code injection
   - Type-safe interfaces

3. **Prithvi AI = Accuracy**
   - Better than NDWI thresholding
   - Handles complex scenarios (urban, vegetation)
   - Trained on real flood events

4. **Gauge Validation = Confidence**
   - Ground truth confirmation
   - Reduces false positives
   - Temporal continuity (real-time updates)

5. **WebSocket = Real-Time UX**
   - No polling needed
   - Immediate feedback
   - Progress visibility builds trust

### Limitations & Future Work

**Current Limitations**:
- 5-day satellite revisit (not truly real-time)
- Cloud cover can block satellite view
- Prithvi processing is slow (~35s/image)
- Single-server deployment (no scaling)

**Future Enhancements**:
- Add Sentinel-1 SAR (all-weather imaging)
- Local Prithvi deployment (GPU server)
- Distributed task queue (Celery)
- Historical trend analysis
- Predictive modeling (flood forecasting)
