# Architecture and deployment

FastAPI/Python, React/Vite, SQLite JSON records, a single in-process queue worker. FFmpeg renders H.264/AAC 1080×1920; Pillow draws title layers; OpenCV refines faces; Google supplies content reasoning/STT/TTS. Secrets live in `.env`; no new environment variables in this revision.

`schemas.Settings` supplies compatible defaults and removes the summary card even when old records request it. Voice profile is validated server-side. `voice_profiles.instruction` gives one-speaker directions; `narration.synthesize` caches by spoken text, voice/model/mode/profile. `align_display` aligns original display tokens to final audio, after atempo. Numeric expansions remain spoken-only. Display and approved TTS text remain separate.

`focus.cached` enriches reaction shots using a single visible face when possible; it does not label that listener as the speaker. `prepared_track` locks each scene to a shared face-safe crop center where possible, otherwise applies deadband/smoothing and clamps safe bounds. API returns this prepared geometry, consumed by frontend and FFmpeg. Unknown/b-roll remains full-frame.

`intro_art` creates real freeze-frame assets and a single 9:16 photo canvas. Optional upper brand band, pan/zoom, separate title/highlight layer; narration is never a static paragraph. `intro-preview` returns server-rendered PNG matching export. `intro-audio` returns audio plus word timings for browser karaoke. Full export burns ASS timed events over the still segment. Caption visibility does not disable TTS.

## Deployment decision

For this user's personal workflow, keep Docker local first: source files remain on disk, no full-source upload to a second server, minimal operations. Google AI still requires network/API usage. Performance depends on allocated CPU, media resolution and source download; Docker alone does not accelerate inference.

A VPS with persistent SSD is the simplest next step for a shared/always-on worker. Add authentication, HTTPS, allowed-origin configuration, backups and job recovery. Current local-only origin guard is intentionally incompatible with an arbitrary public domain.

Cloud Run is feasible after separating web API from render jobs and externalizing state: Cloud Storage for media, external DB, durable queue/job dispatch. Do not deploy the current local volume + SQLite + daemon worker unchanged. Its writable filesystem consumes RAM and disappears on stop; service CPU allocation depends on billing. Cloud Run Jobs supports longer render tasks (CPU task timeout up to 7 days), but that does not make local state durable.

Sources verified 2026-09-08:
- https://docs.cloud.google.com/run/docs/container-contract
- https://docs.cloud.google.com/run/docs/configuring/task-timeout
- https://ai.google.dev/gemini-api/docs/speech-generation
