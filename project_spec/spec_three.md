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
