make the following updates:

- add a config value for how long the background clip should be in seconds
  - call it 'backgroundVideoLength'
  - reference the new config value in the code 
- I want the option to be able to add audio to the final result of the video.
- this should be added to a new class
- add a config option to toggle adding the audio to the video and call the config value 'includeAudio'
- the audio file will come from a '*.mp3' file under '/background_sounds'
- add a config value with the path to the *.mp3 that should be used
- when config value 'includeAudio' is true the audio should be added to the video and it should:
  - use the mp3 file path from the config
  - check to see how long the final video is and create a trimmed version of the mp3 file to be added to the video
  - the trimmed version should be saved in a dir under 'background_sound' called 'trimmed_audio'
    - add 2 config options to determine the start and end time for the trimmed audio
      - default the config values to the start of the audio and end at the 60 seconds from the start
      - the new trimmed audio should be saved as the name of the source mp3 file and append '_{duration}_{startTime}_
        {stopTime}_{dateTimeStamp}'
        - 'duration' should be the length of the trimmed audio time in seconds
        - 'startTime' starting timestamp from trim of the source file
        - 'endTime' end timestamp from trim of the source file
        - 'dateTimeStamp' date time stamp when it was created 
  - before creating a new trimmed version of the audio it should check the 'trimmed_audio' dir to see if there is a cached file with the applicable audio length that can be used instead of creating a new trimmed file

---

## Suggested improvements accepted

- **`backgroundAudioVolume` + `ttsAudioVolume`** — added volume controls so background music doesn't overpower TTS speech
- **`backgroundVideoLength` drives TTS `MAX_VIDEO`** — TTS now fills up to `backgroundVideoLength` seconds instead of being hardcoded at 60s
- **Cache matching on source filename + duration** — more reliable than duration alone; prevents false cache hits from different trims that happen to be the same length

## Q&A

**Q1: Where should the background audio config live in `config.json`?**
In a new `backgroundAudio` section in `config.json`.

**Q2: Add `backgroundAudioVolume` to control music volume relative to TTS?**
Yes — also add `ttsAudioVolume` to control TTS voice volume in the mix.

**Q3: Should `backgroundVideoLength` also replace the hardcoded `MAX_VIDEO = 60.0` in `tts_generator.py`?**
Yes — TTS should fill up to `backgroundVideoLength` seconds for consistency.

**Q4: Should cache matching use source filename + duration, or just duration?**
Source filename + duration.

**Q5: Should the trim be from `audioStartTime` to `audioStartTime + video_duration`, making `audioEndTime` unnecessary?**
Yes — no `audioEndTime` config needed.

---

## Summary of changes

### `background_audio.py` (new)
- New `BackgroundAudio` class with `get_trimmed_audio(video_duration)` method
- Resolves `trimmed_audio/` dir from the source audio's parent directory
- Cache check: matches on source stem + duration (within 0.01s tolerance)
- If no cache hit: trims source MP3 via FFmpeg from `audioStartTime` to `audioStartTime + video_duration`
- Trimmed filename: `{source}_{duration:.3f}_{start:.3f}_{stop:.3f}_{timestamp}.mp3`

### `clip_generator.py`
- `clip_length = 60` replaced with `bg_config.get("backgroundVideoLength", 60)`
- Validation error message now includes the configured length

### `tts_generator.py`
- `_fill_clips()` — added `max_video` parameter (defaults to `MAX_VIDEO`); uses it instead of module constant
- `_generate_new_clips()` — same `max_video` parameter added
- `generate_tts()` — reads `backgroundVideoLength` from config, computes `min_video = max_video * 0.75`, passes `max_video` to both fill functions

### `video_composer.py`
- Imported `BackgroundAudio`
- `compose_video()` reads `backgroundAudio` config; when `includeAudio` is `true`, calls `BackgroundAudio.get_trimmed_audio()` and appends to FFmpeg inputs
- Audio filter section refactored: TTS clips mix to `[tts_amix]` when background audio is present; volume filters applied to both; final `amix` produces `[amix]`
- When `includeAudio` is `false`, existing behavior is completely unchanged

### `config.json`
- `backgroundVideoLength: 60` added to `backgroundVideo` section
- New `backgroundAudio` section: `includeAudio`, `audioPath`, `audioStartTime`, `backgroundAudioVolume`, `ttsAudioVolume`

### `.gitignore`
- `background_sounds/` added

### `README.md`
- `backgroundVideoLength` added to `backgroundVideo` config table
- New `backgroundAudio` config section with full table and cache/filename description
- Config example updated with both new sections
- Project structure updated to show `background_sounds/` and `background_audio.py`
