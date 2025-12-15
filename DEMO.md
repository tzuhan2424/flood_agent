# Flood Detection System - Demo Guide

## 📺 Video Demo

**Watch the full demo**: [https://youtu.be/aAE-llk9wU4](https://youtu.be/aAE-llk9wU4)

---

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

