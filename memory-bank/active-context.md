# Active context — 2026-09-08

## Accepted user intent

Personal tool for Vietnamese business talk shows, local/file/YouTube sources, Docker, Google AI, Full HD vertical output. MISA standards explicitly waived earlier; current request adds MISA logo with tagline, orange #ff7300, Light and Dark mode.

Latest clarification: user confirmed removing BOTH the separate summary card and the long static narration block. Intro becomes a freeze/uploaded photo, short editable title and optional actual-audio karaoke. Narration still plays when intro subtitles are disabled. Optional brand background is a separate upper band, disabled initially to remove the old static frame.

Voice options: prebuilt Google voice or Gemini synthesis directed by age (young/middle-aged/working adult), gender, North/Central/South, news/current affairs/TVC, neutral/cheerful/energetic, 1x/1.2x. The second option uses a base voice with a direction prompt, as AI Motion Studio does; it is not a trained/cloned unique voice. Speed uses atempo to preserve pitch.

Crop must stay stable inside each shot and avoid meaningless center-table/half-face crops. Keep talk continuous through reaction shots. Original camera edits remain; no crossfades that smear faces across unrelated shots.

User authorized creating a private repository named Talkcut and pushing. Repo created at tuannhh/Talkcut. Baseline 7450657 was created locally from the prior delivered application, NOT a confirmed commit on another machine. No known environment B: handoff base remains unconfirmed/null.

## State and caveats

SQLite JSON records and media live in Docker volume; snapshots pre-v2-backup.sqlite and pre-v3-backup.sqlite exist in /data. Source VnExpress is 43:01; primary clip f6b8f14c662b47bea60b8da3eb204ffd, 1510.28–1801.18. Do not delete user sources/exports. Older exported files retain their previous design; re-render to apply the new intro/stable crop.

Focus raw cache remains speaker-shots-v2.2 to reuse costly Google analysis, with derived stable-v3 layout. Scene classification is AI inference; wrong-shot intent and overlapping speech are not guaranteed. Review ambiguous scenes. Intro alignment failures should explain how to retry or disable intro captions rather than fabricate timings.

Runtime generates freeze images with FFmpeg and chooses time samples; crop uses the known focus plan. It does not synthesize imaginary video stills. Long source clips need a ready focus plan for best portrait framing.

## Delivered v3

Implementation commit b914a1b. 102 Python + 4 JS tests passed; actual 302.867-second 1080×1920 export completed as 0edbf27cba1b42c99baad5512a7c3127 (job 8f4a43c6f4384f9ea35f62fce316e4aa). Browser verified real intro playback, optional settings, saved profile/photo/title and both logos/themes. See VALIDATION.md for evidence and limitations. Handoff export remains draft pending user review; code push is authorized.
