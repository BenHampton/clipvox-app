make the following updates:

- add an optional flag called 'intro' for when generate_tts.py is called directly
- when this flag is used the user should not be prompted for how many tts should be created
  - it should use the tts config phrasesPath value's parent dir '/intro_tts' to reference 'intro_phrase.json'
    - 'intro_phrase.json' will have a single key value pair {"phrase": "string"}
  - it should always check the '/saved_elevenlabs_tts' dir to see if the phrase has already been cached
  - if it is cached 
    - then move the 'tts_elevenlabs_*' dir into '/intro_tts'
    - if there was an existing 'tts_elevenlabs_*' move it to the '/saved_elevenlabs_tts'
  - if it is not cached
    - it should always get a new tts from elevenlabs overriding any config using 'intro_phrase.json'
      - if 'intro_phrase.json' is missing or empty gracefully exit logging a clear message why
    - if there is an existing 'tts_elevenlabs_*' dir move it to '/saved_elevenlabs_tts'
    - save the new tss to '/intro_tts' using the same dir and file format that was used to save tts in '/saved_elevenlabs_tts'
  - if '/intro_tts' does not exist create it
  - update README.md

---

## Q&A

**Q1: Should the flag be invoked as `--intro` (argparse-style), `intro` (positional), or something else?**
`--intro` (argparse-style): `python generate_tts.py --intro`

**Q2: If `intro_tts/` already has a `tts_elevenlabs_*` dir that needs to be moved back to `saved_elevenlabs_tts/`, is it always exactly one — or should all be moved if multiple exist?**
Always exactly one. If more than one is found, exit before calling ElevenLabs and log a clear message requiring manual cleanup.

**Q3: What counts as "empty" for `intro_phrase.json` — just an empty string value, or also when the `phrase` key is missing entirely?**
When the `phrase` key is missing entirely from the JSON. (An empty string value is also treated as invalid.)

---

## Summary of changes

### `tts_generator.py`
- Added `import shutil`
- Added `generate_intro_tts(config)` — resolves `intro_tts/` from `phrasesPath` parent, reads and validates `intro_phrase.json`, guards against multiple existing `tts_elevenlabs_*` dirs in `intro_tts/`, moves any existing intro clip back to `saved_elevenlabs_tts/`, then either promotes a cached clip or calls ElevenLabs to generate a new one saved directly to `intro_tts/`

### `generate_tts.py`
- Added `import argparse`
- Added `--intro` CLI flag via `argparse`
- When `--intro` is passed: skips the "how many clips" prompt and calls `generate_intro_tts(config)`; exits after completion
- Existing regular-generation behavior is unchanged

### `README.md`
- Added `--intro` flag documentation under `generate_tts.py` with full behavior description and `intro_phrase.json` format
- Updated the project structure tree to show `intro_phrase.json` and the `tts_elevenlabs_*` subdirectory inside `intro_tts/`
- Updated the **Intro phrase** section example layout to match the new structure
