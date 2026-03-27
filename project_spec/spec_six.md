make the following updates:

- create an api that will be able to upload the video result to youtube as a short
- the clientId and clientSecret will be added to the .env file
- make config values for the reasonable youtube api config, the config should live inside a config value called "youtube"
- after it is completed the upload it should log the url to the youtube short
- this process should be in an isolated class from the reset of the clip and tts generation classes
- add a config value called 'uploadOnly' to determine whe main.py runs should it only upload a video from the results to youtube, the config should be defaulted to true
- when a video is uploaded successfully the video in the results should be moved into a sub dir under 'results' called 'uploaded'
- if the results dir is empty log a message and create a new video to be uploaded this should override the 'uploadOnly' config but it should still follow the caching configs for generating a clip and generating tts that calls elevenlabs
- if the results were empty and the app had to create a new video log a very clear message at the end of the process that the results are empty.

---

## Q & A

**Q1: When `uploadOnly: true` and there are multiple videos in `results/`, should the script upload all of them or just one?**
A: Configurable via `youtube.uploadCount` — defaults to `1` (most recent video).

**Q2: Should token caching be included so re-authorization isn't needed on every run?**
A: Yes — OAuth token is saved to `.youtube_token.json` and refreshed automatically on subsequent runs.

**Q3: What YouTube metadata should be configurable?**
A: `title`, `description`, `tags`, `categoryId`, `privacyStatus` — all housed under a `"youtube"` key in `config.json`.

---

## Summary of changes

- **`youtube_uploader.py`** *(new)*: Isolated `YouTubeUploader` class — handles OAuth 2.0 with token caching, uploads via YouTube Data API v3, logs the Short URL, and moves the uploaded file to `results/uploaded/`.
- **`config.json`**: Added `"youtube"` section with `uploadOnly` (default `true`), `uploadCount` (default `1`), `title`, `description`, `tags`, `categoryId`, `privacyStatus`.
- **`main.py`**: Refactored into `_run_pipeline()`, `_run_upload()`, and `_get_result_videos()`. Handles `uploadOnly` logic — generates a new video if `results/` is empty (with a prominent end-of-run warning), then uploads.
- **`.env`**: Added `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` placeholder keys.
- **`requirements.txt`**: Added `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`.
- **`README.md`**: Updated setup instructions, project structure, and config reference table.