make the following updates:

- add a flag called '--tts', when this flag is applied on main.py it should only run generate_tts.py and behave as if the file was called directly
- add a flag called '--clip', when this flag is applied on main.py it should only run generate_clip.py and behave as if the file was called directly
- add a flag called '--loop', when this flag is applied on main.py prompt the user how many times the script should run
- add a cron job that will execute main.py at a specific time, the cron should be added to the config in central time
  - there should also be a flag added called '--schedule', this should enable the scheduled cron to run at the time set in the config
- add a flag called '--help', this should essentially be a typical help flag command response, it should give a brief description of the available flags and anything else a normal help flag would give you
-

---

## Suggested improvements accepted

- **`--tts [N]` and `--clip [N]` accept optional count argument** — more scriptable than an interactive prompt; defaults to `1` if omitted
- **`--unschedule` flag** — complements `--schedule`; removes the Windows Task Scheduler entry. If `--schedule` hits an error, it automatically attempts to unschedule and logs whether the cleanup succeeded
- **Log existing task on `--schedule`** — if a task named `ClipVox` already exists, a notice is printed before overwriting it
- **`--loop` includes upload per iteration** — each loop run is fully end-to-end including upload when `shouldUpload` is true

## Q&A

**Q1: Should `--tts` use an interactive prompt or accept a count argument?**
Accept an optional count directly (e.g. `--tts 3`), defaulting to `1` if omitted.

**Q2: Should `--clip` match the same pattern as `--tts`?**
Yes — `--clip [N]`, defaulting to `1`.

**Q3: Should `--loop` run the full pipeline including upload each iteration?**
Yes — treat each loop iteration as a complete end-to-end run.

**Q4: Should `--schedule` use a persistent Python process or register with Windows Task Scheduler?**
Register a Windows Task Scheduler entry so the job survives process restarts and runs even if the terminal is closed.

**Q5: Should the schedule config support a single daily time or days of the week?**
Single daily time only.

**Q6: Should `--help` use custom formatting or rely on argparse defaults?**
Rely on argparse — ensure all flag descriptions are well-written so the default output is informative.

**Q7: Should `--loop` upload after each run, and should `--unschedule` be added?**
Yes — each loop iteration uploads if `shouldUpload` is true. Yes — include `--unschedule`. If `--schedule` errors, automatically attempt to unschedule and log the result clearly.

---

## Summary of changes

### `main.py`
- Added imports: `subprocess`, `sys`, `datetime`, `ZoneInfo` from `zoneinfo`, `generate_single_tts` from `tts_generator`
- Added `TASK_NAME = "ClipVox"` constant
- Added `_run_tts_mode(config, count)` — calls `generate_single_tts` N times, stops early if all cached
- Added `_run_clip_mode(config, count)` — sets `useExistingClip=False`, calls `generate_clip` N times, prints summary
- Added `_run_loop_mode(config)` — prompts for count, runs full pipeline + upload per iteration
- Added `_task_exists()` — queries `schtasks` to check if the ClipVox task is registered
- Added `_unregister_schedule(log_result)` — deletes the Task Scheduler entry, returns success bool
- Added `_register_schedule(config)` — converts `scheduleTime` from CT to local time, registers with `schtasks /create`; logs if existing task found; on error, unschedules and logs cleanup result
- Replaced single `--upload` argument with a `mutually_exclusive_group` containing: `--tts`, `--clip`, `--loop`, `--upload`, `--schedule`, `--unschedule`
- All flag help strings written for informative `--help` output
- `main()` dispatches to the appropriate mode function based on which flag is set

### `config.json`
- Added `"schedule": { "scheduleTime": "14:30" }` section (time in Central Time)

### `requirements.txt`
- Added `tzdata>=2023.3` — provides IANA timezone data for `zoneinfo` on Windows

### `README.md`
- Scripts table updated with `--loop`, `--tts [N]`, `--clip [N]`, `--schedule`, `--unschedule`
- New `schedule` config section added with table and usage note
- `config.json` example updated with `schedule` section and corrected `youtube` keys
