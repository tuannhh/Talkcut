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

### v0.8.0-rc.1 — 2026-09-09
- Added selected-subject tracking: users choose a local face sample, then SFace compares that portrait with locally detected faces per native camera shot. Crop locks inside each shot instead of following detector jitter.
- Removed the unsafe dependence on Gemini freehand face coordinates. Ambiguous, missing, profile or occluded shots retain a verified portrait still and are explicitly reviewable; original audio and karaoke timing continue.
- Opening a clip no longer performs a synchronous visual scan before showing the editor. Added bundled Google Sans, Open Sans, Barlow and Roboto for rendered intro titles.
- Regression validation: 150 Python tests and 6 JavaScript tests pass; Docker production build passes. The real 160.4-second VnExpress clip was re-analysed, and a 30-second Full-HD H.264/AAC proof decoded without errors. Its ambiguous +9s frame retains the selected male portrait rather than the interviewer/table.

### Distribution requirements — 2026-09-09 (documentation only)
- Recorded user-selected all-in-one installer flow retaining Docker, first-run Gemini API key and Internet requirement.
- Added provisional Windows minimum/recommended hardware and release validation gates. Packaging deferred until stable acceptance; no new runtime version.

### v0.9.0-rc.1 — 2026-09-10

- Replaced selected-face tracking's Haar + SFace path with a local SCRFD 10G
  detector, five-landmark alignment and ArcFace r50 512-value appearance
  embeddings adapted from the user's high-accuracy face-search project.
- Added an internal Docker `face-engine` with two bounded ONNX workers. It is
  not exposed on a host port, uses no Google request, retains no identity
  catalogue, and persists downloaded models only in the local Docker volume.
- Focus checks one still per short camera shot and two per long shot. This
  removes expensive per-1.5-second scanning while keeping shot locking and Mix
  pacing.
- Matching accepts only a clear winner. Ambiguous, profile or missing scenes
  use a verified portrait hold instead of moving the crop to a table,
  microphone or other guest.
- Version checkpoints now capture Studio and face-engine images together.

### v0.9.0-rc.2 — 2026-09-10

- YouTube imports now prefer a 2160p MP4 video stream with M4A audio. Existing
  YouTube sources can use “Tải lại bản sắc nét”: it downloads beside the old
  file, probes before switching, retains transcript/settings and refreshes
  generated thumbnails only.
- Compatible MP4 media remains the editor preview rather than being reduced to
  a 1280px proxy, preserving portrait crop detail.
- Removed selected-subject portrait-JPEG replacement and automatic visual
  holds. Ambiguous shots retain a crop anchor but the actual source footage,
  speech and captions remain moving.
- 152 Python tests and the Vite production build passed. The supplied test
  source was refreshed from 640×360 to 3840×2160; a 15.034-second Full-HD
  proof has no reference/visual holds and decodes successfully.

### v0.9.0-rc.3 — 2026-09-10

- Fixed the focus reload HTTP 500 caused by removing the freeze helper for
  ordinary reaction holds. Selected-subject tracking continues to produce no
  still holds, so this does not reintroduce frozen reference portraits.
- Hardened the browser API client against plain-text server errors, showing a
  recoverable Vietnamese error instead of `Unexpected token ... valid JSON`.
- Validation: 153 Python tests and Vite production build pass.

### v0.9.0-rc.4 — 2026-09-10

- Replaced synchronous OpenCV video seeking for face suggestions with FFmpeg
  frame extraction, fixing empty results on the 4K AV1 YouTube source.
- Face suggestions run as a persistent, clip-scoped `subject-gallery` queue
  job; the inspector can close while it continues. The UI auto-starts it and
  selecting a portrait queues tracking directly.
- The intro title-size field now permits clearing and typing a replacement
  value before committing it on blur or Enter.

## 2026-09-10 — v0.10.0-rc.1

- Default Dựng nhanh flow: suggested subject, reusable reference style, finishing
  options. Existing detailed controls remain reachable via one flat selector.
- Persisted background reference-video analysis with validated caption/Mix/title/
  cue settings and explicit observations for unsupported composition layers.
- Native-source retry for uncertain profile shots, denser bounded observations
  on long camera shots, sharpness-ranked portrait suggestions and a 720×1280
  preview canvas. Gallery cache status distinguishes unscanned from empty.
- Registered bundled subtitle fonts in Docker. Applying a style preserves user
  crop coordinates/mode/zoom and the selected person; no reference text replaces
  the clip's content. Added in-flight apply guard.
- Verified both supplied references, actual background gallery completion across
  panel navigation, template draft application and a decoded 22-second Full-HD
  proof. 159 Python + 6 JS tests pass. See VALIDATION.md for limits and evidence.

## 2026-09-15 — v0.11.0-rc.1

- New `backend/stacked_view.py`: AI-detected "cảnh toàn" (wide, two-person)
  moments are composited into a stacked two-frame portrait — one selected
  person locked top, the other locked bottom, position fixed for the whole
  clip rather than swapped by who is speaking (a deliberate, user-confirmed
  simplification; see active-context.md). Detection is pure geometry over the
  existing SCRFD/ArcFace engine (both selected faces confidently matched,
  small and horizontally separated) — no new Gemini call. Qualifying shots
  get one locked bust crop per person; non-qualifying shots (close-ups) are
  untouched.
- Render (`stacked_view.wrap`) adds a parallel FFmpeg branch off the original
  frame — crop each half, `vstack`, blend a soft gradient across the seam,
  overlay onto the existing crop/Mix output only during detected windows.
  Audio and caption timing are unaffected, same principle as the existing Mix.
- New schema fields `tracking_subject_2` (bottom person) and `stacked_enabled`
  (opt-in toggle). `style_templates.py`'s previously inert `profile.layout`
  field now sets `stacked_enabled` when a learned reference used a
  stacked/mixed layout; it still never selects a subject/identity.
- Frontend: QuickEditor gained a stacking toggle, a second subject picker for
  the bottom person, and a prepare button; MotionPreview and
  `studio-helpers.mjs` mirror the backend geometry for a matching live
  preview using a canvas gradient.
- 169 Python tests (10 new) pass inside Docker with a real ffmpeg, including a
  real-FFmpeg pixel test of the stacked filter graph; 8 JS tests; Vite and
  Docker builds pass. A semi-synthetic real-engine probe (real face crops
  composited into a fixture with a genuine wide-two-shot window) proved
  detection and render end-to-end: exactly the constructed window was found
  and correctly stacked with a clean cut at its boundary. See VALIDATION.md.
  B-roll and complex-motion-layer reproduction remain unimplemented, as before.

## 2026-09-15 — v0.11.0 (accepted stable)

- Fixed a pre-existing Windows-only crash in `scripts/versions.py`: Vietnamese
  status text couldn't be printed on Windows' default console codepage,
  making a successful checkpoint look like a failure. Forced UTF-8 stdout.
- User ran the app for real against a 23-minute 4K source and 4 real clips
  (subject gallery, selected-subject tracking, stacked-view detection all
  completed through the browser). Diagnosed slow processing as CPU-only face
  recognition capped at 2 workers plus a 4-thread render limit, versus this
  machine's 20 CPUs/62 GB/idle NVIDIA GPU; raised local `FACE_ENGINE_WORKERS`
  to 6 and `RENDER_THREADS` to 12 (this machine's `.env` only). GPU
  acceleration for the face-engine was proposed as a further follow-up.
- User explicitly accepted this build as stable. Promoted with
  `scripts/versions.py checkpoint v0.11.0 --accepted`: git tag `v0.11.0`,
  images `talkcut-studio:v0.11.0` / `talkcut-face-engine:v0.11.0`, SQLite
  snapshot recorded. First stable (not just candidate) version in this
  project. See releases.md.
