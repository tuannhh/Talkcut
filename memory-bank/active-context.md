# Active context — 2026-09-08

## Accepted user intent

Personal tool for Vietnamese business talk shows, local/file/YouTube sources, Docker, Google AI, Full HD vertical output. MISA standards explicitly waived earlier; current request adds MISA logo with tagline, orange #ff7300, Light and Dark mode.

Latest clarification: user confirmed removing BOTH the separate summary card and the long static narration block. Intro becomes a freeze/uploaded photo, short editable title and optional actual-audio karaoke. Narration still plays when intro subtitles are disabled. Latest correction: the uploaded brand background belongs at the bottom, composited over the freeze frame with alpha preserved, as in the MISA News reference. It is not an upper band. Remove the black title backing. Intro captions can be moved above the logo or below the title.

Voice options: prebuilt Google voice or Gemini synthesis directed by age (young/middle-aged/working adult), gender, North/Central/South, news/current affairs/TVC, neutral/cheerful/energetic, 1x/1.2x. The second option uses a base voice with a direction prompt, as AI Motion Studio does; it is not a trained/cloned unique voice. Speed uses atempo to preserve pitch.

Crop must stay stable inside each shot and avoid meaningless center-table/half-face crops. Keep talk continuous through reaction shots. User explicitly requested fade/mix and fewer distracting visual changes. Apply a brief visual blend at observed camera cuts; preserve audio/timestamps. Optional short listener inserts may hold the preceding image.

User authorized creating a private repository named Talkcut and pushing. Repo created at tuannhh/Talkcut. Baseline 7450657 was created locally from the prior delivered application, NOT a confirmed commit on another machine. No known environment B: handoff base remains unconfirmed/null.

## State and caveats

SQLite JSON records and media live in Docker volume; snapshots pre-v2-backup.sqlite and pre-v3-backup.sqlite exist in /data. Source VnExpress is 43:01; primary clip f6b8f14c662b47bea60b8da3eb204ffd, 1510.28–1801.18. Do not delete user sources/exports. Older exported files retain their previous design; re-render to apply the new intro/stable crop.

Focus raw cache remains speaker-shots-v2.2 to reuse costly Google analysis, with derived stable-v3 layout. Scene classification is AI inference; wrong-shot intent and overlapping speech are not guaranteed. Review ambiguous scenes. Intro alignment failures should explain how to retry or disable intro captions rather than fabricate timings.

Runtime generates freeze images with FFmpeg and chooses time samples; crop uses the known focus plan. It does not synthesize imaginary video stills. Long source clips need a ready focus plan for best portrait framing.

## Delivered v3

Implementation commit b914a1b. 102 Python + 4 JS tests passed; actual 302.867-second 1080×1920 export completed as 0edbf27cba1b42c99baad5512a7c3127 (job 8f4a43c6f4384f9ea35f62fce316e4aa). Browser verified real intro playback, optional settings, saved profile/photo/title and both logos/themes. See VALIDATION.md for evidence and limitations. The previous handoff draft is historical documentation, NOT a stable release. Code push remains authorized.

## v4 correction / version workflow

The user clarified handoff means a stable version checkpoint for rollback, then continued development. Do not ask to approve every handoff document or mark an unaccepted build stable. Use release candidates (`-rc.N`) while iterating. Promote a stable tag only after real-media validation and user acceptance. Keep tagged Docker images and SQLite snapshots; rollback app image preserves current media/database by default.

v0.3.0-rc.1 points to 200b2ef and has a local Docker image rebuilt from that exact Git archive. It is a known-issues fallback, not stable. Actual rollback to this image and return to development were exercised, preserving 2 sources, 7 clips and 5 previous exports.

v4 fixes: bottom alpha intro artwork with no black title box; direct sentence/frame textarea editing preserves existing timing anchors (insertions share a nearby interval); original-frame camera cut refinement, brief frame mixing, optional hold of short reaction insert. Source is 25 fps; proxy-only cut at 15.833 was late relative to native cut 15.760. Cache layout calm-v4.2 now stores native cut timestamps and source fps. Main preview has a canvas compositor; final export applies visual filters before ASS, preserving original speech timing.

The first v4 trial render cc7326e77fa54dc38c96bf285f49ec3b was intentionally superseded when native frame drift was discovered; do not retry that old snapshot as acceptance evidence.

Final v4 job a6a26e1d73d54f758ae59b78081a9d49 completed: export 8ef839c948664b1b8e40986c7e1a3d44, 302.367 s, 1080×1920 H.264/AAC, 133747786 bytes. Entire MP4 decoded without errors; HTTP Range 206 verified. Final browser tests covered direct sentence/frame edit → Save with unchanged original timing, then restored original text. 107 Python + 5 JS tests passed. Runtime keeps 2 sources, 7 clips, 6 exports. User voice profile is now female North/1.2x, and selected freeze frame 3; preserve these latest settings. See VALIDATION.md.
