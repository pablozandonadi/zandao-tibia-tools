# Mirror Implementation Plan

> **For agentic workers:** Execute task-by-task using Superpowers subagent-driven-development or executing-plans. Preserve the shared checkout; publish using a temporary develop copy.

**Goal:** Deliver visual Mirror regions, selectors with loupe, character/profile isolation, glow and an official analysis Beta.
**Architecture:** A pure private store coordinates a thread-owned DWM engine through MirrorService. The WebView panel exposes profile and crop controls, while native Windows layers provide live content and external glow.
**Tech Stack:** Python, ctypes Win32/DWM, Pillow, PyWebView, JavaScript/CSS.
**Spec:** docs/superpowers/plans/2026-10-14-mirror-brainstorm.md

## Global Constraints

- Default square32physical pixels; no mandatory calibration.
- Manual and square selection both have loupe.
- Glow free color, off/min/med/max, persisted per crop/profile/character.
- Only exact linked Tibia HWND foreground shows overlays.
- No game input generation, client memory/injection/patches or capture-protection bypass.
- Preserve all pending shared work and personal data; develop Beta automatic, stable requires user approval.

## Tasks and verification

- [x] Model/persistence: mirror_core.py and test_mirror_core.py. Character→profile→crop, stable IDs, atomic save and valid backup. Run `python -m unittest test_mirror_core -v`.
- [x] Native engine/selectors/glow: mirror_native.py, mirror_selector.py, mirror_visual.py and test_mirror_native.py. DWM thumbnail + independent RGBA glow/name, physical client coords, strict focus, release pairing and teardown. Run `python -m unittest test_mirror_native -v`; synthetic native content/opacity/hit testing/resources; real protection read-only diagnostic.
- [x] Async bridge: mirror_service.py and test_mirror_service.py. `configure(character,profile)`, `select(mode,on_result,existing)`, cancellation, client binding, stale generation rejection. Run `python -m unittest test_mirror_service -v`.
- [x] UI: web/mirror.js and web/mirror.css, test_mirror_ui.cjs. Profile CRUD, crop appearance and source edits, pending/cancel state, character generation. Run `node test_mirror_ui.cjs`; actual browser QA with synthetic data1550/430width.
- [x] Integration/privacy: web_api.py, web/index.html, zandao_tibia_tools.py, app_paths.py, backup.py, package_tools.py, .gitignore, packaging-resources.json. Add navigation/API/startup/shutdown/backup and exact resource allowlist; `python package_tools.py resources .`.
- [x] Review and limits: independent spec/quality review, scoped fix review, test_mirror_rules.py and docs/mirror.md; visual-only boundaries from user14/10.
- [ ] Publication: apply only baseline→Mirror delta to clean temporary develop clone, full unittest and JS suites, commit/push develop, confirm successful workflow and all release assets, record exact version/link. No shared branch switch, no stable release.

## Rulings

- Shared development source preserved per user AGENTS.md; new files have separate ownership, mutations to existing files use exact anchors. Only publication is isolated. Cost of mismatch is detected by baseline diff/apply review.
- Black screenshots from protected Tibia do not prove a visible black mirror. Read-only affinity returned WDA_MONITOR0x1; keep DWM reference mechanism and require direct visual validation. No bypass permitted.
- Background callbacks run off renderer so profile-teardown barrier cannot deadlock with store/service locks.
- Source geometry/DPI changes pause instead of silently stretching slot coordinates. Reposition with loupe; monitor physical matrix remains user QA.
