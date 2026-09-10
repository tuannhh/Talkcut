# Architecture and deployment

FastAPI/Python, React/Vite, SQLite JSON records, a single in-process queue worker. FFmpeg renders H.264/AAC 1080×1920; Pillow draws title layers; OpenCV refines faces; Google supplies content reasoning/STT/TTS. Secrets live in `.env`; no new environment variables in this revision.

`schemas.Settings` supplies compatible defaults and removes the summary card even when old records request it. Voice profile is validated server-side. `voice_profiles.instruction` gives one-speaker directions; `narration.synthesize` caches by spoken text, voice/model/mode/profile. `align_display` aligns original display tokens to final audio, after atempo. Numeric expansions remain spoken-only. Display and approved TTS text remain separate.

`focus.cached` enriches reaction shots using a single visible face when possible; it does not label that listener as the speaker. `visual_layout` verifies proxy cut candidates against native source frames; `prepared_track` groups by those camera cuts and locks each shot to a shared face-safe crop center where possible, otherwise applies deadband/smoothing and clamps safe bounds. API returns this prepared geometry, consumed by frontend and FFmpeg. Unknown/b-roll remains full-frame.

`intro_art` creates real freeze-frame assets and a single 9:16 photo canvas. Bottom brand artwork composited with alpha, pan/zoom, separate title/highlight layer; narration is never a static paragraph. `intro-preview` returns server-rendered PNG matching export. `intro-audio` returns audio plus word timings for browser karaoke. Full export burns ASS timed events over the still segment. Caption visibility does not disable TTS.

## Deployment decision

For this user's personal workflow, keep Docker local first: source files remain on disk, no full-source upload to a second server, minimal operations. Google AI still requires network/API usage. Performance depends on allocated CPU, media resolution and source download; Docker alone does not accelerate inference.

A VPS with persistent SSD is the simplest next step for a shared/always-on worker. Add authentication, HTTPS, allowed-origin configuration, backups and job recovery. Current local-only origin guard is intentionally incompatible with an arbitrary public domain.

Cloud Run is feasible after separating web API from render jobs and externalizing state: Cloud Storage for media, external DB, durable queue/job dispatch. Do not deploy the current local volume + SQLite + daemon worker unchanged. Its writable filesystem consumes RAM and disappears on stop; service CPU allocation depends on billing. Cloud Run Jobs supports longer render tasks (CPU task timeout up to 7 days), but that does not make local state durable.

Sources verified 2026-09-08:
- https://docs.cloud.google.com/run/docs/container-contract
- https://docs.cloud.google.com/run/docs/configuring/task-timeout
- https://ai.google.dev/gemini-api/docs/speech-generation

## v4 visual pacing and releases

`transitions.visual_filters` converts to 30 fps with upward timestamp rounding, optionally holds a brief listener insert using select + fps, and mixes a small frame window at camera cuts. A clean branch preserves PTS; tmix is buffered continuously and its overlay enabled only at transitions (tmix disabled output can use older timestamps). ASS is added afterward, so words stay crisp and audio remains unchanged. Native source FPS determines hold thumbnail time; taking the previous 30 fps frame from a 25 fps source could otherwise select the incoming listener by mistake.

`MotionPreview` draws the same prepared crop and short holds into a canvas, mixing recent frames near the same cuts. Browser performance and display cadence can differ from the encoded file; the MP4 is acceptance evidence. `editTimedGroup` preserves measured intervals; it never divides a row duration into invented timings.

`scripts/versions.py` manages local checkpoints and app-image rollback. `compose.yaml` accepts TALKCUT_IMAGE; `.active-image` keeps start.sh on a selected checkpoint. Development checkout stays intact during image rollback. `.releases` stores local image/commit/snapshot metadata and is ignored by Git. No automatic restoration of old SQLite over new edits. Before future breaking DB migrations, define an explicit restore/migration path.

## v5 portrait, Mix and presets

The current user request supersedes old automatic fit/letterbox fallbacks. `geometry` and prepared tracks retain 9:16 crop, refine available faces, and preserve same-shot anchors. Explicit legacy `fit` API input remains compatible, but is no longer offered in the UI. Extremely close source portraits may exceed a vertical crop's width; no invented image area is synthesized.

`visual_preview` is a cached local face-detection pass at low sampling rate while audio-aware AI runs. It never marks a face as the confirmed speaker. `get_focus` returns this as `preview_plan` separately from final `plan`, so it cannot suppress the real analysis job. Raw cache version stays v2.2; derived camera/portrait layout is `portrait-v5.1`, including transcript speech turns for conservative short-angle holds.

`transitions` uses select + fps to retain an outgoing frame, then normal blend opacity. Output-side sendcmd drives a linear Mix per cut; upstream commands were rejected by tests because frame prefetch could apply future opacity early. A bounded tail pad covers cuts near the end; shortest framesync preserves the original timeline. Native source timing still defines crop boundaries. Browser canvas uses the same cuts/holds and linear opacity. Documentation: https://ffmpeg.org/ffmpeg-filters.html#blend and https://ffmpeg.org/ffmpeg-filters.html#sendcmd_002c-asendcmd (checked 2026-09-08).

`backend/presets.py` strips content-specific fields and validates referenced assets. `/api/presets` stores durable records in SQLite. Applying returns merged settings for review in the current editor; Save persists to that clip. It does not mutate other clips or include their transcript/timing. Presets use existing assets in the same Docker volume; relocating to another machine requires the normal volume backup.

Rollback compatibility: v5 persists new `mix_seconds` (0–1.2s), while the legacy `transition_seconds` stays within v4's 0–0.5 range. This lets the previous image open the same records without validation errors. The initial internal v5 RC used the old field for longer values; RC.2 separates the fields and normalizes these records without changing the intended Mix duration.

## v6 geometry and Intro layers
`face_tracking` adds frontal/profile/mirrored-profile geometry matched to the AI speaker anchor by position and scale. Geometry cache `face-v6` upgrades observations without invalidating AI transcription, native visual cuts or Mix settings. `camera_points` ignores boundary-adjacent anchors from both sides before the existing face-safe shot lock. Focus GET supports validated draft zoom; cosmetic edits no longer cancel its load.

`photo_card` retains upload alpha and composites transparent portrait-slot artwork over a source-specific first frame. The saved base and transparent title PNG reconstruct the exported still pixel-for-pixel. Browser transforms the title layer during drag and only updates settings after pointer release. Title formatting is rendered by Pillow using matching DejaVu font variants; underline/justified spacing are drawn explicitly. Legacy intro preview remains supported without separate layers.

## v7 fixed subject
`static_framing` reads an existing camera cache without invoking AI or refining faces. Its prepared keyframes contain only fixed user centers at camera/lock boundaries. All points are discontinuous boundaries, so no tracking interpolation occurs. Explicit locks override the baseline only within their absolute source-time ranges. Rendering, freeze-frame generation and the preview use the same bounds/clamping. Static preview POST accepts draft settings and renders hold thumbnails using those settings. Auto analysis is explicitly initiated rather than started simply by loading a clip.

SubjectPicker shows the original source video with a 9:16 crop rectangle, coordinate sliders, frame-time scrubber and scope selection. Selecting a face does not claim biometric identification; it fixes the requested crop center. Underlying movement in source footage is retained. Crop positions and lock ranges are content-specific and excluded from channel presets.

## v8 selected-subject tracking

`TrackingSubjects` presents local face samples from the current clip. The selected sample is content-specific and is excluded from presets. `subject_tracking` divides the source into native camera shots, samples local faces, and uses bundled OpenCV SFace embeddings to compare each local face with the selected portrait. A shot is locked to one feasible crop center; there is no left-right camera drift while that person remains inside the face-safe region. Gemini is not trusted for face coordinates in this flow.

The threshold deliberately abstains on profile, occlusion, or ambiguous two-person frames. `reference_holds` then replaces that visual interval with a verified portrait still while original audio and timed captions continue. Preview and FFmpeg export use the exact same holds and geometry. This is an appearance match scoped to the source video, not identity verification or active-speaker recognition.

`get_focus` now returns immediately when no prepared plan exists, instead of doing a synchronous low-resolution whole-video scan. The editor presents an explicit preparation state. The title renderer bundles Google Sans, Open Sans, Barlow and Roboto; its font selection is rendered by the same Pillow code used by preview and export.

## Future distribution decision — 2026-09-09
Retain Docker for the no-tech Windows installer. A bootstrapper installs/checks Docker and WSL, loads the prebuilt TalkCut Linux amd64 image, starts the service and opens first-run Gemini API key setup. Runtime dependencies stay inside the image. Build only after stable acceptance; see [distribution plan](distribution.md).

## v9 local face engine — 2026-09-10

For user-selected subjects, `face-engine` is a private Docker-network service
rather than a browser or Google API feature. It uses SCRFD 10G face detection,
five-point alignment and ArcFace r50 embeddings. The Python editor submits
still frames to it only in the background focus job. It accepts a local face
only when its cosine score and lead over the next candidate meet strict video
thresholds. This is appearance matching within one source, not active-speaker
verification or a global person database. The ONNX models download to the
persistent local Docker volume on first use; two workers are the default to
reserve CPU for FFmpeg and web preview.

`scripts/versions.py` checkpoints Studio and face-engine images together. A
rollback cannot silently load a newer recognition engine; `.active-image`
derives the matching face-engine tag for `start.sh`.

## v10 reference templates

`style_templates` defines a bounded Pydantic profile, uses an 8fps/480px H264
proxy with audio (2–180 seconds, <=18MiB) in Gemini, and maps only implemented
settings. `/api/style-templates` uploads, lists, retries and applies profiles;
`style-template` queue work persists across tab changes. Reference content,
logos and identities never overwrite clip content. `sound_effects` synthesizes
short local cues. ASS renders optional opening text from the current clip title,
while existing word timestamps drive captions; bundled fonts are registered in
fontconfig. QuickEditor keeps existing detailed editors available, and shows
unimplemented profile observations separately from applied settings.
