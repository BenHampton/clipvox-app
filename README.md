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
        └──────────┬──────────┘
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
          moves file → results/uploaded/
```

1. **Background Clip** — extracts a random 60s segment from a source video in `background_videos/`, or reuses an existing saved clip
2. **Text-to-Speech** — loads saved ElevenLabs TTS clips or generates new ones from a phrases file, filling the video duration (45–60s) with 0.5s gaps between clips
3. **Compose** — builds a single FFmpeg command that scales/crops the background to 9:16, mixes all TTS audio at their calculated offsets, and burns in synced word-by-word captions via the `drawtext` filter, then writes to `results/`
4. **Upload** — authenticates with YouTube via OAuth 2.0 and uploads to Shorts; after a successful upload the video is moved to `results/uploaded/`

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

Extracted clips are saved to `background_videos/<subfolder>/clips/` using stream copy (no re-encoding).

---

## Scripts

| Script | What it does |
|--------|-------------|
| `python main.py` | Full pipeline or upload-only, depending on `youtube.uploadOnly` |
| `python generate_clip.py` | Extract one or more background clips without running TTS or compositing |
| `python generate_tts.py` | Pre-generate and cache TTS clips without compositing a video |

### `generate_clip.py`

Prompts for the number of clips to create (defaults to 1). Each clip is a random 60s segment saved to `background_videos/<subfolder>/clips/`.

Filenames include a timestamp and start time, e.g. `saved_clip_20260324_143022_start_time_45.mp4`. Up to 3 retry attempts are made on filename collision before overwriting with a warning.

```
=== Summary ===
Clips requested:        3
Clips created:          3
Clips with collisions:  1
```

### `generate_tts.py`

Generates and caches individual TTS clips from the configured phrases file. Stops early if all phrases are already cached. Useful for pre-filling the cache before a batch run.

```
=== TTS Generator ===
How many clips to generate? (press Enter for 1):
```

---

## `config.json` reference

```json
{
    "backgroundVideo": {
        "videoName": "minecraft_parkour/minecraft_parkour.mp4",
        "clipName": "saved_clip_",
        "useExistingClip": true,
        "existingClipName": ""
    },
    "tts": {
        "model": "eleven_multilingual_v2",
        "voice": "JBFqnCBsd6RMkjVDRZzb",
        "phrasesPath": "talk_to_speak/creepy_ai/phrases.json",
        "useSavedTts": true,
        "savedTtsPrefix": "",
        "font": "Arial",
        "fontColor": "white",
        "fontSize": 70
    },
    "output": {
        "name": "result_",
        "encodingPreset": "fast",
        "threads": 4
    },
    "youtube": {
        "uploadOnly": true,
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
| `clipName` | string | Filename prefix for newly extracted clips |
| `useExistingClip` | bool | When `true`, reuses the most recent saved clip instead of generating a new one |
| `existingClipName` | string | Use a specific saved clip by name; falls back to most recent if not found |

### `tts`

| Key | Type | Description |
|-----|------|-------------|
| `model` | string | ElevenLabs model ID |
| `voice` | string | ElevenLabs voice ID |
| `phrasesPath` | string | Path to a JSON array of phrase strings |
| `useSavedTts` | bool | `true` = use cached clips; `false` = call the API and cache results |
| `savedTtsPrefix` | string | Only load cached clips whose filenames start with this prefix |
| `font` | string | Caption font name (must be available to FFmpeg) |
| `fontColor` | string | Caption color — any FFmpeg color string, e.g. `white`, `yellow` |
| `fontSize` | number | Caption font size in pixels |

### `output`

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Output filename prefix |
| `encodingPreset` | string | FFmpeg preset: `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow` |
| `threads` | number | Encoding threads (0 = FFmpeg default) |

### `youtube`

| Key | Type | Description |
|-----|------|-------------|
| `uploadOnly` | bool | `true` = skip generation, upload existing videos from `results/` |
| `uploadCount` | number | Number of videos to upload per run when `uploadOnly` is `true` |
| `title` | string | YouTube video title |
| `description` | string | YouTube video description |
| `tags` | array | List of tag strings |
| `categoryId` | number | YouTube category ID (e.g. `22` = People & Blogs, `24` = Entertainment) |
| `privacyStatus` | string | `public`, `unlisted`, or `private` |

---

## TTS behavior

- **`useSavedTts: true`** — loads all cached clips from the `saved_elevenlabs_tts/` folder alongside `phrases.json`. Fills the video (45–60s target) in random order with no repeats per run. Logs a warning if more than 15s of the video would be silent.
- **`useSavedTts: false`** — calls the ElevenLabs API to generate new clips, caches them, then fills the video the same way.
- Each TTS clip is stored in its own timestamped subdirectory: `saved_elevenlabs_tts/tts_elevenlabs_YYYYMMDD_HHMMSS/`
- ElevenLabs returns word-level timestamps (chunks); these are stored in a JSON sidecar alongside each `.mp3` and used by the composer to place caption `drawtext` filters at exact times.

---

## Upload-only mode

When `youtube.uploadOnly` is `true` (the default), `main.py` skips video generation entirely and uploads the most recent `.mp4` files from `results/`, up to `uploadCount`.

- If `results/` is **empty**, the pipeline runs automatically to generate one video, which is then uploaded immediately. A prominent notice is printed at the end.
- After each successful upload the video file is moved to `results/uploaded/` to prevent re-uploading.

---

## Adding a phrase set

1. Create a directory: `talk_to_speak/<my_set>/`
2. Add `phrases.json` — a JSON array of strings, one phrase per element:
   ```json
   ["Phrase one.", "Phrase two.", "Another thing to say."]
   ```
3. Set `tts.phrasesPath` in `config.json` to point to it
4. Cached TTS clips will be stored automatically at `talk_to_speak/<my_set>/saved_elevenlabs_tts/`

---

## Project structure

```
clipvox-app/
├── background_videos/              # Source videos and extracted clips
│   └── minecraft_parkour/
│       ├── minecraft_parkour.mp4
│       └── clips/
│           └── saved_clip_YYYYMMDD_HHMMSS_start_time_N.mp4
├── talk_to_speak/
│   └── creepy_ai/
│       ├── phrases.json            # JSON array of phrases
│       └── saved_elevenlabs_tts/
│           └── tts_elevenlabs_YYYYMMDD_HHMMSS/
│               ├── tts_elevenlabs_YYYYMMDD_HHMMSS.mp3
│               └── tts_elevenlabs_YYYYMMDD_HHMMSS.json  # word chunks + metadata
├── results/                        # Generated output videos
│   └── uploaded/                   # Videos moved here after successful upload
├── config.json
├── .env                            # API keys (never committed)
├── .youtube_token.json             # OAuth token (auto-generated, never committed)
├── main.py                         # Entry point: pipeline + upload
├── generate_clip.py                # Standalone clip extractor
├── generate_tts.py                 # Standalone TTS pre-generator
├── clip_generator.py
├── tts_generator.py
├── video_composer.py
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
