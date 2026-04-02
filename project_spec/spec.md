### Direct Requests

## Q&A — Clip Registry Consolidation (2026-03-31)

**Q1: Where should the single consolidated JSON file live?**
A: `results/used_clips.json` — inside the results folder, alongside the output videos.

**Q2: Should individual sidecar `.json` files still be created alongside each result `.mp4`, or should `results/used_clips.json` be the only place clip usage is recorded?**
A: Eliminate sidecars entirely. `results/used_clips.json` is the only place clip usage is recorded.

**Q3: Should `results/used_clips.json` also store the YouTube video ID / URL for each entry?**
A: Yes — store `youtube_id`, `youtube_url`, and `uploaded_at` timestamp per entry for full traceability.

**Q4: After migrating existing sidecar JSONs from `results/uploaded/` into the new registry, what should happen to the old `.json` files?**
A: Delete them. The central registry is the single source of truth.

**Q5: Existing uploaded videos have no YouTube URL recorded. How should missing YouTube fields be handled during migration?**
A: Leave them `null` — `"youtube_id": null, "youtube_url": null`. Honest about what we don't know.

**Q6: Should `results/used_clips.json` also store the result video filename (e.g. `result_20260330_221446.mp4`) per entry?**
A: Yes — adds full traceability: clip → result video → YouTube Short.

**Q7: Should deduplication match clips by filename OR start time, or tighten the logic?**
A: Keep both checks — guard against renamed clips with the same start time.

**Q8: Should migration run automatically at startup, or as a separate one-off script?**
A: Auto-migrate at startup — first run detects old sidecars, absorbs them, and deletes them seamlessly.

---

## Summary of Changes — Clip Registry Consolidation (2026-03-31)

### New file: `clip_registry.py`
Central module owning all registry read/write logic.

- `REGISTRY_PATH = Path("results/used_clips.json")` — single array JSON file tracking all clip usage
- `_parse_start_time(filename)` — extracts `start_time_NNN` from a clip filename (moved from `clip_generator.py`)
- `_auto_migrate()` — one-time migration that runs when the registry file does not yet exist: scans `results/uploaded/*.json` sidecars, builds registry entries (with `uploaded_at` set to each sidecar's file modification time as a proxy for upload time, and `youtube_id`/`youtube_url` set to `null`), writes `results/used_clips.json`, then deletes the sidecar files
- `load_registry()` — calls `_auto_migrate()` then reads and returns the full array
- `_save_registry(entries)` — writes the array back to disk
- `get_used_clips()` — returns only entries where `uploaded_at` is not `null` (i.e. actually uploaded); used by `clip_generator.py` for deduplication
- `add_pending_entry(clip_path, result_video)` — called at compose time; appends an entry with `clip_name`, `clip_path`, `start_time`, `result_video` set, and all YouTube fields `null`
- `mark_uploaded(result_video, youtube_id, youtube_url)` — called after upload; finds the entry by `result_video` and sets `youtube_id`, `youtube_url`, `uploaded_at`; if no entry exists (legacy `--upload` mode for old videos), appends a minimal entry with clip fields `null`

### Each registry entry schema
```json
{
  "clip_name": "saved_clip_20260324_222315_start_time_2321.mp4",
  "clip_path": "background_videos/minecraft_parkour/clips/saved_clip_20260324_222315_start_time_2321.mp4",
  "start_time": 2321,
  "result_video": "result_20260330_221446.mp4",
  "youtube_id": "dQw4w9WgXcQ",
  "youtube_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
  "uploaded_at": "2026-03-30T21:14:01+00:00"
}
```

### `clip_generator.py`
- Removed `import json`, `UPLOADED_DIR`, `_parse_start_time()`, and the old `_get_used_clips()` body (which scanned `results/uploaded/*.json`)
- Added `from clip_registry import get_used_clips, _parse_start_time`
- `_get_used_clips()` is now a one-liner delegating to `get_used_clips()`
- Fixed console logging in `generate_clip()` that referenced the now-removed `u['sidecar']` field

### `video_composer.py`
- Removed `import json` and `import re` (no longer needed)
- Added `from clip_registry import add_pending_entry`
- Removed the 9-line block that wrote a sidecar `.json` alongside each result `.mp4`
- Replaced it with a single call: `add_pending_entry(clip_path, output_path.name)`

### `youtube_uploader.py`
- Added `from clip_registry import mark_uploaded`
- After a successful upload, calls `mark_uploaded(video_path.name, video_id, url)` to update the registry with YouTube metadata
- Removed the sidecar `.json` move logic (checking for `video_path.with_suffix(".json")` and moving it to `uploaded/`)
- The result `.mp4` is still moved to `results/uploaded/` as before



------------------------------------------------------------------------------------------------------------



## Q&A — Registry Cleanup: Remove _auto_migrate (2026-03-31)

**Q1: `_auto_migrate()` only ever runs once — should we run it now and remove it to clean up the code?**
A: Yes — run it now, then delete it.

**Q2: Should the migration be triggered by running it directly (via a Python command), or should the user run it first to review the output?**
A: Run it now — trigger it directly.

**Q3: The uploaded videos in `results/uploaded/` had no sidecar JSONs (they predate the sidecar system). What should be seeded into `results/used_clips.json`?**
A: Option A — create entries for the 6 uploaded videos with all clip fields `null`, plus pending entries for the 2 unuploaded results from their existing sidecars.

**Q4: For the 6 uploaded videos with no sidecar data, what should `uploaded_at` be set to?**
A: File modification time of the `.mp4` — best proxy for when they were uploaded, and required for `get_used_clips()` to include them (it filters on `uploaded_at != null`).

---

## Summary of Changes — Registry Cleanup: Remove _auto_migrate (2026-03-31)

### `results/used_clips.json` — seeded via one-off script
- 6 entries for already-uploaded videos (`results/uploaded/*.mp4`): all clip fields `null`, `uploaded_at` set from `.mp4` file modification time, `youtube_id`/`youtube_url` `null`
- 2 pending entries reconstructed from the existing sidecar JSONs in `results/`: `clip_name`, `clip_path`, `start_time` populated from the sidecars; all YouTube fields and `uploaded_at` `null`
- The 2 sidecar JSONs (`result_20260330_221446.json`, `result_20260330_221731.json`) were deleted after seeding

### `clip_registry.py`
- Removed `_auto_migrate()` entirely — migration was run once manually and is no longer needed
- Removed `_UPLOADED_DIR` constant (only used by `_auto_migrate`)
- Simplified `load_registry()` — no longer calls `_auto_migrate()` before reading; now just reads and returns the file



------------------------------------------------------------------------------------------------------------



## Q&A — Extend deduplication to pending results (2026-03-31)

**Q1: `result_20260330_215822.mp4` is in `results/` but has no clip info. Should it be added as a null-clip pending entry?**
A: Skip it — no clip info means no deduplication value; adding it is noise.

**Q2: Should `get_used_clips()` return all entries (pending + uploaded) so any composed video blocks its clip from reuse?**
A: Yes — return all entries. Any composed video blocks its clip whether uploaded or not.

**Q3: The console prints `"Uploaded clip history (N record(s)):"` when listing tracked clips — should it be updated since we now include pending entries too?**
A: Remove the log entirely.

---

## Summary of Changes — Extend deduplication to pending results (2026-03-31)

### `clip_registry.py`
- `get_used_clips()` now returns `load_registry()` directly — no longer filters to `uploaded_at is not None`; all entries (pending and uploaded) are considered used for deduplication

### `clip_generator.py`
- Removed the "Uploaded clip history" log block (6 lines) that printed each tracked clip to console
- Removed the `# Log uploaded clip history` comment
- Updated the fallback message from `"All cached clips have already been used in uploaded videos"` to `"All cached clips have already been used"` to reflect that pending results also count



------------------------------------------------------------------------------------------------------------



## Q&A — --clean-up flag (2026-03-31)

**Q1: Uploaded videos are in `results/uploaded/`, not `results/` — should `--clean-up` also check `results/uploaded/` to avoid removing their entries?**
A: Check both folders — keep entries for any video in `results/` or `results/uploaded/`; only remove truly orphaned entries.

**Q2: Should `--clean-up` print a summary of what it removed and kept?**
A: Always print a full summary, even if nothing was removed.

**Q3: If `results/used_clips.json` doesn't exist when `--clean-up` is run, should it exit with a message or create an empty registry?**
A: Exit with a message — `"No registry found — nothing to clean up."`

---

## Summary of Changes — --clean-up flag (2026-03-31)

### `clip_registry.py`
- Added `clean_registry()` — scans `results/*.mp4` and `results/uploaded/*.mp4` to build a set of known video filenames; splits registry entries into `kept` (result_video exists on disk) and `removed` (result_video not found in either folder); saves the filtered list and returns `(kept, removed)` for the caller to print; raises `FileNotFoundError` if the registry does not exist

### `main.py`
- Added `from clip_registry import clean_registry` import
- Added `--clean-up` to the mutually exclusive mode argument group
- Added handler for `args.clean_up`: calls `clean_registry()`, catches `FileNotFoundError` to print the "no registry" message, then prints removed entries and kept entries (with `[pending]` / `[uploaded]` status labels) before returning



------------------------------------------------------------------------------------------------------------



## Q&A — --clean-up-tts flag (2026-04-01)

**Q1: If a phrase already exists in `converted_phrases.json`, should it be added again or skipped?**
A: Skip duplicates — `converted_phrases.json` is a deduplicated set. A phrase already there is not added again, but is still removed from `phrasesPath` if it has been cached.

**Q2: Should `--clean-up-tts` print a full summary of moved phrases or just a count?**
A: Count only — print moved count and remaining count.

---

## Summary of Changes — --clean-up-tts flag (2026-04-01)

### `main.py`
- Added `import json`
- Added `_run_clean_up_tts(config)` function:
  - Reads `phrasesPath` JSON array
  - Scans `saved_elevenlabs_tts/tts_elevenlabs_*/*.json` files in the phrases parent dir; builds a set of cached phrase texts using each file's `"text"` field
  - Loads `converted_phrases.json` from the phrases parent dir if it exists (empty list otherwise)
  - For each phrase in `phrasesPath`: if cached and not already in `converted_phrases.json`, appends it; if cached regardless of duplicate, removes it from `phrasesPath`; if not cached, keeps it in `phrasesPath`
  - Writes updated `phrasesPath` and `converted_phrases.json` back to disk
  - Prints moved count and remaining count
- Added `--clean-up-tts` to the mutually exclusive mode argument group
- Added handler for `args.clean_up_tts`: loads config, calls `_run_clean_up_tts(config)`, returns
- Updated `--clean-up` help text to reflect current behavior (disk cleanup, registry kept intact)
