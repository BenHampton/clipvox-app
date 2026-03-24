make the following updates:

- when directly running generate_tts.py only execute the file 1 time.
- make sure there is not a cached phase tts to avoid making extra api calls to get the information
- if there is a cache tts use that 
- add logs when making calls to elevenlabs

---

## Q & A

**Q: When running `generate_tts.py` directly, should it iterate through all phrases or generate just one new clip per run?**
A: Execute once — generate one TTS clip per run. When called from `main.py`, behave as-is (fill the video with multiple clips).

**Q: When `generate_tts.py` picks a random phrase that is already cached, should it skip it and pick a different uncached phrase, or just exit?**
A: Skip it and pick a new uncached phrase. If all phrases are cached, log a warning.

**Q: Should the cache lookup match a phrase by exact text against the `"text"` field in each saved `.json` file?**
A: Yes, exact text match.

**Q: Should `generate_tts.py` keep the override that forces `useSavedTts = False`, or respect `config.json`?**
A: The override should stay.


 All done. Here's a summary of every change:

  Temp files — deleted the 3 *TEMP_MPY_wvf_snd.mp4 files from the project root; added the pattern to .gitignore

  config.json — added encodingPreset: "fast" and threads: 4 under output

  config_loader.py — added defaults encodingPreset: "medium" and threads: 0

  video_composer.py — full rewrite:
  - Dropped all MoviePy, PIL, and numpy imports
  - Uses imageio_ffmpeg.get_ffmpeg_exe() to locate FFmpeg (falls back to PATH)
  - Builds a single -filter_complex that:
    - Scales and center-crops the background to 1080×1920 via scale + crop
    - Chains all caption chunks as drawtext filters with enable='between(t,...)' timing
    - Uses adelay per TTS clip to place audio at its correct offset, then amix to merge them
  - Runs the command with subprocess.run, respecting encodingPreset and threads from config

  README.md — updated the compose step description, config example, and config reference table
