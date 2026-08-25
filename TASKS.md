# TASKS.md

Backlog and status tracker for work items. One row per atomic candidate
requirement. Status values: `todo` / `red` / `design` / `green` /
`verify` / `gate` / `done` / `blocked`.

## Epic: NiceGUI frontend redesign

Source: `/home/percevase/.claude/plans/lovely-sauteeing-crystal.md`

| ID | Description | Status | Depends on | Commit | Last status change |
|----|--------------|--------|------------|--------|---------------------|
| FE-1 | Wire NiceGUI into app.py: confirm NiceGUI API via context7, add dependency, mount via ui.run_with() onto the existing FastAPI app, remove old index.html/static/app.js/static/style.css/index_new.html and the /static mount + GET / route, ship a placeholder @ui.page('/') proving the dev server still boots. | red | none | | 2026-08-25T23:18:40Z |
| FE-2 | Theming: ui.colors()/consistent styling derived from the reference meme image's zone colors. | todo | FE-1 | | 2026-08-25T23:02:48Z |
| FE-3 | Auth pages (login/register) using app.storage.user for JWT+username. | todo | FE-1, FE-2 | | 2026-08-25T23:02:48Z |
| FE-4 | Continuous energy/valence mood pad via ui.interactive_image with mouse-event coordinate mapping, SVG overlay marker, quadrant captions as overlay text. | todo | FE-2 | | 2026-08-25T23:02:48Z |
| FE-5 | Wire pad submission to POST /moods via stored JWT, explicit confirm action. | todo | FE-3, FE-4 | | 2026-08-25T23:02:48Z |
| FE-6 | Pad keyboard accessibility (arrow keys nudge energy/valence by 0.05, Enter submits). | todo | FE-4, FE-5 | | 2026-08-25T23:02:48Z |
| FE-7 | Mood history page. | todo | FE-2, FE-3 | | 2026-08-25T23:02:48Z |
| FE-8 | Journal entries page. | todo | FE-2, FE-3 | | 2026-08-25T23:02:48Z |
| FE-9 | Analytics/charts page (ui.echart for trend/distribution/scatter views). | todo | FE-2, FE-3 | | 2026-08-25T23:02:48Z |
| FE-10 | Export page (CSV/JSON/PDF download via ui.download). | todo | FE-2, FE-3 | | 2026-08-25T23:02:48Z |
| FE-11 | Docs sync: update CLAUDE.md's Frontend section and Commands section if the dev-server invocation changed. | todo | FE-1, FE-2, FE-3, FE-4, FE-5, FE-6, FE-7, FE-8, FE-9, FE-10 | | 2026-08-25T23:02:48Z |
