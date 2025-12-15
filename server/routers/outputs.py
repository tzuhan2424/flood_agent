"""Endpoints for serving output files"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import json

from ..config import settings

router = APIRouter(prefix="/api/outputs", tags=["outputs"])


@router.get("/{run_id}/images")
async def list_images(run_id: str):
    """List all images for a run"""
    run_dir = settings.outputs_dir / run_id
    if not run_dir.exists():
        raise HTTPException(404, f"Run not found: {run_id}")

    images = []
    
    # 1. Images in root directory
    for img in run_dir.glob("*.webp"):
        images.append({
            "filename": img.name,
            "type": "webp",
            "url": f"/api/outputs/{run_id}/image/{img.name}"
        })
    for img in run_dir.glob("*.tif"):
        images.append({
            "filename": img.name,
            "type": "tif",
            "url": f"/api/outputs/{run_id}/image/{img.name}"
        })

    # 2. Images in subdirectories (time series)
    for subdir in run_dir.iterdir():
        if subdir.is_dir():
            # Add date prefix to filename for clarity in UI
            prefix = subdir.name

            for img in subdir.glob("*.webp"):
                images.append({
                    "filename": f"{prefix}_{img.name}", # e.g. 20240901_water_mask.webp
                    "type": "webp",
                    "url": f"/api/outputs/{run_id}/{subdir.name}/{img.name}"
                })

            for img in subdir.glob("*.tif"):
                images.append({
                    "filename": f"{prefix}_{img.name}",
                    "type": "tif",
                    "url": f"/api/outputs/{run_id}/{subdir.name}/{img.name}"
                })

    return {"run_id": run_id, "images": images}


@router.get("/{run_id}/image/{filename}")
async def get_image(run_id: str, filename: str):
    """Serve an image file (handles both direct and nested paths)"""
    # Try direct path first
    file_path = settings.outputs_dir / run_id / filename
    if file_path.exists():
        return FileResponse(file_path)

    # For time series, check subdirectories
    run_dir = settings.outputs_dir / run_id
    if run_dir.exists() and run_dir.is_dir():
        for subdir in run_dir.iterdir():
            if subdir.is_dir():
                nested_path = subdir / filename
                if nested_path.exists():
                    return FileResponse(nested_path)

    raise HTTPException(404, f"Image not found: {filename}")


@router.get("/{run_id}/{subdir}/{filename}")
async def get_nested_file(run_id: str, subdir: str, filename: str):
    """Serve a file from nested directory structure"""
    file_path = settings.outputs_dir / run_id / subdir / filename
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {run_id}/{subdir}/{filename}")

    return FileResponse(file_path)


@router.get("/{run_id}/gauges")
async def get_gauge_data(run_id: str):
    """Get gauge data for a run"""
    gauge_file = settings.outputs_dir / run_id / "gauge_data.json"
    if not gauge_file.exists():
        raise HTTPException(404, f"Gauge data not found for run: {run_id}")

    try:
        with open(gauge_file) as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(500, f"Error reading gauge data: {str(e)}")


@router.get("/runs")
async def list_runs():
    """List all available runs"""
    if not settings.outputs_dir.exists():
        return {"runs": []}

    runs = []
    for run_dir in settings.outputs_dir.iterdir():
        if run_dir.is_dir():
            # Check if it has any output files
            has_images = any(run_dir.glob("*.webp")) or any(run_dir.glob("*.tif"))
            has_gauges = (run_dir / "gauge_data.json").exists()

            if has_images or has_gauges:
                runs.append({
                    "run_id": run_dir.name,
                    "created": run_dir.stat().st_ctime,
                    "has_images": has_images,
                    "has_gauges": has_gauges
                })

    return {"runs": sorted(runs, key=lambda x: x['created'], reverse=True)}


@router.get("/latest")
async def get_latest_outputs():
    """Get the most recent run's outputs (for testing frontend)"""
    if not settings.outputs_dir.exists():
        return {"images": [], "gauges": []}

    # Find most recently modified directory
    run_dirs = [d for d in settings.outputs_dir.iterdir() if d.is_dir()]
    if not run_dirs:
        return {"images": [], "gauges": []}

    latest_run = sorted(run_dirs, key=lambda d: d.stat().st_mtime, reverse=True)[0]
    run_id = latest_run.name

    images = []
    gauges = []

    # Check for subdirectories (time-series case)
    subdirs = [d for d in latest_run.iterdir() if d.is_dir()]
    if subdirs:
        for subdir in subdirs:
            # Find images (only WEBP, exclude TIF)
            for img in subdir.glob("*.webp"):
                images.append(f"/api/outputs/{run_id}/{subdir.name}/{img.name}")

            # Find gauge data
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
                    print(f"Error reading gauge data from {subdir.name}: {e}")
    else:
        # No subdirectories, check main directory (only WEBP)
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
                print(f"Error reading gauge data: {e}")

    return {
        "run_id": run_id,
        "images": images,
        "gauges": gauges
    }
