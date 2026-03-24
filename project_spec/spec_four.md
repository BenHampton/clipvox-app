make the following updates:

- in the root of the project there is result_XXXTEMP_MPY_wvf_snd.mp4, why and can they be removed? if so lets remove them.
- the speed of writing the final video is taking longer that i would like, find opportunities to improve performance and speed up this step. if this requires a major refactor that is ok but be sure to keep the same feature/requirments
- update README.md

---

## Q & A

**Q: Should `*TEMP_MPY_wvf_snd.mp4` also be added to `.gitignore` to prevent future leftovers from being tracked?**
A: Yes.

**Q: The biggest speed gain is switching the encoding preset to `ultrafast`/`fast` at the cost of slightly larger files. Is that tradeoff acceptable?**
A: Yes — add it to config, set default to `fast`. If the config value is empty, default to `medium`.

**Q: Should a `threads` parameter also be added to config for parallel encoding?**
A: Yes, add it to config.

**Q: For the FFmpeg text rendering refactor, replace only the text rendering (option A) or bypass MoviePy entirely for final composition and use one FFmpeg command for everything (option B)?**
A: Option B — full FFmpeg bypass for the final compose step.

