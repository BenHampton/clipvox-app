# ClipVox

Generates short-form vertical videos by combining a background gameplay clip with ElevenLabs TTS audio and synced word-by-word captions.

## How it works

1. **Background Clip** — extracts a random 60s segment from a source video in `background_videos/`, or reuses an existing saved clip
2. **Text-to-Speech** — loads saved ElevenLabs TTS clips or generates new ones from a phrases file, filling the video duration (45–60s) with 0.5s gaps between clips
3. **Compose** — builds a single FFmpeg command that scales/crops the background, mixes all TTS audio at their offsets, and burns in synced captions via the `drawtext` filter, then writes the result to `results/`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your API key

Copy `.env` and set your ElevenLabs API key:

```
ELEVENLABS_API_KEY=your_key_here
```

### 3. Add a background video

Place an `.mp4` file (at least 60s long) in `background_videos/`.

### 4. Configure `config.json`

```json
{
    "backgroundVideo": {
        "videoName": "your_video.mp4",
        "clipName": "saved_clip_",
        "useExistingClip": true,
        "existingClipName": ""
    },
    "tts": {
        "model": "eleven_multilingual_v2",
        "voice": "JBFqnCBsd6RMkjVDRZzb",
        "phrasesPath": "talk_to_speak/hannibal_lecter/phrases.json",
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
    }
}
```

## Running

```bash
python main.py
```

Output videos are saved to `results/`.

## Project structure

```
clipvox-app/
├── background_videos/          # Source videos and extracted clips
│   └── clips/
├── talk_to_speak/
│   └── hannibal_lecter/
│       ├── phrases.json        # List of phrases to speak
│       └── saved_elevenlabs_tts/
│           └── tts_elevenlabs_YYYYMMDD_HHMMSS/
│               ├── *.mp3
│               └── *.json
├── results/                    # Generated output videos
├── config.json
├── .env                        # API keys (never committed)
├── main.py
├── clip_generator.py
├── tts_generator.py
├── video_composer.py
└── config_loader.py
```

## Config reference

| Key | Description |
|-----|-------------|
| `backgroundVideo.videoName` | Source `.mp4` filename in `background_videos/` |
| `backgroundVideo.useExistingClip` | Reuse the most recent saved clip instead of generating a new one |
| `backgroundVideo.existingClipName` | Use a specific saved clip by name (falls back to most recent if not found) |
| `tts.phrasesPath` | Path to a JSON array of phrases |
| `tts.useSavedTts` | Use saved TTS clips instead of calling the API |
| `tts.model` | ElevenLabs model ID |
| `tts.voice` | ElevenLabs voice ID |
| `tts.font` / `tts.fontColor` / `tts.fontSize` | Caption styling |
| `output.encodingPreset` | FFmpeg encoding preset (`ultrafast`, `fast`, `medium`, etc.) — defaults to `medium` |
| `output.threads` | Number of encoding threads (0 = FFmpeg default) |

## TTS behavior

- When `useSavedTts: true` — loads all clips from `saved_elevenlabs_tts/` and fills the video (45–60s) in random order with no repeats per run. Logs a warning if more than 15s of the video would be silent.
- When `useSavedTts: false` — generates new TTS clips from the phrases file, saves them, and fills the video the same way.
- Each saved TTS clip is stored in its own subdirectory named after the file.

## Adding a new phrase set

1. Create a directory under `talk_to_speak/`, e.g. `talk_to_speak/my_character/`
2. Add a `phrases.json` file containing a JSON array of strings
3. Update `tts.phrasesPath` in `config.json`

Saved TTS clips for that set will automatically be stored alongside its `phrases.json`.
