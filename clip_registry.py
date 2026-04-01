"""Central registry for tracking which background clips have been used in uploaded videos."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = Path("results/used_clips.json")


def _parse_start_time(filename):
    """Extract start time integer from a clip filename, or None if not present."""
    match = re.search(r"start_time_(\d+)", str(filename))
    return int(match.group(1)) if match else None


def _save_registry(entries):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def load_registry():
    """Return all registry entries."""
    if not REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[registry] Warning: could not read {REGISTRY_PATH}: {e}")
        return []


def get_used_clips():
    """
    Return all registry entries (pending and uploaded).
    Used by clip_generator to skip clips already used in any composed video.
    """
    return load_registry()


def add_pending_entry(clip_path, result_video):
    """
    Record a composed video and the background clip it used, before upload.
    youtube fields are null until mark_uploaded() is called.
    """
    entries = load_registry()
    clip_name = Path(clip_path).name
    entries.append({
        "clip_name": clip_name,
        "clip_path": str(clip_path),
        "start_time": _parse_start_time(clip_name),
        "result_video": result_video,
        "youtube_id": None,
        "youtube_url": None,
        "uploaded_at": None,
    })
    _save_registry(entries)


def clean_registry():
    """
    Remove entries whose result_video no longer exists in results/ or results/uploaded/.
    Returns (kept, removed) lists of entries.
    Raises FileNotFoundError if the registry does not exist.
    """
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(REGISTRY_PATH)

    existing_videos = {p.name for p in Path("results").glob("*.mp4")}

    entries = load_registry()
    kept, removed = [], []
    for entry in entries:
        if entry.get("result_video") in existing_videos:
            kept.append(entry)
        else:
            removed.append(entry)

    _save_registry(kept)
    return kept, removed


def mark_uploaded(result_video, youtube_id, youtube_url):
    """
    Set youtube_id, youtube_url, and uploaded_at on the entry matching result_video.
    If no matching entry exists (e.g. legacy --upload mode), appends a minimal entry.
    """
    entries = load_registry()
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        if entry.get("result_video") == result_video:
            entry["youtube_id"] = youtube_id
            entry["youtube_url"] = youtube_url
            entry["uploaded_at"] = now
            _save_registry(entries)
            return
    # No pending entry found — add one without clip info
    entries.append({
        "clip_name": None,
        "clip_path": None,
        "start_time": None,
        "result_video": result_video,
        "youtube_id": youtube_id,
        "youtube_url": youtube_url,
        "uploaded_at": now,
    })
    _save_registry(entries)
