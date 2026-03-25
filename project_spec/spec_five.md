make the following updates:

- in the background_videos dir move minecraft_parkour.mp4 into minecraft_parkour dir
- in the background_videos dir move the clips dir into minecraft_parkour dir
- update the references and config
- when generate_clip is called directly it should default to creating a new clip
- when generate_clip is called directly it should prompt the use how many clips should be created, if no input then default to 1
- update README.md

---

## Q & A

**Q1: After moving `minecraft_parkour.mp4` into `background_videos/minecraft_parkour/`, how should `videoName` in `config.json` be updated?**
A: Use a relative path from `background_videos/`: `"videoName": "minecraft_parkour/minecraft_parkour.mp4"`.

**Q2: Should the `clips_dir` path in `clip_generator.py` be derived dynamically from the video's directory, or hardcoded?**
A: Derived dynamically — `clips_dir` is computed from `Path("background_videos") / Path(video_name).parent / "clips"`, so any future video organized in its own subfolder will automatically get its own `clips/` directory.

**Q3: When generating multiple clips in `generate_clip.py`, should all clips be generated in a single run, each with a different random start time?**
A: Yes — the scrpt loops N times calling `generate_clip(config)` each iteration, each producing an independently random 60s segment.


---

All done. Here's a summary of every change made:

  Filesystem                                                                                                                                                                                     
  - background_videos/minecraft_parkour.mp4 → background_videos/minecraft_parkour/minecraft_parkour.mp4
  - background_videos/clips/ → background_videos/minecraft_parkour/clips/                                                                                                                        
                                                            
  config.json
  - videoName updated to "minecraft_parkour/minecraft_parkour.mp4"

  clip_generator.py
  - _get_existing_clip: clips_dir now derived from Path("background_videos") / Path(video_name).parent / "clips"
  - generate_clip: same dynamic clips_dir derivation; removed duplicate video_name lookup

  generate_clip.py
  - Added prompt: How many clips should be created? [1]: — defaults to 1 on empty input or invalid entry
  - Loops generate_clip(config) N times, printing progress when N > 1

  README.md
  - Updated setup step 3 to describe the subdirectory structure
  - Updated config example (videoName format)
  - Updated project structure tree
  - Updated config reference table entry for videoName
  - Added "Generate background clips manually" section documenting generate_clip.py

  project_spec/spec_five.md
  - Appended Q&A section with all three questions and answers

---

## Speed up clip generation

**Q: The clip generation is slow — how should it be sped up?**
A: Use stream copy (`-c:v copy`) via a direct `ffmpeg` subprocess call instead of re-encoding with MoviePy/libx264. Duration is fetched with `ffprobe`. This skips re-encoding entirely (10–50x faster); clip boundaries may snap to the nearest keyframe, which is acceptable.

**Changes made:**
- `clip_generator.py`: removed MoviePy/PIL imports; replaced `VideoFileClip` + `write_videofile` with `ffprobe` (duration) and `ffmpeg -ss -t -c:v copy -an` (stream copy cut)

---

● Done. Changes to clip_generator.py:       
                                                                                          
  - Removed MoviePy and PIL imports entirely
  - Added _get_video_duration() using ffprobe — reads only metadata, doesn't load the video                                                                                                      
  - generate_clip() now calls ffmpeg -ss {start} -i {video} -t 60 -c:v copy -an {output} — stream copies the segment with no re-encoding
                                                                                                                                                                                                 
  The result should be near-instant compared to before.

---

## Unique clip naming + collision retry

**Q1: What format should the start time take in the filename?**
A: Append `_start_time_` followed by integer seconds, e.g. `saved_clip_20260324_143022_start_time_45.mp4`.

**Q2: On each retry, should a fresh timestamp also be generated?**
A: No — keep the original timestamp and only pick a new random start time on each retry.

**Changes made:**
- `clip_generator.py`: filename now includes `_start_time_{int(start_time)}`; on collision, retries up to 3 times with a new random start time (same timestamp); logs a warning if all attempts collide and overwrites on the final attempt.


---

● Done. Summary of changes to clip_generator.py:    
                                                                                          
  - Filename format: saved_clip_20260324_143022_start_time_45.mp4
  - On collision: retries up to 3 times, picking a new random start each attempt (timestamp stays fixed)                                                                                         
  - If all 3 attempts collide: logs a warning and overwrites on the final attempt

---

## Run summary logging in generate_clip.py

**Q1: Should the collision count reflect each individual retry, or the number of clips that had at least one collision?**
A: Number of clips that had at least one collision.

**Q2: To track per-clip collision info, should `generate_clip()` return a tuple `(path, had_collision)`?**
A: Yes — requires a small update to `main.py` to unpack the tuple.

**Changes made:**
- `clip_generator.py`: `generate_clip()` now returns `(path, had_collision)` tuple; `had_collision` is set to `True` on the first filename collision.
- `generate_clip.py`: tracks `created` and `collisions` counts across all clips; prints a summary at the end showing clips requested, created, and with collisions.
- `main.py`: updated `generate_clip()` call to unpack `clip_path, _`.

---

● Done. Changes made:                               
                                                                                          
  - clip_generator.py: generate_clip() now returns (path, had_collision) — had_collision is True if any filename collision occurred during that clip's generation
  - generate_clip.py: tracks created and collisions across the loop; prints a summary at the end:                                                                                                
  === Summary ===
  Clips requested:        3                                                                                                                                                                      
  Clips created:          3                                 
  Clips with collisions:  1
  - main.py: updated to unpack clip_path, _ from the new return type
