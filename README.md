# Flood Detection AI System

Real-time flood detection using **satellite imagery**, **AI water segmentation**, and **ground sensor validation** in a conversational multi-agent interface.


![Flood Detection System Architecture](images/flood_arch.png)


## What This Does

Ask in natural language:
```
"Show me flooding in Cedar Key on September 27, 2024"
```

Get back:
- **Satellite imagery** (Sentinel-2)
- **AI-detected water masks** (Prithvi AI)
- **Gauge readings** (NOAA/USGS)
- **Statistical analysis** with confidence scores

## Quick Start

### 1. Prerequisites

- **Python 3.14+**
- **API Keys**:
  - [Sentinel Hub](https://www.sentinel-hub.com/) (OAuth credentials)
  - [Google AI Studio](https://aistudio.google.com/) (Gemini API key)

### 2. Installation

```bash
# Clone/navigate to flood_agent directory
cd flood_agent

# Install UV package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .
```

### 3. Configure Environment

Create `.env` file in `flood_agent/`:

```bash
# Sentinel Hub OAuth2 Credentials
SENTINEL_HUB_CLIENT_ID=your_client_id
SENTINEL_HUB_CLIENT_SECRET=your_client_secret

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key
```

**Get Credentials**:
- **Sentinel Hub**: Sign up at https://www.sentinel-hub.com/ → Dashboard → OAuth clients
- **Gemini**: Visit https://aistudio.google.com/apikey

### 4. Run the Application

**Option 1: Web Interface** (Recommended)

```bash
# Start the FastAPI server
python -m uvicorn server.main:app --host 127.0.0.1 --port 8766

# Open browser
http://127.0.0.1:8766
```

**Option 2: CLI**

```bash
# Interactive mode
adk run agents

# Direct query
adk run agents --prompt "Show me flooding in Cedar Key on Sept 27, 2024"
```

## Using the Web Interface

1. **Open browser**: http://127.0.0.1:8766
2. **Type a query** in the chat input:
   - "Show me flooding in Cedar Key on September 27, 2024"
   - "Analyze flooding from September 20-30, 2024 in Cedar Key"
   - "What was the impact of Hurricane Helene on Cedar Key?"
3. **Watch real-time updates**:
   - Agent activity panel shows progress
   - Images auto-populate when ready (auto-cycling through dates)
   - Gauge chart displays water levels over time

### UI Features

- **Chat Panel** (Left): Conversation with AI agents
- **Activity Panel**: Real-time agent reasoning and tool execution
- **Image Gallery** (Right, 2/3):
  - Row 1: RGB Original + Water Mask (side-by-side)
  - Row 2: Overlay (full-width)
  - Auto-cycles through dates every 2 seconds
- **Gauge Chart** (Right, 1/3): Line chart showing water levels with flood thresholds
- **Load Latest Button**: Test frontend with existing outputs (no agent run needed)

## Example Queries

### Single-Date Analysis
```
Show me flooding in Cedar Key, Florida on September 27, 2024
```
**Returns**: Images + gauge reading for one date (~45 seconds)

### Time Series Analysis
```
Analyze flooding in Cedar Key from September 20-30, 2024
```
**Returns**: Multi-date analysis with statistics (~3-5 minutes)

### Historical Research
```
Find all flooding events in Cedar Key during 2024
```
**Returns**: Year-long analysis with smart sampling (~10 minutes)

## System Architecture

This system combines:

- **Google ADK Multi-Agent Framework**
  - `FloodAnalysisOrchestrator` - Routes queries
  - `DataCollectionAgent` - Fetches satellite/gauge data
  - `FloodDetectionAgent` - Statistical analysis
  - `ImpactAssessmentAgent` - Damage assessment

- **MCP Server (8 Tools)**
  - `search_sentinel_images()` - Search Sentinel-2 catalog
  - `segment_flood_area()` - **Prithvi AI water segmentation**
  - `get_time_series_water()` - Multi-date analysis
  - `search_gauges()` - Find NOAA/USGS gauges
  - `get_gauge_status()` - Current water levels
  - And more...

- **Data Sources**
  - **Sentinel-2**: ESA satellite imagery (10m resolution, 5-day revisit)
  - **Prithvi AI**: IBM/NASA water segmentation model (HuggingFace)
  - **NWPS**: NOAA/USGS gauge network (8,500+ gauges)

- **Web Stack**
  - **Backend**: FastAPI + WebSocket (real-time updates)
  - **Frontend**: Vanilla HTML/CSS/JS (no frameworks)

## Output Files

All results saved to `outputs/{run_id}/{date}/`:

```
outputs/
└── timeseries_20240920_to_20240930_205617/
    ├── 20240922/
    │   ├── original_viz.webp    # RGB satellite image
    │   ├── water_mask.webp      # AI-detected water (blue)
    │   ├── overlay.webp         # Water overlay on RGB
    │   ├── sentinel_image.tif   # Raw 6-band GeoTIFF
    │   └── gauge_data.json      # NOAA gauge readings
    ├── 20240924/
    ├── 20240927/
    └── 20240929/
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent Framework** | Google ADK | Multi-agent orchestration |
| **AI Model** | Gemini 2.0 Flash | Agent reasoning |
| **Water Segmentation** | Prithvi-EO-2.0 (IBM/NASA) | AI water detection |
| **Satellite Data** | Sentinel-2 (Sentinel Hub) | 10m resolution imagery |
| **Gauge Data** | NOAA/USGS NWPS | Ground truth validation |
| **Backend** | FastAPI + Python 3.14 | REST API + WebSocket |
| **Frontend** | Vanilla JS | Real-time UI |
| **Image Processing** | HuggingFace Spaces | Prithvi AI inference |

## Documentation

For detailed information, see:

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, components, data flow
- **[EXPLANATION.md](EXPLANATION.md)** - How Sentinel-2, Prithvi AI, NWPS, and agents work
- **[DEMO.md](DEMO.md)** - Detailed usage guide, examples, troubleshooting

## Troubleshooting

### "No images found"
**Cause**: High cloud cover or no satellite pass
**Solution**: Try wider date range: `"Search Sept 20-30 with up to 30% clouds"`

### "Gauge not found"
**Cause**: No nearby NOAA/USGS gauge
**Solution**: Use satellite-only: `"Show satellite flooding in [location]"`

### WebSocket disconnects
**Cause**: Long processing time
**Solution**: Refresh page and click "Load Latest" button

### API rate limit
**Cause**: Sentinel Hub free tier limit
**Solution**: Wait 24 hours or upgrade to paid plan

## Performance

| Operation | Time |
|-----------|------|
| Single-date analysis | ~45 seconds |
| 10-day time series | ~6 minutes |

**Breakdown**:
- Geocoding: <1s
- Sentinel search: 2-3s
- **Prithvi AI segmentation: ~35s per image** (bottleneck)
- Gauge fetch: 1-2s
- Agent reasoning: 3-5s

## Project Structure

```
flood_agent/
├── agents/              # Multi-agent system (ADK)
│   ├── agent.py         # Orchestrator (root_agent)
│   ├── data_collection.py
│   ├── flood_detection.py
│   ├── impact_assessment.py
│   ├── geocoding.py
│   └── prompts.py
│
├── mcp_server/          # MCP tool server
│   ├── server.py        # 8 MCP tools
│   ├── sentinel.py      # Sentinel Hub client
│   ├── prithvi.py       # Prithvi AI client
│   ├── nwps.py          # NOAA gauge client
│   └── config.py
│
├── server/              # FastAPI backend
│   ├── main.py
│   ├── adk_wrapper.py   # Event capture + WebSocket broadcast
│   ├── websocket_manager.py
│   ├── session_manager.py
│   └── routers/
│       ├── chat.py
│       ├── outputs.py
│       └── websocket.py
│
├── frontend/            # Web UI
│   ├── index.html
│   ├── css/
│   └── js/
│
├── outputs/             # Generated results
├── run.py               # CLI entry point
├── pyproject.toml
├── .env                 # API credentials (create this)
└── README.md            # This file
```

## Development

### Test MCP Tools Directly

```python
# In Python shell
from mcp_server.server import search_sentinel_images

result = await search_sentinel_images(
    start_date="2024-09-27",
    end_date="2024-09-27",
    bbox=[-83.05, 29.12, -82.95, 29.18],
    max_cloud_cover=10.0
)

print(f"Found {result['total_found']} images")
```

### Run with Debug Logging

```bash
adk run agents --debug
```

### Test Frontend Without Agent

1. Run a query to generate outputs
2. Click "Load Latest" button (top-right of images section)
3. Frontend displays latest results instantly

## License

See LICENSE file for details.

## Resources

- [Google ADK Documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder)
- [Sentinel Hub API](https://docs.sentinel-hub.com/)
- [Prithvi Foundation Model](https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0)
- [NOAA NWPS API](https://api.water.noaa.gov/nwps/v1/docs/)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## Citation

If you use this system in research, please cite:
- **Prithvi Model**: IBM/NASA Prithvi-EO-2.0 (HuggingFace)
- **Sentinel-2**: ESA Copernicus Programme
- **NWPS Data**: NOAA/USGS National Water Prediction Service

---

**Built with**: Google ADK, Gemini 2.0, Prithvi AI, Sentinel-2, NOAA/USGS NWPS
