make the following updates:

- add config value called 'saveResult' to the 'output'. 
- when this is True it should save the final video under '/result/saved'. 
  - create '/saved' dir if it does not exist. 
- the saved file name should be the 'result_video' that is saved in the 'used_clips.json'
- update '--clean-up' flag to check '/results/saved' not '/results/uploads'
- '--clean-up' should also litterate over for every 'clip_name' in 'used_clips.json' delete it using the 'clip_path'

---

## Q&A — spec_twelve.md 

**Q1: When `saveResult` is `true`, should the video be copied or moved to `results/saved/`?**
A: Copy — and only when the video is actually being uploaded (`shouldUpload: true` or `--upload`). Since the file is deleted post-upload anyway, the net result is the file ends up only in `results/saved/`.

**Q2: Should `--clean-up` delete clip files for all registry entries, or only entries being removed?**
A: All entries — delete every `clip_path` file and every `result_video` file in `results/` and `results/saved/` referenced by any entry in the registry.

**Q3: After `--clean-up` deletes files, should the registry be cleared or trimmed?**
A: Keep all entries in `used_clips.json` unchanged. `--clean-up` is now purely a disk cleanup command — it frees up files but preserves the registry for deduplication history.

---

## Summary of Changes — spec_twelve.md (2026-04-01)

### `config.json`
- Added `"saveResult": false` under the `output` section

### `youtube_uploader.py`
- Added `import shutil` (re-added for `shutil.copy2`)
- `upload()` now accepts a `save_result=False` parameter
- When `save_result=True`: creates `results/saved/` if needed, copies the video there with `shutil.copy2` before deleting the original from `results/`

### `main.py`
- `_run_upload()` reads `config["output"]["saveResult"]` (default `false`) and passes it as `save_result` to `uploader.upload()`
- `--clean-up` handler rewritten: calls updated `clean_registry()` which returns `(deleted_clips, deleted_results)`; prints two sections — clips deleted and result videos deleted

### `clip_registry.py`
- `clean_registry()` fully rewritten:
  - For each registry entry: deletes the file at `clip_path` if it exists on disk
  - For each registry entry: deletes `result_video` from `results/` and `results/saved/` if found
  - Registry entries are never modified — `used_clips.json` is left intact
  - Returns `(deleted_clips, deleted_results)` lists of deleted file path strings
  - Raises `FileNotFoundError` if registry does not exist
