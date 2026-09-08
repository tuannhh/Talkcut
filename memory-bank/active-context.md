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

## v5 current user correction

User requires full vertical crop for other clips too, section-specific settings (Intro/Main/Outro), reusable presets, and one softer/longer Mix. This supersedes the historical automatic letterboxing fallback. Main auto mode stays portrait; uncertain visual shots retain their kind label instead of being silently labelled a speaking person. Provisional visual-only portrait preview is separate from confirmed focus and does not skip Google analysis.

v5 adds SQLite preset CRUD, a four-section inspector with main subtabs, .65-second linear Mix (up to 1.2s), short same-voice angle holds and reaction holds. Clip 1 now has 50 Mix boundaries instead of 60 original cuts; clip 3 is all-portrait. Preset `12442d0b812d4b7e9d2cdada420a328a` / `MISA News · Dọc 9:16` was created from clip 1. Cross-clip application verified through UI; clip 3 was restored after test. Keep preset and source/clip/export data. pre-v5-backup.sqlite exists; v0.4.0-rc.1 remains a known-issues rollback checkpoint, not accepted stable.

113 Python + 5 JS tests passed. Actual 22s crop/Mix proof for clip 3 is outside Git at ../talkcut-v5-clip3-preview.mp4. See VALIDATION.md for full evidence. Current derived layout is portrait-v5.1; older calm-v4.2 notes above describe history.

Final v5 render job 57daddb8270c43b59298bc288cdb7e80 completed as export 1d053b99ed124cfb9366d3231462ff28: 302.367s, 1080×1920 H.264/AAC, 138678431 bytes. Full decode and range download passed. Main remains exactly 8727 frames / 290.9s. File ../talkcut-v5-fullhd.mp4. Old exports remain unchanged; select the new export to review Mix. No stable acceptance yet.

Final candidate is v0.5.0-rc.2, with new mix_seconds storage preserving the older transition_seconds range so v4 rollback can read current records. v0.5.0-rc.1 is an internal pre-compatibility checkpoint. Final suite: 114 Python + 5 JS.
Rollback to v0.4.0-rc.1 was exercised after normalization: all 7 clip GETs returned 200. Returned to v5 with mix .65 and all 2 sources / 7 clips / 7 exports / 1 preset intact. Data was not reverted.

## v6 — focus and transparent Intro correction (2026-09-08)
User accepted the v5 Mix transition. Preserve its timing/holds; only face geometry and editor bugs changed. Candidate v0.6.0-rc.1, not a stable handoff. Existing data and presets retained.

Fixed cosmetic dirty-state cancellation of focus loading. Zoom requests receive prepared shot geometry. Local frontal + mirrored profile detection refines audio-aware speaker anchors, rejecting small false positives. Camera-point grouping excludes model anchors within 180 ms of either side of a native cut to prevent the next shot pulling the previous crop. Existing camera cuts/holds remain unchanged.

Transparent PNG selected in the portrait-image slot now composites over the same clip's freeze frame (verified supplied testframe.png has alpha=0 at top). Generated stills from a different source/trim are not used as this clip's frame. Preview has separate base/title PNG layers; pointer movement transforms the title locally, persisting position on pointer-up. Added size, left/center/right/justify, bold/italic/underline; defaults remain compatible with older checkpoints and presets.

Evidence: 119 Python + 5 JS tests, Docker build, browser dirty draft at clip1 02:48 focused on right speaker, clip2 transparency/toolbar/drag verified. Full-HD 18-second crop/Mix proof exported and decoded. No full five-minute v6 export was requested/created; earlier exports remain historical. Face tracking is still heuristic with audio-aware AI anchors, not guaranteed biometric speaker identification in every shot.

## v7 — explicit fixed subject (2026-09-08)
User rejected further automatic crop drift for seated/standing subjects. Added explicit `Chủ thể cố định` and relabelled auto as `AI tracking · người di chuyển`. Fixed mode never uses face motion: user chooses a center on the original source frame, for a known camera shot, custom source-time interval, or whole clip. Unconfigured intervals use the explicitly displayed global center. Existing clip settings remain intact; new AI-suggested clips start in fixed mode. Merely opening an old auto clip no longer queues new paid tracking analysis; the preparation action remains available.

`crop_locks` and vertical center are additive fields under legacy `manual` mode, preserving v6 schema compatibility. Locks use absolute source seconds and last-edit precedence; no interpolation. Presets exclude subject coordinates/ranges. Cached camera cuts preserve existing Mix/short-hold behavior, while newly selected interval boundaries can Mix to the next fixed position. Without a cached camera plan, the picker offers whole clip/custom range, without requiring AI analysis.

Validated 126 Python + 6 JS tests, actual browser selection of the right speaker for 1677.88–1682.12 source seconds, and decoded 1080×1920 fixed-shot proof ../talkcut-v7-locked-subject.mp4. Runtime now has 3 sources/9 clips/7 exports/1 preset from user activity. Snapshot pre-v7-backup.sqlite retained. v0.7.0-rc.1 is a candidate, not stable. Do not overwrite existing drafts or old exports.
