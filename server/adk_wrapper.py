"""Wrapper around ADK Runner to capture and broadcast agent events"""
import asyncio
import json
from typing import AsyncIterator
from pathlib import Path
from datetime import datetime
from google.adk.runners import Runner
from google.genai import types

from .websocket_manager import WebSocketManager
from .models import AgentThought, ToolExecution, DataUpdate


class ADKEventCapture:
    """
    Captures ADK runner events and broadcasts them to WebSocket clients.

    Monitors:
    - Agent thoughts (content.parts with agent reasoning)
    - Tool calls (function calls in events)
    - Output files (new images/gauge data in outputs/)
    - Progress estimation for long operations
    """

    def __init__(self, ws_manager: WebSocketManager, outputs_dir: Path):
        self.ws_manager = ws_manager
        self.outputs_dir = outputs_dir
        self._active_tools: dict[str, datetime] = {}
        self._progress_tasks: dict[str, asyncio.Task] = {}

    async def run_agent(
        self,
        runner: Runner,
        session_id: str,
        user_id: str,
        message: str,
        ws_session_id: str = None
    ):
        """
        Run agent and broadcast events via WebSocket.

        Events are broadcast directly to WebSocket clients.

        Args:
            session_id: ADK session ID for runner
            ws_session_id: WebSocket session ID for broadcasting (if different from session_id)
        """
        # Use WebSocket session ID for broadcasting if provided
        broadcast_session_id = ws_session_id or session_id

        print(f"[ADK Wrapper] Starting run_agent for ADK session {session_id}")
        print(f"[ADK Wrapper] Broadcasting to WebSocket session {broadcast_session_id}")
        print(f"[ADK Wrapper] Message: {message}")

        content = types.Content(role="user", parts=[types.Part(text=message)])

        current_agent = None
        current_tool = None
        current_run_id = None

        try:
            async for event in runner.run_async(
                session_id=session_id,
                user_id=user_id,
                new_message=content
            ):
                # Debug: print event type
                print(f"[ADK Event] Type: {type(event)}, Has author: {hasattr(event, 'author')}, Has content: {hasattr(event, 'content')}")

                event_data = None

                # Agent detection from author
                if hasattr(event, 'author') and event.author:
                    agent_name = event.author
                    print(f"[ADK Event] Agent: {agent_name}")
                    if agent_name != current_agent:
                        current_agent = agent_name
                        event_data = AgentThought(
                            timestamp=datetime.utcnow(),
                            agent_name=agent_name,
                            thought=f"{agent_name} is analyzing..."
                        ).model_dump(mode='json')
                        print(f"[Broadcast] Broadcasting agent_thought for {agent_name}")
                        await self.ws_manager.broadcast(broadcast_session_id, event_data)

                # Content extraction
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        print(f"[ADK Event] Part type: {type(part)}, has text: {hasattr(part, 'text')}, has function_call: {hasattr(part, 'function_call')}")

                        # Text content (agent responses)
                        if hasattr(part, 'text') and part.text:
                            print(f"[ADK Event] Text content: {part.text[:100]}...")
                            event_data = AgentThought(
                                timestamp=datetime.utcnow(),
                                agent_name=current_agent or "Agent",
                                thought=part.text
                            ).model_dump(mode='json')
                            print(f"[Broadcast] Broadcasting agent text")
                            await self.ws_manager.broadcast(broadcast_session_id, event_data)

                        # Function call detection (tool start)
                        if hasattr(part, 'function_call'):
                            func_call = part.function_call
                            tool_name = func_call.name if hasattr(func_call, 'name') else "unknown_tool"

                            # Extract arguments to detect run_id
                            if hasattr(func_call, 'args'):
                                args = func_call.args
                                # Try to extract location or parent_dir for run_id
                                if 'location' in args:
                                    # Generate a timestamp-based run_id
                                    current_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

                            # Mark tool as active
                            current_tool = tool_name
                            self._active_tools[tool_name] = datetime.utcnow()

                            event_data = ToolExecution(
                                type="tool_start",
                                timestamp=datetime.utcnow(),
                                tool_name=tool_name,
                                status=f"Starting {tool_name}...",
                                progress=0
                            ).model_dump(mode='json')
                            await self.ws_manager.broadcast(broadcast_session_id, event_data)

                            # Start progress monitoring for long operations
                            if tool_name in ["segment_flood_area", "get_time_series_water"]:
                                task = asyncio.create_task(
                                    self._monitor_tool_progress(broadcast_session_id, tool_name, current_run_id)
                                )
                                self._progress_tasks[tool_name] = task

                        # Function response detection (tool complete)
                        if hasattr(part, 'function_response'):
                            func_resp = part.function_response
                            tool_name = func_resp.name if hasattr(func_resp, 'name') else current_tool

                            # Parse response
                            result = None
                            if hasattr(func_resp, 'response'):
                                result = func_resp.response
                                print(f"[Tool Result] Tool: {tool_name}, Result type: {type(result)}")
                                print(f"[Tool Result] Result: {result}")

                                # Extract run_id from result if available
                                if isinstance(result, dict):
                                    print(f"[Tool Result] Result keys: {result.keys()}")
                                    if 'run_id' in result:
                                        current_run_id = result['run_id']
                                        print(f"[Tool Result] Extracted run_id: {current_run_id}")
                                    elif 'parent_dir' in result:
                                        current_run_id = result['parent_dir']
                                        print(f"[Tool Result] Extracted parent_dir as run_id: {current_run_id}")
                                    else:
                                        print(f"[Tool Result] No run_id or parent_dir found in result")
                                else:
                                    print(f"[Tool Result] Result is not a dict, cannot extract run_id")

                            # Cancel progress monitoring
                            if tool_name in self._progress_tasks:
                                self._progress_tasks[tool_name].cancel()
                                del self._progress_tasks[tool_name]

                            # Mark tool as complete
                            if tool_name in self._active_tools:
                                del self._active_tools[tool_name]

                            event_data = ToolExecution(
                                type="tool_complete",
                                timestamp=datetime.utcnow(),
                                tool_name=tool_name,
                                status=f"Completed {tool_name}",
                                progress=100,
                                result=result
                            ).model_dump(mode='json')
                            await self.ws_manager.broadcast(broadcast_session_id, event_data)

                            # Check for new outputs
                            if current_run_id:
                                print(f"[Output Check] Checking outputs for run_id: {current_run_id}")
                                await self._check_new_outputs(broadcast_session_id, current_run_id)
                            else:
                                print(f"[Output Check] No run_id available, skipping output check")

            # Find latest outputs and send completion event with paths
            latest_data = await self._get_latest_outputs()

            await self.ws_manager.broadcast(broadcast_session_id, {
                "type": "complete",
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": broadcast_session_id,
                "final_message": "Analysis complete!",
                "data": latest_data  # Include images and gauge paths
            })

        except Exception as e:
            # Send error event
            await self.ws_manager.broadcast(broadcast_session_id, {
                "type": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": broadcast_session_id,
                "error": str(e)
            })
            raise

    async def _monitor_tool_progress(self, session_id: str, tool_name: str, run_id: str = None):
        """
        Simulate progress for long-running tools.

        segment_flood_area takes ~35 seconds:
        - 0-5s: Fetching Sentinel imagery (20%)
        - 5-30s: Running Prithvi segmentation (80%)
        - 30-35s: Saving outputs (100%)
        """
        try:
            if tool_name == "segment_flood_area":
                stages = [
                    (3, 20, "Searching for Sentinel-2 imagery..."),
                    (8, 40, "Downloading satellite data..."),
                    (15, 60, "Running Prithvi water segmentation..."),
                    (10, 85, "Analyzing water coverage..."),
                    (5, 95, "Saving results..."),
                ]
            elif tool_name == "get_time_series_water":
                stages = [
                    (5, 25, "Searching for time series images..."),
                    (15, 50, "Processing multiple dates..."),
                    (15, 75, "Computing statistics..."),
                    (10, 95, "Generating outputs..."),
                ]
            else:
                return

            for delay, progress, message in stages:
                if tool_name not in self._active_tools:
                    break  # Tool completed

                await asyncio.sleep(delay)

                event = ToolExecution(
                    type="tool_progress",
                    timestamp=datetime.utcnow(),
                    tool_name=tool_name,
                    status=message,
                    progress=progress
                ).model_dump(mode='json')

                await self.ws_manager.broadcast(session_id, event)

        except asyncio.CancelledError:
            # Task was cancelled (tool completed)
            pass

    async def _check_new_outputs(self, session_id: str, run_id: str):
        """
        Check for new output files and broadcast data updates.
        """
        print(f"[Output Check] _check_new_outputs called with run_id: {run_id}")
        if not run_id:
            print(f"[Output Check] No run_id provided, returning")
            return

        # Check the main directory
        run_dir = self.outputs_dir / run_id
        print(f"[Output Check] Checking directory: {run_dir}")

        if not run_dir.exists():
            print(f"[Output Check] Directory does not exist: {run_dir}")
            return

        # For time series, check subdirectories (analysis dates)
        subdirs = [d for d in run_dir.iterdir() if d.is_dir()]
        if subdirs:
            print(f"[Output Check] Found {len(subdirs)} subdirectories, checking each...")
            for subdir in subdirs:
                await self._check_directory_for_outputs(session_id, run_id, subdir)
        else:
            # No subdirectories, check this directory directly
            await self._check_directory_for_outputs(session_id, run_id, run_dir)

    async def _check_directory_for_outputs(self, session_id: str, run_id: str, directory: Path):
        """Check a specific directory for output files and broadcast."""
        print(f"[Output Check] Checking directory for files: {directory}")

        # Check for images
        images = list(directory.glob("*.webp")) + list(directory.glob("*.tif"))
        if images:
            print(f"[Output Check] Found {len(images)} images: {[img.name for img in images]}")
            event = DataUpdate(
                type="image_ready",
                timestamp=datetime.utcnow(),
                run_id=run_id,  # Use main run_id
                data={
                    "images": [f"/api/outputs/{run_id}/{directory.name}/{img.name}" for img in images],
                    "count": len(images)
                }
            ).model_dump(mode='json')
            print(f"[Output Check] Broadcasting image_ready event")
            await self.ws_manager.broadcast(session_id, event)

        # Check for gauge data
        gauge_file = directory / "gauge_data.json"
        if gauge_file.exists():
            print(f"[Output Check] Found gauge_data.json")
            try:
                with open(gauge_file) as f:
                    gauge_data = json.load(f)

                event = DataUpdate(
                    type="gauge_data",
                    timestamp=datetime.utcnow(),
                    run_id=run_id,  # Use main run_id
                    data=gauge_data
                ).model_dump(mode='json')
                print(f"[Output Check] Broadcasting gauge_data event")
                await self.ws_manager.broadcast(session_id, event)
            except Exception as e:
                print(f"[Output Check] Error reading gauge data: {e}")

    async def _get_latest_outputs(self):
        """
        Scan outputs directory for the most recent run and return all images/gauge data.

        Returns:
            dict with 'images' (list of paths) and 'gauges' (list of gauge data)
        """
        print(f"[Latest Outputs] Scanning outputs directory: {self.outputs_dir}")

        if not self.outputs_dir.exists():
            print(f"[Latest Outputs] Outputs directory does not exist")
            return {"images": [], "gauges": []}

        # Find the most recently modified directory
        run_dirs = [d for d in self.outputs_dir.iterdir() if d.is_dir()]
        if not run_dirs:
            print(f"[Latest Outputs] No run directories found")
            return {"images": [], "gauges": []}

        # Sort by modification time, most recent first
        latest_run = sorted(run_dirs, key=lambda d: d.stat().st_mtime, reverse=True)[0]
        run_id = latest_run.name

        print(f"[Latest Outputs] Found latest run: {run_id}")

        images = []
        gauges = []

        # Check for subdirectories (time-series case)
        subdirs = [d for d in latest_run.iterdir() if d.is_dir()]
        if subdirs:
            print(f"[Latest Outputs] Found {len(subdirs)} subdirectories (time-series)")
            for subdir in subdirs:
                # Find images in subdirectory (only WEBP, exclude TIF)
                for img in subdir.glob("*.webp"):
                    images.append(f"/api/outputs/{run_id}/{subdir.name}/{img.name}")

                # Find gauge data in subdirectory
                gauge_file = subdir / "gauge_data.json"
                if gauge_file.exists():
                    try:
                        with open(gauge_file) as f:
                            gauge_data = json.load(f)
                            gauges.append({
                                "date": subdir.name,
                                "data": gauge_data
                            })
                    except Exception as e:
                        print(f"[Latest Outputs] Error reading gauge data from {subdir.name}: {e}")
        else:
            # No subdirectories, check main directory (only WEBP)
            print(f"[Latest Outputs] No subdirectories, checking main directory")
            for img in latest_run.glob("*.webp"):
                images.append(f"/api/outputs/{run_id}/image/{img.name}")

            gauge_file = latest_run / "gauge_data.json"
            if gauge_file.exists():
                try:
                    with open(gauge_file) as f:
                        gauge_data = json.load(f)
                        gauges.append({
                            "date": "latest",
                            "data": gauge_data
                        })
                except Exception as e:
                    print(f"[Latest Outputs] Error reading gauge data: {e}")

        print(f"[Latest Outputs] Found {len(images)} images, {len(gauges)} gauge datasets")

        return {
            "run_id": run_id,
            "images": images,
            "gauges": gauges
        }
