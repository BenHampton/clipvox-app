make the following updates:

- when adding the tts to the final clip. I want to make sure that we are not using previous tts from the last 3 days
  - let's make the 3 days configurable in tts config create a config key pair and name it something meaningful
  - this should also always be the start of the day to make it easy
- the information needed to store what clips were used for the last 3 days should be stored in the parent dir of tts.phrasesPath
  - create the file needed, I think we only need one new file unless you recommend something else?
  - let's call this past_phrase_used.json
- when the app runs it needs not use a tts from the last 3 days
- if the day has passed then the "previously used list of tts" should be cleared and start over

---

## Q & A

**Q1: Rolling window vs full reset for expired entries?**
Option A (rolling window) — entries older than `phraseExclusionDays` days are pruned on each run. `saved_elevenlabs_tts/` is never touched or modified.
Confirmed: Option A.

**Q2: What data should `past_phrase_used.json` store?**
Store by phrase text (not file path, since paths could change). Structure:
```json
{
  "used_phrases": [
    { "text": "some phrase here", "used_date": "2026-04-08" }
  ]
}
```
Confirmed: text-based storage, single file.

**Q3: Config key name for the exclusion window?**
`phraseExclusionDays` added to the `tts` section in `config.json` and `DEFAULT_CONFIG`. Default value: `3`.
Confirmed: `phraseExclusionDays`.

**Q4: When to write to `past_phrase_used.json`?**
After the final video is successfully written (not at clip selection time), so a failed or cancelled run does not burn a phrase slot.
Confirmed: Option B — write after video is done.

**Q5: Should the intro clip be excluded from the exclusion logic?**
Yes — the intro is a permanent fixture that repeats every video. It is never recorded in `past_phrase_used.json` and never filtered by the exclusion window.
Confirmed: skip the intro.

---

## Summary of Changes

### `config_loader.py`
- Added `"phraseExclusionDays": 3` to `DEFAULT_CONFIG["tts"]`. This is the number of days a used phrase is excluded from reuse. Start-of-day granularity (date comparison, no time component).

### `tts_generator.py`
- Added `date, timedelta` to the `datetime` import.
- Added `_get_past_phrases_path(config)` — returns the path `<phrasesPath parent>/past_phrase_used.json`.
- Added `_load_excluded_texts(config)` — reads `past_phrase_used.json`, prunes entries older than `phraseExclusionDays` days (rolling window from start of today), saves the pruned file back, and returns a `set` of excluded phrase texts.
- Added `record_used_phrases(config, clips)` — public function that appends each used phrase (with today's date) to `past_phrase_used.json`. Skips duplicates. Called after video is written, not during clip selection.
- Updated `_generate_new_clips` — added `excluded_texts=None` parameter. Filters the phrase list before shuffling so excluded phrases are never selected or re-generated.
- Updated `generate_tts()` — calls `_load_excluded_texts` at the start; passes excluded set to both `_generate_new_clips` and the `useSavedTts` filter; return signature changed from `(all_clips, video_duration, api_count)` to `(all_clips, used_clips, video_duration, api_count)` so the caller can record only non-intro clips.

### `main.py`
- Imported `record_used_phrases` from `tts_generator`.
- Updated `generate_tts` return unpacking: `tts_clips, used_clips, video_duration, tts_api_count`.
- Added `record_used_phrases(config, used_clips)` call immediately after `compose_video` succeeds in `_run_pipeline`.

### New file: `talk_to_speak/creepy_ai/past_phrase_used.json` (created at runtime)
- Created automatically on first successful video run.
- Stores `{ "used_phrases": [{ "text": "...", "used_date": "YYYY-MM-DD" }] }`.
- Pruned automatically each run — entries outside the rolling window are removed.
- Never modified by `saved_elevenlabs_tts/` logic; those files are untouched.



-----------------------------------------------------------------------------------------------------------

## Spec 14 — Force-refresh past_phrase_used when all saved TTS are excluded

### Ask

> phraseExclusionDays should be added to config.json also
> when creating a final result if all tts are used and the phraseExclusionDays has not passed then force it to refresh the past_phrase_used list. log a clear warning.

---

## Q & A

**Q1: Should this only trigger when `useSavedTts` is `true`?**
Yes — force-clear only applies when using saved ElevenLabs TTS files (`useSavedTts: true`) and every phrase in `saved_elevenlabs_tts/` is present in `past_phrase_used`.
Confirmed.

**Q2: When the refresh happens, clear the entire list or only expired entries?**
Clear the entire `past_phrase_used` list — even entries that haven't reached `phraseExclusionDays` yet.
Confirmed: wipe all entries.

**Q3: After clearing, restart TTS selection from scratch or continue from current state?**
Restart the full TTS selection process from scratch with the now-empty exclusion list.
Confirmed.

---

## Summary of Changes

### `config.json`
- Added `"phraseExclusionDays": 5` to the `tts` section so the value is visible and editable alongside other TTS settings (previously only present in `DEFAULT_CONFIG` in `config_loader.py`).

### `tts_generator.py`
- Added `_force_clear_past_phrases(config)` — writes `{"used_phrases": []}` back to `past_phrase_used.json`, wiping all entries.
- Updated `generate_tts()` — in the `useSavedTts` branch, all saved clips are now loaded first (before exclusion filtering). If there are saved clips but none survive the exclusion filter (all are in `past_phrase_used`), the function:
  1. Logs a `WARNING` naming the clip count and `phraseExclusionDays` value
  2. Calls `_force_clear_past_phrases()` to wipe `past_phrase_used.json`
  3. Resets `excluded_texts` to an empty set and sets `available` to the full saved clip list
  4. Continues into `_fill_clips` as normal — TTS selection restarts from scratch with no exclusions



