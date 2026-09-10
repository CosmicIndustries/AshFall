#!/usr/bin/env python3
"""AshFall perception engine: turn system and visual inputs into shared evidence.

AshFall observes. Downstream agents interpret. No agent-specific policy or
mutation is performed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

from ashfall_store import DEFAULT_STORE, append_evidence

try:
    import psutil
except ImportError:  # optional; /proc telemetry still works on Linux
    psutil = None


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def _cpu_load() -> dict[str, float]:
    if psutil is not None:
        return {"load1": float(psutil.getloadavg()[0]), "load5": float(psutil.getloadavg()[1]), "load15": float(psutil.getloadavg()[2])}
    raw = _read_text("/proc/loadavg")
    if raw:
        p = raw.split()
        return {"load1": float(p[0]), "load5": float(p[1]), "load15": float(p[2])}
    return {}


def _memory() -> dict[str, int]:
    if psutil is not None:
        m = psutil.virtual_memory()
        s = psutil.swap_memory()
        return {"ram_total": int(m.total), "ram_used": int(m.used), "ram_available": int(m.available), "swap_total": int(s.total), "swap_used": int(s.used)}
    data: dict[str, int] = {}
    raw = _read_text("/proc/meminfo") or ""
    for line in raw.splitlines():
        k, _, v = line.partition(":")
        if k in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            data[k] = int(v.strip().split()[0]) * 1024
    if data:
        data["ram_used"] = data.get("MemTotal", 0) - data.get("MemAvailable", 0)
        data["swap_used"] = data.get("SwapTotal", 0) - data.get("SwapFree", 0)
    return data


def _thermals() -> list[dict[str, Any]]:
    zones = []
    root = Path("/sys/class/thermal")
    for zone in sorted(root.glob("thermal_zone*")):
        temp = _read_text(str(zone / "temp"))
        if temp is None:
            continue
        try:
            value = int(temp.strip()) / 1000.0
        except ValueError:
            continue
        zones.append({"zone": zone.name, "type": (_read_text(str(zone / "type")) or zone.name).strip(), "celsius": value})
    return zones


def system_observation() -> dict[str, Any]:
    """Collect a safe, read-only system perception frame."""
    obs: dict[str, Any] = {
        "schema": "ashfall.perception.system.v1",
        "observed_at": time.time(),
        "host": {
            "hostname": platform.node(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "cpu": _cpu_load(),
        "memory": _memory(),
        "thermal": _thermals(),
    }
    if psutil is not None:
        obs["process"] = {"count": len(psutil.pids()), "cpu_percent": psutil.cpu_percent(interval=0.2)}
        try:
            obs["network"] = {name: {"is_up": bool(stats.isup), "speed_mbps": int(stats.speed or 0)} for name, stats in psutil.net_if_stats().items()}
        except Exception:
            obs["network"] = {}
    return obs


def image_observation(path: str | Path) -> dict[str, Any]:
    """Extract deterministic visual features from an image without inference."""
    p = Path(path).expanduser().resolve()
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image perception; install requirements.txt") from exc

    with Image.open(p) as im:
        rgb = im.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(rgb)
        gstat = ImageStat.Stat(gray)
        edge = gray.filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edge).mean[0]
        return {
            "schema": "ashfall.perception.vision.v1",
            "observed_at": time.time(),
            "source": {"path": str(p), "sha256": digest, "format": im.format, "mode": im.mode},
            "image": {"width": im.width, "height": im.height, "channels": 3, "aspect_ratio": round(im.width / im.height, 6) if im.height else None},
            "features": {
                "mean_rgb": [round(x, 3) for x in stat.mean],
                "stddev_rgb": [round(x, 3) for x in stat.stddev],
                "luminance_mean": round(gstat.mean[0], 3),
                "luminance_stddev": round(gstat.stddev[0], 3),
                "edge_density_proxy": round(edge_mean / 255.0, 6),
            },
        }


def publish(kind: str, observation: dict[str, Any], source: str = "ashfall") -> str:
    """Publish one observation into the canonical shared evidence store."""
    event = {
        "kind": "observation",
        "source": source,
        "producer": "ashfall",
        "visibility": "shared",
        "audience": ["jarvis", "aaron", "george", "leeloo"],
        "observation_kind": kind,
        "observation": observation,
    }
    return append_evidence(event)


def observe_system_and_publish() -> tuple[str, dict[str, Any]]:
    obs = system_observation()
    return publish("system", obs), obs


def observe_image_and_publish(path: str | Path) -> tuple[str, dict[str, Any]]:
    obs = image_observation(path)
    return publish("vision", obs), obs


def tool_metadata() -> dict[str, Any]:
    return {
        "schema": "ashfall.tool.v1",
        "name": "ashfall",
        "role": "perception",
        "store": str(DEFAULT_STORE),
        "capabilities": ["system_observation", "thermal_observation", "network_presence", "vision_feature_extraction", "shared_evidence_publish"],
        "policy": {"mutates_host": False, "interprets_for_agents": False, "autonomous_control": False},
    }


if __name__ == "__main__":
    print(json.dumps(tool_metadata(), indent=2))
