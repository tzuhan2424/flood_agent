# Flood Detection System - Architecture

## System Overview

Real-time flood detection using **Google ADK multi-agent framework**, **Sentinel-2 satellite imagery**, **Prithvi AI water segmentation**, and **NOAA/USGS NWPS gauge data**.

## Architecture Diagram

```
User Query (Natural Language)
        ↓
Web Frontend (HTML/CSS/JS + WebSocket)
        ↓
FastAPI Server (Python 3.14)
        ↓
Google ADK Multi-Agent System (Gemini 2.0 Flash)
    ├─ FloodAnalysisOrchestrator (Root Agent)
    ├─ DataCollectionAgent
    ├─ FloodDetectionAgent  
    └─ ImpactAssessmentAgent
        ↓ (via MCP Tools)
MCP Server (Model Context Protocol)
    ├─ Sentinel Hub API (Sentinel-2 imagery)
    ├─ Prithvi AI (IBM/NASA water segmentation)
    └─ NWPS API (NOAA/USGS gauge data)
```

## Core Components

### 1. Multi-Agent System (Google ADK)

**Orchestrator**: `FloodAnalysisOrchestrator`
- Routes queries to specialist agents based on intent
- Model: Gemini 2.0 Flash
- Tools: geocode_location + 3 agent tools

**Specialist Agents**:
- **DataCollectionAgent** - Fetches satellite imagery and gauge data via MCP
- **FloodDetectionAgent** - Performs change detection and statistical analysis
- **ImpactAssessmentAgent** - Estimates damage and suggests response

### 2. MCP Server (mcp_server/server.py)

**8 MCP Tools Exposed**:

**Satellite Imagery Tools**:
1. `search_sentinel_images()` - Search Sentinel Hub catalog
   - Smart sampling strategies (lowest_cloud, evenly_spaced, most_recent)
   - Returns image metadata and availability

2. `segment_flood_area()` - **Core flood detection tool**
   - Fetches Sentinel-2 **6-band imagery** (B02, B03, B04, B8A, B11, B12)
   - Sends to **Prithvi AI** (HuggingFace Spaces API)
   - Generates: RGB viz, water mask, overlay (WebP format)
   - Returns: Water coverage %, output paths

3. `get_time_series_water()` - Multi-date water analysis
   - Processes multiple dates in sequence
   - Computes statistics: mean, std dev, z-scores
   - Detects anomalies (outliers = flood events)

4. `fetch_sar_image()` - Sentinel-1 SAR (cloud-penetrating radar)

**NWPS Gauge Tools**:
5. `search_gauges()` - Find nearby NOAA/USGS gauges
6. `get_gauge_status()` - Current water levels + flood category
7. `get_gauge_timeseries()` - Historical readings

**Utility**:
8. `get_current_datetime()` - Server timestamp

### 3. Prithvi AI Water Segmentation

**Model**: IBM/NASA Prithvi-EO-2.0-Sen1Floods11 (HuggingFace Spaces)
- **Input**: Sentinel-2 6-band GeoTIFF (B02/B03/B04/B8A/B11/B12)
- **Output**: Binary water mask (0 = land, 1 = water)
- **Processing**: ~35 seconds per image
- **Accuracy**: Trained on Sen1Floods11 dataset

**Why 6 bands?**
- **B02 (Blue), B03 (Green), B04 (Red)**: RGB visualization
- **B8A (NIR)**: Water absorbs near-infrared → dark in water
- **B11/B12 (SWIR)**: Short-wave infrared → strong water detection

### 4. Sentinel-2 Satellite Data

**Provider**: Sentinel Hub (Copernicus)
- **Revisit time**: 5 days (with both satellites)
- **Resolution**: 10m (RGB), 20m (NIR/SWIR)
- **Coverage**: Global
- **API**: OAuth2 authentication → Process API

### 5. NWPS Gauge Data (NOAA/USGS)

**Data Source**: National Water Prediction Service
- **Coverage**: ~8,500 gauges across USA
- **Metrics**: Water level (ft), discharge (cfs), flood stage
- **Flood Categories**:
  - Normal → Action → Minor → Moderate → Major

**Purpose**: Ground truth validation of satellite-detected flooding

### 6. Web Frontend (frontend/)

**Technology**: Vanilla HTML/CSS/JavaScript (no frameworks)

**UI Layout**:
- **Left Panel (50%)**: Chat interface + agent activity tracker
- **Right Panel (50%)**: 
  - Images (2/3 height): Auto-cycling RGB/MASK/OVERLAY
  - Gauges (1/3 height): Line chart with flood thresholds

**Real-time Features**:
- WebSocket connection for agent events
- Auto-cycling images (2-second intervals)
- Progress bars for long operations
- Canvas-based line charts

### 7. FastAPI Backend (server/)

**Key Modules**:

**adk_wrapper.py** (Most Critical):
- Wraps ADK runner to capture events
- Parses: agent thoughts, tool calls, results
- Scans outputs/ for generated files
- Broadcasts via WebSocket

**Event Types**:
- `agent_thought` - Agent reasoning
- `tool_start/progress/complete` - Tool execution
- `image_ready` - New images available
- `gauge_data` - Gauge readings
- `complete` - Analysis done (with all output paths)

**websocket_manager.py**:
- Per-session WebSocket connections
- Broadcast messages to session clients

**session_manager.py**:
- ADK session lifecycle
- Maps frontend session IDs → ADK session IDs

## Data Flow Example

**Query**: "Show me flooding in Cedar Key on September 27, 2024"

```
1. User sends query → Frontend POST /api/chat/message
2. Backend creates async task → ADK Runner starts
3. Orchestrator processes:
   - Geocode "Cedar Key" → [-83.03, 29.13, -82.97, 29.19]
   - Route to DataCollectionAgent
4. DataCollectionAgent calls MCP tools:
   - search_sentinel_images(date="2024-09-27", bbox=...)
   - segment_flood_area(date="2024-09-27", location=...)
     → Fetch Sentinel-2 → Send to Prithvi → Generate masks
   - search_gauges(location="Cedar Key")
   - get_gauge_status(lid="CDRF1")
5. FloodDetectionAgent analyzes:
   - Water coverage: 45.3%
   - Gauge: 2.54 ft (Minor Flood)
6. Events broadcast via WebSocket:
   - Frontend updates: activity panel, images, chart
7. Final response: "Minor flooding detected..."
```

## Directory Structure

```
flood_agent/
├── agents/              # Multi-agent system
├── mcp_server/          # MCP tools (Sentinel, Prithvi, NWPS)
├── server/              # FastAPI backend
├── frontend/            # Web UI (HTML/CSS/JS)
├── outputs/             # Generated results
│   └── {run_id}/
│       └── {date}/
│           ├── original_viz.webp
│           ├── water_mask.webp
│           ├── overlay.webp
│           └── gauge_data.json
└── run.py               # CLI entry point
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK |
| AI Model | Gemini 2.0 Flash |
| Water Segmentation | Prithvi-EO-2.0 (HuggingFace) |
| Satellite Data | Sentinel Hub (Sentinel-2) |
| Gauge Data | NOAA/USGS NWPS |
| Backend | FastAPI + Python 3.14 |
| Frontend | Vanilla JS + WebSocket |
| Image Processing | HuggingFace Spaces API |

## Key Design Patterns

1. **AgentTool Pattern**: Agents wrapped as tools for dynamic routing
2. **Event-Driven**: ADK events → WebSocket → real-time UI updates  
3. **Session Isolation**: Per-user ADK sessions
4. **Progressive Enhancement**: Works without WebSocket (fallback to polling)
5. **Smart Sampling**: Time series auto-cycles to avoid UI overload
