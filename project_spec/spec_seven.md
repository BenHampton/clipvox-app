make the following updates:

- when the tts is added into the video the time between a phrase should be added to the config
- add a config to check if there is a path to the first phrase that should be used when adding the tts to the video
- if the config path is empty or can not find it log a message and exit
- the config path should default to the phrasesPath config value's parent dir '/intro_tts' what will have 2 files a *.json and *.mp3 file similar th the content under '/saved_elevenlabs_tts/*/'
- the video should always start with this intro_phase tts then proceed to add the other tts like before

---

## Q&A

**Q1: What should the config key be named for the gap between phrases?**
`phraseGap`

**Q2: What should the config key be named for the intro TTS path?**
`introPath` *(ultimately not added as a config key — see Q4)*

**Q3: When `introPath` is not set or empty, should the code default to `<phrasesPath parent>/intro_tts/` or exit?**
If empty, exit gracefully and log a message explaining why.

**Q4: Should the code automatically use the default path `<phrasesPath parent>/intro_tts/`, or always exit if `introPath` isn't explicitly set?**
Yes, default automatically — do not add a config key. The code always resolves `<phrasesPath parent>/intro_tts/`. If the directory or required files are missing, log a clear message and exit gracefully.

**Q5: Should `phraseGap` apply between the intro phrase and the first regular TTS phrase?**
Add a separate `introPhraseGap` config key. It defaults to the value of `phraseGap` and falls back to `phraseGap` if empty or not set.

---

## Summary of changes

### `tts_generator.py`
- Removed hardcoded `GAP = 0.5` constant
- Added `_get_intro_dir(config)` — resolves `<phrasesPath parent>/intro_tts/`
- Added `_load_intro_clip(config)` — loads the single `.mp3` + `.json` from `intro_tts/`; calls `sys.exit(1)` with a clear message if the directory is missing or files are absent
- `generate_tts()` now reads `phraseGap` and `introPhraseGap` from `config["tts"]`; `introPhraseGap` falls back to `phraseGap` if empty or not set
- `generate_tts()` loads the intro clip first (offset `0.0`), then fills regular clips starting at `intro_duration + introPhraseGap`
- `_fill_clips()` now accepts `gap` and `start_time` parameters instead of using the removed `GAP` constant
- `_generate_new_clips()` now accepts `gap` and `start_time` parameters
- Added `import sys`

### `config.json`
- Added `"phraseGap": 0.5` to the `tts` section
- Added `"introPhraseGap": 0.5` to the `tts` section

### `README.md`
- Added `phraseGap` and `introPhraseGap` rows to the `tts` config reference table
- Added **Intro phrase** section explaining the `intro_tts/` directory requirement, fallback behavior, and example layout
- Updated the project structure tree to show `intro_tts/` alongside `saved_elevenlabs_tts/`
- Updated the example `config.json` block to include the two new keys