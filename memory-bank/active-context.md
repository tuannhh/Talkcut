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

## Button colors — 2026-09-08
Latest user instruction replaces orange button fills with #0086ff and white #ffffff labels in Light and Dark mode. Action buttons, icon actions and active segmented choices share CSS button tokens; inactive choices, color swatches, video styling and MISA logos retain their semantics. Docker/Vite build and browser computed colors verified in both themes, including disabled actions. Patch candidate v0.7.1-rc.1; no stable acceptance implied.

## Packaging direction accepted — 2026-09-09
User explicitly chooses a single installer orchestrating Docker/prerequisites, then Gemini API key onboarding with Internet available. Finish and accept a stable app first; do not start packaging yet. Python/FFmpeg/Node remain inside a prebuilt image, not separate host installs. See distribution.md for install/reboot flow, Windows amd64 validation and provisional 16 GB minimum / 32 GB recommended system targets. These are engineering targets pending Windows benchmarks. No stable acceptance or runtime change in this documentation update.

## v8 — selected face tracking / title fonts — 2026-09-09

The user reported that both auto-tracking and fixed screen coordinates fail across wide/close camera angles. v8 introduces choosing a face sample from the current clip, then compares only locally detected candidate faces against that selected portrait with bundled OpenCV SFace. This supersedes trusting Gemini bounding boxes, which were observed to drift to the interviewer in real two-person shots. Low-confidence or undetected profile/occluded shots deliberately become portrait holds marked for review; they must never default to the table or unrelated person. This is source-scoped appearance matching, not identity or active-speaker verification.

The primary VnExpress regression clip `f179175fe81b47079707ce5af7cf3fed` (493.98–654.38) was re-analysed with the male glasses reference. It produced 34 camera shots, 17 conservative holds. The prior false female crop at +81s is now an uncertain hold. A 30-second Full-HD 9:16 proof was rendered, decoded without errors, and at +9s displays the selected male portrait through a missing/ambiguous angle. Full existing user data remains untouched. v0.8.0-rc.1 will remain an RC until the user confirms this behavior in the running editor.

## v9 — SCRFD + ArcFace selected-face tracking — 2026-09-10

The user authorized reusing the proven local face-matching pipeline from
`/Users/tuanbui/misa-tim-anh-ai`. TalkCut now runs an independent local
`face-engine` Docker service: SCRFD 10G detects faces and five landmarks;
ArcFace r50 creates a 512-value source-scoped appearance descriptor after
alignment. The editor, API, SQLite data and UI remain independent from the
photo-search project.

One or two still frames are checked per native camera shot, not every 1.5
seconds. The two-worker background pass keeps preview requests free of ONNX
work. A match needs a conservative cosine score and a lead over the next face.
Ambiguous or missing shots remain verified portrait holds; they cannot become
a table, microphone, or other participant crop.

The 60-second VnExpress regression probe (source 540–600s, selected guest
wearing glasses) produced 14 camera shots, 11 selected-subject shots and 3
portrait holds. Wide-camera detections correctly moved to the guest at x≈.80;
the selected close-camera portraits stayed x≈.51. Candidate `v0.9.0-rc.1`
awaits user review; it is not a stable handoff.

## v9 RC.2 — high-resolution YouTube and moving ambiguous shots — 2026-09-10

The user accepted the SCRFD/ArcFace tracking behavior, then reported soft
YouTube image quality and occasional frozen visuals while voice and captions
continued. The test source `G5vFOYti6QA` had been imported as 640×360 despite
an available 4K stream. YouTube import now prefers a 2160p MP4 stream and
keeps compatible MP4 media as the editor preview instead of building a 1280px
proxy. “Tải lại bản sắc nét” downloads a sibling file, only switches after
probe success, and preserves transcript/clip configuration.

Selected-subject plans no longer insert portrait JPEGs or short-shot holds.
An ambiguous camera angle retains a confirmed crop anchor while the source
video, voice and subtitles continue moving; it remains marked for review.
The cache namespace is `reference-v5-dynamic`, so an old portrait-hold plan
cannot be reused. The current test source is upgraded to 3840×2160 AV1 while
the old 640×360 file remains in the Docker volume. Candidate `v0.9.0-rc.2`
awaits user review and is not a stable handoff.

## v9 RC.3 — reliable focus reload — 2026-09-10

The selected-face finder itself completed successfully, but reloading the
prepared focus plan could fail with HTTP 500 when an ordinary (non-reference)
plan contained a short reaction hold. RC.2 had removed the image helper used
only by that legacy path. RC.3 restores it while selected-subject plans still
return no holds and therefore never replace moving footage with a JPEG. The
browser now converts any unexpected non-JSON error response into a concise
Vietnamese message instead of exposing a JSON parser exception. Candidate only;
no stable acceptance or handoff yet.

## v9 RC.4 — background face suggestions — 2026-09-10

The 4K AV1 test source exposed that OpenCV cannot seek its frames reliably,
which made the old synchronous face gallery return an empty list even when a
clear face was visible. Face suggestion now extracts only nine FFmpeg-decoded
stills inside the selected proposal, then uses the existing local engine to
offer up to six clear, distinct portraits. It is a persistent background job,
so leaving the inspector/tab does not cancel scanning; completed results remain
available for that clip. Choosing a portrait saves it and queues tracking in
one action. Intro title-size accepts typed replacement values on blur/Enter.
Candidate only; no stable acceptance or handoff yet.

## v10 — reference styles and simpler editing — 2026-09-10 (candidate)

Latest request: study the two supplied TikTok videos, improve framing, learn
reusable styles, and simplify the editor for nontechnical users. Correct
reference checkout is `/Users/tuanbui/Documents/Codex/2026-09-07/hi-n-nay-tr-n-facebook/outputs/ai-motion-studio-next`.
Its bounded profile/video-analysis approach was reviewed read-only. The first
sample uses a stable single portrait and compact dark-box captions; the second
frequently stacks two camera views and inserts illustrative footage. These are
different layouts, not simply different zoom strengths.

Dựng nhanh is the default inspector: choose a suggested face, learn/apply a
reference style, then optional finishing edits. All prior detailed editors are
available through a flat selection and a return button. Learned styles persist
in SQLite and analysis runs in the background queue. Analysis receives a
bounded full-video proxy with audio; the original stays local. Supported style
mapping includes captions, Mix, a main opening title using the NEW clip title,
and a synthesized opening sound cue. Stacked view, illustrative footage and
complex motion layers are recorded as observations but are explicitly not
claimed as automatically reproduced. Existing channel presets remain available.

Selected-face tracking now samples long shots more densely and retries missing
shots at two native-source 1440px stills before abstaining, without lowering
appearance thresholds. Stable shot locking remains; no portrait freezes.
Gallery ranks face sharpness as well as size. Preview canvas increases from
360x640 to 720x1280. No stable handoff until user acceptance.

v10 verification completed: both supplied references are ready in the local
library; a 20s 4K tracking probe found the selected person in all 3 shots without
holds. The 22.034s final proof includes test intro/music fixtures plus actual
caption timing/title/Mix/watermark/cue. `../talkcut-v10-preview.mp4` is reviewable.
Browser template application was tested as an unsaved draft; stored settings
were not changed. Background face scanning completed after leaving its panel
(5 portraits). Final checks: 159 Python + 6 JS, Vite and Docker builds. Candidate
v0.10.0-rc.1 remains pending user acceptance; stacked/B-roll/complex animated
composition is still not implemented. Do not describe template learning as full
reconstruction. User requested finishing interrupted work; browser file chooser
hung previously, so reference uploads were verified through API instead.

## v11 — stacked two-frame composite — 2026-09-15 (accepted stable, v0.11.0)

User asked to implement the "stacked" part of the still-unimplemented v10
observations first (B-roll and complex motion stay unimplemented/out of scope
for this request). Two new sample TikTok clips were inspected frame-by-frame
(via OpenCV, no ffmpeg on this Windows host): the stacked reference keeps one
person on top and the other on bottom for its entire 145s duration regardless
of who is talking, not swapped per speaking turn. Given that evidence, the
implementation uses a **fixed top/bottom assignment by chosen face**, not a
per-moment speaker/listener swap — a deliberate simplification from the user's
literal wording ("người nói và người nghe"), chosen to avoid fragile
cross-modal (visual identity ↔ audio diarization) speaker attribution the
project's own conventions warn against inventing. This was not re-confirmed
with the user before implementing; flag it for review.

Added `backend/stacked_view.py`: reuses the existing SCRFD/ArcFace engine and
per-shot sampling pattern from `subject_tracking.py`. A shot counts as a
"cảnh toàn" (wide two-person shot) only when both selected faces are
confidently matched simultaneously AND both are small/separated enough
(`wide_two_shot`, pure geometry, no new Gemini call). Qualifying shots get one
locked representative crop per person (`half_geometry`, a tighter 9:8 bust
crop than the normal single-subject crop). Render (`stacked_view.wrap`) adds a
parallel FFmpeg branch — split the original frame, crop each half, `vstack`,
blend a soft dark gradient across the seam, overlay onto the existing
crop/Mix output only during detected windows (`enable=between(t,a,b)`) — audio
and caption timing are untouched, same principle as the existing Mix. New
schema fields `tracking_subject_2` (bottom person) and `stacked_enabled`
(opt-in toggle). `style_templates.py`'s previously-inert `profile.layout`
field now sets `stacked_enabled` when a learned reference used a
stacked/mixed layout (still never selects a subject/identity).

Frontend: `QuickEditor` step 1 gained a "Ghép khung chồng khi quay cảnh toàn"
toggle, a second `TrackingSubjects` picker (bottom person), and a prepare
button calling new `POST/GET /clips/{id}/stacked`. `MotionPreview` and
`studio-helpers.mjs` (`stackedGeometry`, `stackedWindowAt`) mirror the backend
math for a matching live preview, using a canvas gradient instead of the
backend's generated PNG (no shared asset dependency needed for preview).

The fixed-position design was explicitly confirmed with the user afterward:
they agreed it matches the reference video's actual behaviour, and separately
re-emphasized the OTHER core requirement — stacking must only replace the
close-up crop during AI-detected wide/two-person moments, never for a whole
clip, and a clip with no qualifying wide shot must render exactly as before.
That was already the implemented design (`wide_two_shot` + `assemble`'s
per-shot qualification + `wrap`'s `enable=between(...)` gating), so no code
change was needed from that confirmation.

Docker (freshly reinstalled by the user this session) came up after a machine
restart. Full validation: 169 Python tests pass **inside the `studio`
container with real ffmpeg** (previously 10 of these could only run natively
on Windows with ffmpeg absent), 8 JS tests, Vite and Docker builds. A
semi-synthetic real-engine probe (real face crops from the two reference
videos, composited into a 12s fixture with a genuine wide-two-shot segment)
proved the full pipeline end-to-end through the real SCRFD/ArcFace engine and
real FFmpeg render: gallery scan found both distinct faces; stacked detection
returned exactly the constructed `[3.0, 9.0]` window with correct top/bottom
tokens and no false positive on the two close-up thirds; the rendered export
showed a clean hard-cut into a correctly stacked, gradient-seamed composite
exactly at the window boundary, and ordinary single-crop framing outside it.
See `VALIDATION.md` (`v0.11.0-rc.1`) for full detail and remaining limits —
notably, no genuine (non-synthetic) two-person camera footage was available
on this machine to probe, and `half_geometry`'s bust-crop headroom constants
still await a visual pass against real frontal (not just profile) footage.
Test data was created and then fully deleted from the Docker volume; it holds
no leftover clips/sources from this probe. Not yet done: browser/UI
verification of the new QuickEditor controls and live preview, and a
multi-minute render combining captions with the stacked composite.

After that, the user ran the app themselves with a real 23-minute 4K
(3840×2160) YouTube source ("AIforAi#01…") and 4 real clips (148–298s each):
real subject-gallery scans, real focus/selected-subject tracking, and a real
stacked-view detection job all completed successfully through the browser UI.
They asked about processing speed feeling slow. Diagnosis: the face-engine's
ONNX sessions are CPU-only (`onnxruntime-node`, no GPU execution provider
configured) and hard-limited to `FACE_ENGINE_WORKERS=2` workers of
`intraOpNumThreads:1` each; `RENDER_THREADS` defaulted to 4 — on this
particular machine (20 CPUs, 62 GB RAM, an idle NVIDIA GPU with CUDA 12.6 and
the `nvidia` Docker runtime already available), that leaves most of the
hardware unused. Bumped this machine's `.env` to `FACE_ENGINE_WORKERS=6` and
`RENDER_THREADS=12` and recreated the two containers (no job was running; all
data survived). GPU acceleration for the face-engine was raised as a bigger,
separate follow-up (real onnxruntime/CUDA-driver compatibility work, not
attempted) — not done, offered but not requested yet.

The user then reviewed the resulting behavior and explicitly accepted this
build as stable: "Bản này tôi thấy là ổn rồi" (this version looks good to
me). Promoted via `scripts/versions.py checkpoint v0.11.0 --accepted`,
which also fixed a pre-existing Windows-only crash in that script itself
(Vietnamese console output crashed on Windows' default codepage after the
real checkpoint work had already completed — cosmetic only, fixed by forcing
UTF-8 stdout/stderr). This is the first version in this project accepted as
stable — see `releases.md` for the checkpoint record and rollback command.

## v12 (candidate) — opt-in NVIDIA GPU acceleration, verified on real hardware — 2026-09-19

Follow-up to the GPU offer raised (not attempted) at the end of v11: the
user separately asked, in a fresh session working in the sibling
`Talkcut - GPU` checkout, to develop a version that actually exploits
2GB/4GB/6GB/8GB VRAM GPUs instead of running everything on CPU. Built as a
fully additive, opt-in track — the default `Dockerfile`/`Dockerfile`
(face-engine)/`compose.yaml` are untouched, so a machine with no GPU (or a
user who never runs the overlay) behaves exactly as v0.11.0 always did.

New files: `Dockerfile.gpu` (studio), `face-engine/Dockerfile.gpu`,
`compose.gpu.yaml`, `backend/gpu_profile.py`, `face-engine/gpu.js`. Edited
(additively, `auto`-gated): `backend/config.py`, `backend/media.py`
(`hwaccel_input_args()`, NVENC branch in `encode_args()`), the `-i <source>`
call sites in `editor.py`/`focus.py`/`subject_tracking.py`/`stacked_view.py`/
`style_templates.py`/`intro_art.py` that decode the original (often 4K)
source — including the exact "native-resolution retry" path
(`subject_tracking.py`'s "Đang kiểm tra góc khó ở ảnh gốc") the prior session
identified as decode-heavy on 4K sources. Face engine: `face.js` now builds
a CUDA execution provider list (with a try/catch fallback to CPU if the
provider fails to load — a broken driver must never take the engine down);
`pool.js` auto-tiers `FACE_ENGINE_WORKERS` by detected VRAM (2GB→2, 4GB→4,
6GB→6, 8GB→8) and splits detected VRAM across workers via
`FACE_ENGINE_GPU_MEM_LIMIT_MB` unless the user sets these explicitly.

This machine turned out to actually have an NVIDIA GPU (RTX 3050, 8GB VRAM,
driver 560.94) plus Docker Desktop with the `nvidia` runtime already
registered, so the whole thing was built and verified for real instead of
being handed over untested:

- `docker build -f face-engine/Dockerfile.gpu` (base
  `nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04` + Node 24) succeeded;
  `libonnxruntime_providers_cuda.so` (343MB) ships inside
  `onnxruntime-node@1.26.0` itself, no extra install step needed. Running
  the container with `--gpus all` logged correct auto-detection (`GPU NVIDIA
  GeForce RTX 3050 (8192 MB VRAM) detected, 8 worker(s), ~870 MB
  VRAM/worker`). A real `/v1/describe` call against a standard CV test image
  (Lena, downloaded for this test only) returned a real detected face
  (score 0.6892) and a 512-value embedding; GPU memory usage jumped from
  idle to **5.7GB/8GB** during the call, confirming genuine CUDA execution,
  not a silent CPU fallback.
- `Dockerfile.gpu` (studio) first tried a prebuilt static ffmpeg (BtbN's
  "latest" GPL release). That failed for real on this machine: "Cannot load
  libnvidia-encode.so.1 ... minimum required Nvidia driver is 610.00 or
  newer" against the installed 560.94 driver — a genuine instance of the
  exact "driver/version compatibility" risk flagged (but not investigated)
  in v11. Fixed by building ffmpeg from source (`n7.1`) against an older
  pinned `nv-codec-headers` (`n12.1.14.0`, min driver ~530.41), trading the
  newest NVENC features (e.g. AV1) for compatibility with a much wider range
  of already-installed drivers — the right tradeoff given 2-8GB cards in the
  field may not have the newest driver. After that fix, a real `h264_nvenc`
  encode (and the full `backend.media.ffmpeg()` path: `-hwaccel cuda` decode
  of a synthetic 4K source → scale/pad to 1080×1920 → `h264_nvenc` encode →
  AAC audio, run as the non-root `studio` user, matching the real
  `editor.py` main-render call shape) succeeded and produced a valid
  1080×1920 H.264/AAC file. One real gotcha hit and resolved along the way:
  `docker run --gpus all` alone does **not** mount `libnvidia-encode.so`;
  `NVIDIA_DRIVER_CAPABILITIES` must include `video` (already set correctly
  in `compose.gpu.yaml`, just missing from an ad-hoc manual test command).

Usage: `docker compose -f compose.yaml -f compose.gpu.yaml up -d --build`.
`RENDER_ACCEL`/`FACE_ENGINE_ACCEL` default to `auto` (GPU only when actually
detected). See the new README section and `.env.example` for the full
variable list. Not yet done: no real multi-minute talk-show render was
exercised end-to-end through the actual `/api` job queue (only the
lower-level `backend.media` functions and a synthetic source were
exercised directly); the existing `tests/test_core.py` suite was re-run
natively on this Windows host and is unchanged (22 passed / 3 failed on
missing native ffmpeg/ffprobe on PATH — pre-existing, unrelated to this
work, ffmpeg only exists inside the Docker images). No git commit/tag was
made; this is implementation + hands-on verification only, pending the
user's own review in the running app.

## v13 (candidate) — merged CPU/GPU tracks into one auto-detecting image + in-app toggle — 2026-09-21

User asked to merge the two separate tracks from v12 into a single build
that auto-detects an NVIDIA GPU at runtime and either self-tunes for it or
falls back to CPU-only, plus a UI switch that only appears when a GPU is
actually present. The two-Dockerfile split from v12 is gone:
`Dockerfile.gpu` (studio) and `face-engine/Dockerfile.gpu` were deleted;
their content was folded into the single `Dockerfile` / `face-engine/Dockerfile`
that every machine now builds. `scripts/start.sh` runs
`nvidia-smi` + `docker info | grep nvidia` and adds the `compose.gpu.yaml`
overlay only when both succeed; running `docker compose up` directly (no
overlay) still works and is CPU-only, matching the pre-v12 default exactly.

Runtime toggle: `backend/accel_settings.py` is a new SQLite-backed singleton
record (`auto|cuda|cpu`) read by `backend/media.py`'s `_resolved_render_accel()`
in place of the old fixed `RENDER_ACCEL` env var (env var is still the
default when no override is set). `GET/POST /api/accel` (`backend/app.py`)
exposes detected GPU/VRAM tier, ffmpeg capability flags, current mode, and
face-engine status (new `face.js`/`pool.js`/`server.js` `/status` chain).
The frontend settings modal (gear icon → "Tăng tốc phần cứng" in
`frontend/src/main.jsx`) renders three buttons (auto/cuda/cpu) that call
this endpoint live, no container restart needed — but the whole section is
conditionally rendered only when `accel.gpu` is non-null, so a CPU-only
machine never sees a GPU control at all. Face-engine acceleration
(`FACE_ENGINE_ACCEL`) stays read-only in this UI (status text only): live
CUDA/CPU switching would require reloading ONNX sessions across worker
threads, judged not worth the complexity for this pass.

Two real bugs found and fixed while merging, both in
`face-engine/Dockerfile`: (1) installing the full `nvidia/cuda:*-cudnn-runtime`
base pulled NCCL/cuSOLVER/cuSPARSE/NPP/nvJPEG that onnxruntime never uses;
switched to installing only the exact libs `ldd` showed as actually linked
(`cuda-cudart-12-6 libcublas-12-6 libcufft-12-6 libcurand-12-6 libcudnn9-cuda-12`
via NVIDIA's apt repo), cutting the image from 7.85GB to 6.1GB. (2) a
`chown -R engine:engine /engine /data` run *after* `npm ci`/`COPY . ./`
forced overlayfs to copy up ~600MB of already-written files (mostly
onnxruntime-node's bundled CUDA `.so`s) into a new layer, duplicating them;
fixed by creating the user and switching to `USER engine` *before*
installing/copying anything and using `COPY --chown=` instead, bringing the
image down to **5.14GB** (confirmed by rebuild, tag `talkcut-face-engine:merged2`).

Verified for real on the same RTX 3050 (8GB, driver 560.94) machine as v12:
built the merged root `Dockerfile` (ffmpeg-from-source, ffmpeg/ffprobe copied
into the `python:3.12-slim-bookworm` final stage — 1.32GB), ran the full
stack with the `compose.gpu.yaml` overlay, confirmed `GET /api/accel`
correctly reports the GPU/tier/capabilities, exercised `POST /api/accel`
switching `cuda→auto` both via curl and by clicking the actual UI buttons in
a browser (`aria-pressed` state and the persisted `render_accel` in the
response both updated correctly), and confirmed the toggle is fully absent
in the JSX unless `accel.gpu` is set. Not yet done: no test of the
auto-detection branch on an actual GPU-less machine (only inspected the
`scripts/start.sh` logic; the dev machine always has the RTX 3050 present).

Committed and pushed to `origin/main` after the user approved (studio merge =
`1b295a5`, macOS plan doc = `37738b6`).

Regression found in user testing after that push and fixed: the `analyze`
pipeline (`pipeline.py` extracts `audio-*.mp3` for Google STT) failed with
"Default encoder for format mp3 ... Encoder not found". The from-source
ffmpeg was configured without libmp3lame — Debian's packaged ffmpeg (used by
the pre-merge CPU image) shipped MP3 encode, so this only surfaced once the
merged image replaced apt-ffmpeg with the source build. Fixed by adding
`libmp3lame-dev` + `--enable-libmp3lame` (build stage) and `libmp3lame0`
(runtime) to the root `Dockerfile`. Verified by running the exact
`pipeline.py` extraction command inside the rebuilt container against the
real source: valid MP3 (mp3/16kHz/mono) produced, no Gemini credits spent.
Audited every other ffmpeg external-lib dependency the backend uses at the
same time — x264/libass/zlib/aac all present, all other filters are built-in,
no `drawtext`/libfreetype needed — so libmp3lame was the only gap.

## Review-feedback polish pass — 2026-09-21

User reviewed a real rendered clip and gave six items. Done + verified this
pass (all on a real render/stack): (1) failed job rows no longer dump raw
ffmpeg stderr — they show a friendly Vietnamese line, and a dismiss (X) button
(`DELETE /api/jobs/{id}`, blocks queued/running) lets stale failures be
cleared; (4) render progress is now real, streamed from ffmpeg via a new
`media.ffmpeg_progress()` (`-progress pipe:1`, defensive fallback) wired into
the two long encodes in `editor.render` (main 42→64, final mux 78→94) —
verified the bar moved 45→63 then 79→93 on a live render; jobs also store a
`started` epoch so the UI shows a bigger % plus an ETA (`etaText` in
main.jsx); (6) exports have a delete button → `DELETE /api/exports/{id}`
(removes the DB record, the final.mp4, and the whole disposable render folder;
verified file+folder gone); (3a) the stacked-view seam was too faint — mask
regenerated as `stacked-seam-mask-v2.png` with a fully-opaque central plateau
(was peak 235 falling off from centre), SEAM_HEIGHT 220→300, blur 26→40.

Diagnosed, NOT yet fixed (need a re-render + the user's eyes, so deferred):
- (2) "đứng hình" freezes: the pacing holds. freezedetect on the user's
  exported clip flagged a clean 2.0s frozen span matching
  `transitions.py`'s Mix `tpad=stop_mode=clone:stop_duration=2`; also
  `calm_short_shots` holds up to `calm_max_seconds` (default 4s). Likely the
  fix is shortening these, but must verify visually.
- (3b) stacked "some clips yes, some no": data-grounded — several clips have
  `stacked_enabled=True` but are missing one of the two subjects
  (`tracking_subject`/`_2`), so `editor.render` silently skips stacking with
  no user feedback; plus the `wide_two_shot` detection bar may be too strict.
  Fix = warn in UI when stacked is on but a subject is unset, and/or relax
  detection.
- (5) end frame cut mid-word / ugly mouth: the main content is cut at
  `clip['end']` with no tail handling. Proposed a short video+audio
  fade-out (or snapping the end to a word/silence boundary), pending the
  user's preference.

## Review items 2 / 3b / 5 implemented + AV1 CPU-decode fix — 2026-09-22

Finished the three deferred review items and verified each without burning
Gemini credits, then found and fixed a merge regression that blocked CPU render.

- (2) Freezes: hard cap on pacing holds. `focus.MAX_HOLD_SECONDS = 1.6`;
  `calm_holds` now uses `limit = min(calm_max_seconds, 1.6)`. A held frame
  reads as an intentional beat up to ~1.6s; longer inserts are dropped from the
  hold set and play live (a real listener shot) instead of freezing. The
  framing slider is clamped to 1–1.6s to match. Verified in-container: the
  exact 2.0s reaction insert that froze before now yields NO hold (plays live);
  a 1.4s insert still holds at 1.4s. No hold can exceed 1.6s.
- (5) End frame: when the clip has no outro, `editor.render` now appends a
  ~0.4s `fade=t=out` (video) + `afade=t=out` (audio) at the very end
  (`fade = min(0.4, joined_seconds/6)`), forcing the filter re-encode path.
  Avoids the cut-off / ugly-mouth last frame. Verified with an ffmpeg smoke
  test: brightness ramps 70.8->25->0 over the last 0.4s (flat ~125 without),
  end audio drops to -30 dB.
- (3b) Stacked trigger: two parts. (a) `QuickEditor.jsx` now warns (amber
  `.quick-warn`) when stacking is on but the second subject is unset — this was
  the real cause of "some clips yes, some no" (clips had `stacked_enabled` but
  a missing `tracking_subject`/`_2`, so render silently skipped). The "0 đoạn"
  case now reads "chưa tìm thấy cảnh toàn nào" instead of a green "✓ 0 đoạn".
  (b) Relaxed detection in `stacked_view.py`: `wide_two_shot` max_width
  .34->.40, min_gap .05->.035; `assemble` quorum .6->.5, min_duration
  1.0->0.8; `VERSION` bumped stacked-v1->stacked-v2 to invalidate old caches so
  re-detection runs. Verified: a borderline 37%-face / 4%-gap two-shot is now
  accepted while a true close-up is still rejected.

- AV1 CPU-decode regression (found while verifying (2)/(3b)/(5) via a real
  render): the render failed at 0% with "Your platform doesn't support hardware
  accelerated AV1 decoding". Root cause: the merged from-source ffmpeg has only
  the native `av1` decoder (hwaccel-only) and `av1_cuvid` (needs a GPU) — no
  software AV1 decoder, because the build lacked libdav1d (Debian's apt ffmpeg
  shipped it). So AV1 phone/screen recordings could only render on a GPU,
  silently breaking the CPU-only path the single image promises. Same class as
  the earlier libmp3lame regression. Fix: `--enable-libdav1d` + `libdav1d-dev`
  (build) + `libdav1d6` (runtime) in the root Dockerfile. This machine has an
  RTX 3050 (face-engine uses it) but the studio container was run CPU-only,
  which is exactly why it surfaced.

## Caption size (preview vs export) + install-size trims — 2026-09-22

User: subtitles render smaller than in the preview; also asked to optimize the
build/install size.

- Caption size root cause + fix: browsers size text by the em (unitsPerEm), but
  libass scales a font so its OS/2 win-metrics (winAscent+winDescent) map to the
  ASS Fontsize. Google Sans declares 1509+1079 win-metrics against a 1000 em
  (2.59x), so at caption_size 64 libass rendered its em at only ~25px — ~2.6x
  smaller than the CSS preview. (Every font is affected a little: DejaVu 0.86x,
  Roboto 0.83x; Google Sans 0.39x is the extreme.) Fix: editor.make_ass now
  multiplies the ASS Fontsize by (winAscent+winDescent)/unitsPerEm, read from the
  exact file `fc-match` hands libass (pure-struct TTF parse, cached, clamps to
  [1,3], falls back to 1.0 so a bad font can never blank captions). Applied to
  both the Default and Hook (main-title) styles. Verified in-container: Google
  Sans caption ink 24px -> 63px, DejaVu/Roboto -> ~62px, all matching the CSS
  preview ink (~63px at size 64). No frontend change (preview was already right).

- Install-size trims (safe, no feature loss):
  * studio: dropped libgl1 — opencv-python-headless links libglib2.0 but not
    libGL/X11 (verified via ldd), so its ~30MB mesa+X11 chain was dead weight.
  * face-engine: onnxruntime-node ships prebuilt binaries for every OS/arch;
    pruned win32, darwin and linux/arm64 (~165MB) plus the unused TensorRT
    provider, keeping only linux/x64 (face.js uses cuda/cpu only).
- Not touched (deliberately): the face-engine's ~2.2GB CUDA runtime (cuDNN
  engines_precompiled 563MB + adv 261MB + cublas/cufft/curand). It is the GPU
  feature the merge was built for and this machine's RTX 3050 uses it; trimming
  cuDNN sublibraries is GPU/arch-specific and risky to ship blind. Flagged to the
  user as the big remaining lever (a CPU-only face-engine variant would drop
  ~2.5GB for GPU-less target devices) — their call.
