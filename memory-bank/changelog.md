# Changelog — 2026-09-08 / v3

User confirmed the new photo intro replaces both the summary card and long static narration. Requested generated Google voice profiles, stable crop, Light/Dark MISA branding, memory and GitHub publication.

- Validated voice profiles with North/Central/South, age, gender, style, mood and deterministic 1.2x playback. Actual female/South/news/working-adult/neutral/1.2x synthesis produced 9.576083 seconds for the saved narration.
- Original display text aligns to generated audio, with exact token identity and finite ordered bounds. A failed real alignment prompted a bounded retry and duration hint. A subsequent real result aligned all 45 display tokens; browser playback showed advancing karaoke. Hiding intro captions preserves narration.
- Photo intro offers first frame and two varied timestamps, upload, pan/zoom, optional brand band, editable/AI title, case, text/highlight colors and position. No static narration block. Concurrent image generation uses a lock and only publishes an asset after the file exists.
- Crop preparation locks feasible face-safe centers per shot; moving subjects use deadband and smoothing. Single visible faces on reaction shots can retain a portrait without relabeling the listener as speaker. Raw focus cache reused, derived layout stable-v3.
- On the 618-point VnExpress clip, summed horizontal movement between samples in the same scene dropped from 8.3889 to 0.5739 normalized units (93.16%). This is a jitter diagnostic, not a speaker-recognition accuracy benchmark.
- Exact supplied MISA logo files with tagline, neutral Light/Dark themes and #ff7300 accent. Both modes inspected in the browser; theme/profile/title/photo persisted after reload.
- 102 Python tests and 4 JavaScript tests passed. Docker/Vite production build passed. No credentials, runtime SQLite or video/audio assets in source publication.

Full MP4 validation is recorded in ../VALIDATION.md. Exported source videos and runtime assets stay in the local Docker volume, not GitHub.
