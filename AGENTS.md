# Talkcut project context

Read `memory-bank/README.md`, `memory-bank/active-context.md` and `memory-bank/architecture.md` before making changes. This is a personal Docker application; the user explicitly exempted MISA design-system/backend standards. MISA logos and #ff7300 are product branding requirements, not a request to import AMIS frameworks.

Keep `.env`, source media, runtime database, render files and credentials outside Git. Public artwork in `frontend/public/brand` is the supplied MISA logo including tagline; do not recreate or recolor it.

Keep preview and exported crop/intro geometry consistent. Never replace actual word timing with proportional estimates while describing captions as synchronized. Do not remove talk audio because the camera shows a listener.

Update memory-bank and create an evidence-backed handoff for substantial session changes when requested. Installed handoff skill: `/Users/tuanbui/.codex/skills/handoff/SKILL.md`. Handoff review is separate from authorization to commit/push code; an unconfirmed base must remain null, never invented.

The user clarified "handoff" means an accepted stable version/checkpoint for rollback. During iteration, use RC versions and ordinary memory/changelog updates. Do not generate or request approval of a new handoff package after each edit. Mark stable only after user acceptance of a working build; historical handoff drafts are not stable releases. Use scripts/versions.py and memory-bank/releases.md.
