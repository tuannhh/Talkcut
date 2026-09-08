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


# v4 RC — feedback corrections

- User clarified stable-version handoff/rollback. Historical v3 handoff remains documentation, not acceptance. Added immutable local checkpoints, version tags, image rollback and development return scripts; actual rollback round trip preserved source/clip/export counts.
- Corrected transparent MISA News template placement: original PNG is 4500×8000 with alpha bbox starting at y4499. Crop only invisible padding, fit visible artwork to full canvas width and anchor bottom. Preserve transparency over portrait. Removed title rectangle; caption x/y has wide safe range and drag support.
- Transcript sentence/frame rows are directly editable textareas. LCS-based mapping keeps original timing anchors; inserted text shares a nearby anchor instead of fabricated proportional word timings. Browser verified edit in sentence mode, switch to frame mode, reverse edit and save; original wording restored after test.
- Discovered proxy cut precision was insufficient: source 25 fps cut at relative 15.760 versus proxy label 15.833. Native source frame refinement fixes the brief wrong crop around camera edits. Group crop by observed camera shots, not each model semantic/chunk boundary. Layout calm-v4.2 includes source fps; first cuts 3.96,7.44,11.2,15.76,19.24,23.92,29.8,32.76.
- Visual-only frame mix around cuts, optional 1.4-second reaction hold at 94.04–95.44 on the sample. Source-FPS-aware thumbnail uses preceding frame 94.00, not next incoming frame. Conversion to 30 fps rounds upward to avoid bringing incoming frames into the held interval early. Audio/ASS timing remains unchanged. 60 source cuts, 59 after optional hold; no claim of removing most original camera edits.
- Actual Linux FFmpeg test kept 90 frames for a 3-second fixture, held red through a blue insert, showed red/green mixture at transition and clean green after it. Native-cut 8-second real-media proof checked incoming face and brief blend around 15.76, eliminating the empty crop seen in the first trial.
- 107 Python tests and 5 JavaScript tests passed; production build passed. Full-media evidence appended to VALIDATION.md after render finishes.

## 2026-09-08 — v5 candidate: portrait throughout, section editor, reusable presets

- Fixed automatic letterboxing: inferred uncertain/listener shots now use visible face geometry for a full-height portrait; no automatic fit mode. While audio-aware AI runs, a separate visual-only face preview supplies provisional crop and is labelled accordingly.
- Bàn dựng now separates Intro / Nội dung chính / Outro / Dùng chung. Main has trim, focus & Mix, and captions subpanels. Timeline buttons open the corresponding section; outro has a dedicated preview.
- SQLite presets support create, update, delete and apply. Styles/assets/voice transfer; narration, title/highlight words, source portrait and trim remain clip-specific. Applying an intro preset to an empty narration requests a new AI suggestion for that clip.
- Replaced temporal frame averaging with one two-image Mix (outgoing held frame → moving incoming shot), default .65s, adjustable to 1.2s. Runtime opacity commands run after the compositor to avoid framesync prefetch changing opacity early; the schedule leads by one output frame. The last cut cannot shorten video. ASS/audio timing unchanged.
- Short same-voice angle inserts can hold the preceding image only inside one continuous measured voice turn. Reaction/transition inserts can hold up to user limit. On real clip 1: 60 native camera cuts, 10 holds, 50 visible Mix points; clip 3: 45 cuts, 4 holds. This is editing cadence, not a precision claim for speaker recognition.
- Keep v0.4.0-rc.1 as rollback image/tag. v5 remains a candidate until the user accepts it. pre-v5-backup.sqlite created before changes.
- RC.2 compatibility correction: store the longer Mix in `mix_seconds`, preserve the v4 field range for rollback. Added a compatibility regression test; 114 Python + 5 JS tests pass. The rendered Mix geometry/audio are unchanged by the storage-field split.

### v0.6.0-rc.1 — 2026-09-08
- Fix center crop during unsaved edits; add profile-face refinement and reject wrong-sized detections.
- Remove cross-shot anchor contamination causing within-shot crop sway. Preserve accepted Mix.
- Keep PNG alpha over a freeze frame from the current clip, including artwork selected in the image slot.
- Drag the title locally; add size/alignment/bold/italic/underline controls shared with export and presets.
- Validation: 119 Python tests, 5 JavaScript tests, Docker/Vite build, actual browser edits/drag, 18s 1080×1920 H.264/AAC proof with full decode.

### v0.7.0-rc.1 — 2026-09-08
- Added user-directed fixed subject selection on the source frame, scoped to camera shot/custom interval/whole clip.
- Fixed crop has no AI/face-driven motion; moving-subject tracking remains available separately.
- Added vertical positioning, exact interval persistence, same geometry in preview/export/freeze frames, and content-safe presets.
- New clips default fixed; existing choices preserved. Loading clips no longer automatically queues AI tracking.
- 126 Python/6 JS tests and real source/browser/Full-HD fixed-shot validation passed.

### v0.7.1-rc.1 — 2026-09-08
- Set action buttons and active button choices to #0086ff backgrounds with #ffffff labels in both themes; retain disabled opacity and hover feedback.
- Validated Docker/Vite build and actual browser screenshots/computed styles in Light and Dark mode. No video/data logic changed.
