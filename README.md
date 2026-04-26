# ClipVox

Automated short-form vertical video pipeline. Combines a background gameplay clip with ElevenLabs TTS audio and synced word-by-word captions, then optionally uploads directly to YouTube Shorts.

---

## How it works 

```
background_videos/  +  phrases.json
        │                    │
        ▼                    ▼
  [clip_generator]    [tts_generator]
  60s random clip     MP3 + word chunks
        │                    │
        └──────────┬─────────┘
                   ▼
          [video_composer]
          FFmpeg: scale/crop + drawtext captions + audio mix
                   │
                   ▼
              results/*.mp4
                   │
                   ▼
          [youtube_uploader]
          OAuth2 → YouTube Shorts
          logs to results/used_clips.json
          deletes local file after upload
```

1. **Background Clip** — extracts a random segment from a source video in `background_videos/` (length adjusted for `speed`), or reuses an existing cached clip. Set `cacheClip: true` to save the clip to disk for reuse; `false` (default) extracts a temp clip that is deleted after composition.
2. **Text-to-Speech** — always plays a fixed intro clip first, then fills the remaining video duration (45–60s) with saved or newly-generated TTS phrases separated by configurable gaps (`phraseGap`, `introPhraseGap`)
3. **Compose** — builds an FFmpeg filter complex that scales/crops the background to 9:16, mixes all TTS audio at their calculated offsets, and burns in synced word-by-word captions via the `drawtext` filter, then writes to `results/`
4. **Upload** — authenticates with YouTube via OAuth 2.0 and uploads to Shorts; records the YouTube video ID, URL, and timestamp in `results/used_clips.json`, then deletes the local file

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in .env
cp .env.example .env   # or create .env manually — see Environment variables below

# 3. Add a background video
#    Place an .mp4 (≥60s) under background_videos/<name>/<name>.mp4

# 4. Edit config.json to point at your video and phrase set

# 5. Run
python main.py
```

---

## Setup

### Environment variables

Create a `.env` file in the project root:

```ini
ELEVENLABS_API_KEY=your_elevenlabs_key

# YouTube — only needed if using the uploader
YOUTUBE_CLIENT_ID=your_oauth_client_id
YOUTUBE_CLIENT_SECRET=your_oauth_client_secret
```

**Getting YouTube credentials:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Enable the **YouTube Data API v3**
3. Create an **OAuth 2.0 Client ID** (Application type: Desktop app)
4. Copy the client ID and secret into `.env`
5. On first run a browser window opens for authorization — the token is cached in `.youtube_token.json` at the project root for all subsequent runs (automatically refreshed when expired)

### Install FFmpeg

FFmpeg is bundled via `imageio-ffmpeg` and used automatically. No manual FFmpeg install is required.

### Add a background video

Place a `.mp4` file (at least 60 seconds long) at:

```
background_videos/<subfolder>/<subfolder>.mp4
```

Example: `background_videos/minecraft_parkour/minecraft_parkour.mp4`

When `cacheClip` is `true`, extracted clips are saved to `background_videos/<subfolder>/clips/` using stream copy (no re-encoding). When `false`, a temp clip is written there and deleted after composition.

---

## Scripts

| Script | What it does |
|--------|-------------|
| `python main.py` | Full pipeline: generate a new video and optionally upload it |
| `python main.py --upload [N]` | Skip generation, upload N existing video(s) from `results/` (default 1) |
| `python main.py --loop [N]` | Run the full pipeline N times end-to-end (default 1) |
| `python main.py --tts [N]` | Generate and cache N TTS clips (default 1), skip composition. Each generated phrase is automatically moved from `phrases.json` to `converted_phrases.json` |
| `python main.py --clip [N]` | Extract and cache N background clips (default 1), skip TTS and composition |
| `python main.py --clean-up` | Delete clip files and result videos referenced in `results/used_clips.json`; registry entries are kept intact |
| `python main.py --clean-up-tts` | Move phrases from `phrasesPath` that already have a cached TTS clip into `converted_phrases.json`, remove duplicates from `phrasesPath`, and log a full report |
| `python main.py --tts-status` | Show remaining ElevenLabs monthly characters and the next reset date |
| `python main.py --schedule` | Register a recurring Windows Task Scheduler entry using `schedule.intervalMinutes` and `schedule.autoShutoffHours` |
| `python main.py --unschedule` | Remove the ClipVox Windows Task Scheduler entry |
| `python generate_clip.py` | Extract one or more background clips without running TTS or compositing |
| `python generate_tts.py` | Pre-generate and cache TTS clips without compositing a video |

### `generate_clip.py`

Prompts for the number of clips to create (defaults to 1). Each clip is a random 60s segment saved to `background_videos/<subfolder>/clips/`.

Filenames include a timestamp, start time, and speed, e.g. `saved_clip_20260324_143022_start_time_45_speed1.25.mp4`. Up to 3 retry attempts are made on filename collision before overwriting with a warning.

```
=== Summary ===
Clips requested:        3
Clips created:          3
Clips with collisions:  1
```

### `generate_tts.py`

Generates and caches individual TTS clips from the configured phrases file. Stops early if all phrases are already cached. Useful for pre-filling the cache before a batch run.

After each clip is generated, the phrase is automatically moved from `phrases.json` into `converted_phrases.json` in the same directory, keeping the active phrase pool clean. Phrases already present in `converted_phrases.json` are excluded from API calls entirely.

```
=== TTS Generator ===
How many clips to generate? (press Enter for 1):
```

#### `--intro` flag

```bash
python generate_tts.py --intro
```

Sets up the intro TTS clip used at the start of every video. Reads `intro_phrase.json` from `<phrasesPath parent>/intro_tts/` and either promotes a cached clip or generates a new one from ElevenLabs.

**`intro_phrase.json` format:**

```json
{"phrase": "Your intro text here."}
```

**Behavior:**

1. Reads `intro_phrase.json` — exits with a clear message if missing or if the `phrase` key is absent
2. Checks `saved_elevenlabs_tts/` for a cached clip matching the phrase
3. **If cached** — moves it into `intro_tts/`; any existing `tts_elevenlabs_*` already in `intro_tts/` is moved back to `saved_elevenlabs_tts/` first
4. **If not cached** — calls ElevenLabs to generate a new clip and saves it directly to `intro_tts/`; any existing `tts_elevenlabs_*` in `intro_tts/` is moved back to `saved_elevenlabs_tts/` first
5. Exits with an error if more than one `tts_elevenlabs_*` dir is found in `intro_tts/` (requires manual cleanup)

`intro_tts/` is created automatically if it does not exist.

---

## `config.json` reference

```json
{
    "backgroundVideo": {
        "videoName": "minecraft_parkour/minecraft_parkour.mp4",
        "clipName": "saved_clip_",
        "backgroundVideoLength": 60,
        "speed": 1.0,
        "useExistingClip": true,
        "existingClipName": "",
        "cacheClip": false
    },
    "tts": {
        "model": "eleven_multilingual_v2",
        "voiceId": "JBFqnCBsd6RMkjVDRZzb",
        "introVoiceId": "JBFqnCBsd6RMkjVDRZzb",
        "phrasesPath": "talk_to_speak/creepy_ai/phrases.json",
        "useSavedTts": true,
        "savedTtsPrefix": "",
        "phraseGap": 0.5,
        "pauseDuration": 0.5,
        "introPhraseGap": 0.5,
        "phraseExclusionDays": 3,
        "font": "Arial",
        "fontColor": "white",
        "fontSize": 70
    },
    "output": {
        "name": "result_",
        "encodingPreset": "fast",
        "threads": 4,
        "saveResultOnUpload": false
    },
    "backgroundAudio": {
        "includeAudio": false,
        "audioPath": "background_sounds/your_music.mp3",
        "audioStartTime": 0,
        "backgroundAudioVolume": 0.3,
        "ttsAudioVolume": 1.0
    },
    "schedule": {
        "intervalMinutes": 30,
        "autoShutoffHours": 2
    },
    "youtube": {
        "shouldUpload": true,
        "uploadCount": 1,
        "title": "Things AI Have Actually Said #Shorts",
        "description": "",
        "tags": ["Shorts"],
        "categoryId": 24,
        "privacyStatus": "public"
    }
}
```

### `backgroundVideo`

| Key | Type | Description |
|-----|------|-------------|
| `videoName` | string | Source `.mp4` path relative to `background_videos/`, e.g. `minecraft_parkour/minecraft_parkour.mp4` |
| `clipName` | string | Filename prefix for newly extracted clips (only used when `cacheClip` is `true`) |
| `backgroundVideoLength` | number | Duration in seconds for the final background clip and TTS max fill (default `60`) |
| `speed` | number | Playback speed multiplier for the background video (default `1.0`). `1.25` = 25% faster. Only the background visuals are sped up — TTS audio and captions are unaffected. Source footage extracted is `backgroundVideoLength × speed` seconds |
| `useExistingClip` | bool | When `true`, reuses the most recent cached clip instead of generating a new one. Cached clips with a different speed are automatically skipped |
| `existingClipName` | string | Use a specific cached clip by name; falls back to most recent if not found |
| `cacheClip` | bool | When `true`, saves newly extracted clips to `clips/` for reuse; `false` (default) uses a temp file deleted after composition. Always `true` when using `--clip` |

### `tts`

| Key | Type | Description |
|-----|------|-------------|
| `model` | string | ElevenLabs model ID |
| `voiceId` | string | ElevenLabs voice ID used for regular TTS phrases |
| `introVoiceId` | string | ElevenLabs voice ID used for the intro clip; falls back to `voiceId` if empty or not set |
| `phrasesPath` | string | Path to a JSON array of phrase strings |
| `useSavedTts` | bool | `true` = use cached clips; `false` = call the API and cache results |
| `savedTtsPrefix` | string | Only load cached clips whose filenames start with this prefix |
| `phraseGap` | number | Seconds of silence between regular TTS phrases (default `0.5`) |
| `pauseDuration` | number | Duration in seconds of pauses inserted where `[pause]` appears in a phrase (default `0.5`). The `[pause]` marker is stripped from captions |
| `introPhraseGap` | number | Seconds of silence between the intro phrase and the first regular phrase; falls back to `phraseGap` if empty or not set |
| `phraseExclusionDays` | number | Number of days a used phrase is excluded from reuse. Phrases used within this rolling window (start-of-day granularity) are skipped on selection. Default `3` |
| `font` | string | Caption font name (must be available to FFmpeg) |
| `fontColor` | string | Caption color — any FFmpeg color string, e.g. `white`, `yellow` |
| `fontSize` | number | Caption font size in pixels |

### `output`

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Output filename prefix |
| `encodingPreset` | string | FFmpeg preset: `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow` |
| `threads` | number | Encoding threads (0 = FFmpeg default) |
| `saveResultOnUpload` | bool | When `true`, copies the result video to `results/saved/` before deleting it after a successful upload (default `false`) |

### `backgroundAudio`

| Key | Type | Description |
|-----|------|-------------|
| `includeAudio` | bool | `true` = mix a background music track into the final video |
| `audioPath` | string | Path to the source `.mp3` under `background_sounds/` |
| `audioStartTime` | number | Start offset in seconds from the source file (default `0`) |
| `backgroundAudioVolume` | number | Volume of the background music relative to full (e.g. `0.3` = 30%) |
| `ttsAudioVolume` | number | Volume of the TTS voices when mixed with background audio (default `1.0`) |

The source audio is trimmed once from `audioStartTime` to the end of the file and cached in `background_sounds/trimmed_audio/` as `{source}_{audioStartTime}.mp3`. The same cached file is reused for every video regardless of duration — the video composer's `-t` flag handles the actual cutoff. The cache is only invalidated if `audioStartTime` changes.

### `schedule`

| Key | Type | Description |
|-----|------|-------------|
| `intervalMinutes` | number | **Required.** How often to run the pipeline, in minutes (e.g. `30` = every 30 minutes) |
| `autoShutoffHours` | number\|null | Stop the repeating task after this many hours (e.g. `2`). Set to `null` or omit to run indefinitely until manually unscheduled |

Register with `python main.py --schedule` — the task starts immediately at the current time and repeats at the configured interval. On registration, the console logs the schedule, auto-shutoff, background video, background audio, and phrases path that will be used. Remove with `python main.py --unschedule`.

### `youtube`

| Key | Type | Description |
|-----|------|-------------|
| `shouldUpload` | bool | `false` = skip YouTube upload entirely, video is kept in `results/` (default `true`) |
| `uploadCount` | number | Number of videos to upload per run when `--upload` is passed |
| `title` | string | YouTube video title |
| `description` | string | YouTube video description |
| `tags` | array | List of tag strings |
| `categoryId` | number | YouTube category ID (e.g. `22` = People & Blogs, `24` = Entertainment) |
| `privacyStatus` | string | `public`, `unlisted`, or `private` |

---

## Clip deduplication

`results/used_clips.json` is a registry that tracks every background clip used in a composed video. Each entry records:

| Field | Description |
|-------|-------------|
| `clip_name` | Background clip filename |
| `clip_path` | Full path to the clip |
| `start_time` | Start offset (seconds) within the source video |
| `result_video` | Composed output filename |
| `youtube_id` | YouTube video ID (set after upload) |
| `youtube_url` | YouTube Shorts URL (set after upload) |
| `uploaded_at` | ISO 8601 UTC timestamp of upload |

Deduplication prevents the same background clip from being reused across any composed video (pending or uploaded), matching by both filename and start time.

Run `python main.py --clean-up` to free disk space: it deletes every clip file listed in `clip_path` and every result video listed in `result_video` (checked in both `results/` and `results/saved/`). Registry entries are never removed — `used_clips.json` is preserved for deduplication history.

---

## Intro phrase

Every video starts with a fixed intro TTS clip. On each run, `main.py` automatically checks whether `intro_phrase.json` has changed and updates the intro clip if needed before compositing.

The intro clip is loaded from `<phrasesPath parent>/intro_tts/`, which must contain:
- `intro_phrase.json` — `{"phrase": "..."}` defining the intro text
- One `tts_elevenlabs_*` subdirectory with an `.mp3` and matching `.json` (same format as `saved_elevenlabs_tts/` clips)

If either is missing the program logs a clear error and exits — no video is generated. Run `python generate_tts.py --intro` to create or update the intro clip.

After the intro plays, regular TTS phrases begin at `intro_duration + introPhraseGap` seconds.

**Example layout for `talk_to_speak/creepy_ai/`:**

```
talk_to_speak/creepy_ai/
├── phrases.json
├── converted_phrases.json
├── past_phrase_used.json           # auto-created after first successful video run
├── intro_tts/
│   ├── intro_phrase.json           # {"phrase": "Your intro text here."}
│   └── tts_elevenlabs_YYYYMMDD_HHMMSS/
│       ├── tts_elevenlabs_YYYYMMDD_HHMMSS.mp3
│       └── tts_elevenlabs_YYYYMMDD_HHMMSS.json
└── saved_elevenlabs_tts/
    └── tts_elevenlabs_YYYYMMDD_HHMMSS/
        ├── tts_elevenlabs_YYYYMMDD_HHMMSS.mp3
        └── tts_elevenlabs_YYYYMMDD_HHMMSS.json
```

---

## TTS behavior

- **`useSavedTts: true`** — loads all cached clips from the `saved_elevenlabs_tts/` folder alongside `phrases.json`. Fills the video (45–60s target) in random order with no repeats per run. Logs a warning if more than 15s of the video would be silent.
- **`useSavedTts: false`** — calls the ElevenLabs API to generate new clips, caches them, then fills the video the same way.
- **Phrase exclusion** — before selecting clips each run, phrases used within the last `phraseExclusionDays` days are excluded. The exclusion list is stored in `past_phrase_used.json` (next to `phrases.json`) and written only after a video is successfully composed. Entries older than the window are pruned automatically on each run. The intro clip is never subject to exclusion.
- **Exhaustion fallback** (`useSavedTts` only) — if every saved TTS phrase is in `past_phrase_used` and the exclusion window has not fully passed, `past_phrase_used.json` is force-cleared, a warning is logged, and TTS selection restarts from scratch with no exclusions.
- Each TTS clip is stored in its own timestamped subdirectory: `saved_elevenlabs_tts/tts_elevenlabs_YYYYMMDD_HHMMSS/`
- ElevenLabs returns word-level timestamps (chunks); these are stored in a JSON sidecar alongside each `.mp3` and used by the composer to place caption `drawtext` filters at exact times.
- After every ElevenLabs API call, remaining monthly characters and the next reset date are logged. For `--tts` this appears after the moved-phrase confirmation; for other flows it appears after the clip is saved:
  ```
  ElevenLabs credits: 8,432 remaining of 10,000  |  resets 2026-05-01 00:00 UTC
  ```
  If the reset date is unavailable for the plan, only the remaining/limit is shown. Logged silently if the request fails.

---

## Upload behaviour

| Command | `shouldUpload` | Behaviour |
|---------|------------|-----------|
| `python main.py` | `true` | Generate a new video and upload it |
| `python main.py` | `false` | Generate a new video, skip upload — file stays in `results/` |
| `python main.py --upload` | any | Skip generation, upload existing video(s) from `results/` |

> `--upload` always triggers an upload regardless of the `shouldUpload` config flag.

When `--upload` is passed and `results/` is **empty**, the pipeline runs automatically to generate one video, which is then uploaded immediately. A prominent notice is printed at the end.

After each successful upload the YouTube video ID and URL are written to `results/used_clips.json` and the local file is deleted.

---

## Adding a phrase set

1. Create a directory: `talk_to_speak/<my_set>/`
2. Add `phrases.json` — a JSON array of strings, one phrase per element:
   ```json
   ["Phrase one.", "Phrase two.", "Another thing to say."]
   ```
3. Set `tts.phrasesPath` in `config.json` to point to it
4. Cached TTS clips will be stored automatically at `talk_to_speak/<my_set>/saved_elevenlabs_tts/`
5. When using `--tts`, each newly generated phrase is moved from `phrases.json` to `converted_phrases.json` automatically after generation
6. Run `python main.py --clean-up-tts` to retroactively move any phrases that were cached before the auto-move behavior — or after manually placing clips into `saved_elevenlabs_tts/`. Also removes any duplicate phrases from `phrases.json` and logs them by name

---

## Project structure

```
clipvox-app/
├── background_videos/              # Source videos and extracted clips
│   └── minecraft_parkour/
│       ├── minecraft_parkour.mp4
│       └── clips/
│           └── saved_clip_YYYYMMDD_HHMMSS_start_time_N_speed1.25.mp4
├── talk_to_speak/
│   └── creepy_ai/
│       ├── phrases.json            # JSON array of active phrases
│       ├── converted_phrases.json  # Phrases already cached as TTS (moved here by --clean-up-tts)
│       ├── past_phrase_used.json   # Rolling exclusion log — phrases used in the last N days
│       ├── intro_tts/              # Required: one tts_elevenlabs_* clip + intro_phrase.json
│       │   ├── intro_phrase.json   # {"phrase": "..."} — defines the intro text
│       │   └── tts_elevenlabs_YYYYMMDD_HHMMSS/
│       │       ├── tts_elevenlabs_YYYYMMDD_HHMMSS.mp3
│       │       └── tts_elevenlabs_YYYYMMDD_HHMMSS.json
│       └── saved_elevenlabs_tts/
│           └── tts_elevenlabs_YYYYMMDD_HHMMSS/
│               ├── tts_elevenlabs_YYYYMMDD_HHMMSS.mp3
│               └── tts_elevenlabs_YYYYMMDD_HHMMSS.json  # word chunks + metadata
├── background_sounds/              # Source music files
│   ├── your_music.mp3
│   └── trimmed_audio/              # Auto-generated trims (cached, never committed)
├── results/                        # Generated output videos
│   ├── saved/                      # Copies kept when saveResultOnUpload is true
│   └── used_clips.json             # Clip deduplication registry (never committed)
├── config.json
├── .env                            # API keys (never committed)
├── .youtube_token.json             # OAuth token (auto-generated, never committed)
├── main.py                         # Entry point: pipeline + upload
├── clip_registry.py                # Clip deduplication registry read/write
├── generate_clip.py                # Standalone clip extractor
├── generate_tts.py                 # Standalone TTS pre-generator
├── clip_generator.py
├── tts_generator.py
├── video_composer.py
├── background_audio.py
├── youtube_uploader.py
└── config_loader.py
```

---

## Dependencies

| Package | Used for |
|---------|----------|
| `python-dotenv` | Loads `.env` API keys into the environment |
| `elevenlabs` | ElevenLabs API client — TTS generation with word-level timestamps |
| `moviepy` | Reads audio clip duration (`AudioFileClip`) |
| `imageio-ffmpeg` | Provides the bundled FFmpeg binary |
| `imageio` | Required by `imageio-ffmpeg` |
| `Pillow` | Required by `moviepy` |
| `numpy` | Required by `moviepy` |
| `decorator` | Required by `moviepy` |
| `proglog` | Required by `moviepy` |
| `google-api-python-client` | YouTube Data API v3 — uploads videos |
| `google-auth-oauthlib` | OAuth 2.0 browser flow for Google authorization |
| `google-auth-httplib2` | HTTP transport for Google API auth |
