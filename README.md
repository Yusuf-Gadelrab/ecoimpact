# EcoImpact

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)
![SQLite](https://img.shields.io/badge/db-SQLite-003B57)
![License](https://img.shields.io/badge/license-source--available-lightgrey)

EcoImpact is a local-first web app for reporting litter on a shared map, claiming cleanups, and logging everyday eco actions. It turns that activity into a quantified "world fixed" impact meter, streaks, badges, weekly challenges, and a leaderboard — a lightweight way for a person, class, dorm, or club to track community cleanup and daily habits without any account system or cloud backend.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/Yusuf-Gadelrab/ecoimpact.git
cd ecoimpact
./run.sh        # → http://127.0.0.1:8900
```

`run.sh` just runs `uv run uvicorn main:app --host 127.0.0.1 --port 8900`, so `uv` resolves and installs dependencies from `uv.lock` on first run. Open the printed URL, tap the map to report trash, tap a red pin to claim a cleanup.

### Tests

```bash
uv run pytest tests/
```

## How it works

**Report → claim → credit.** Tapping the map opens a popup to file a report (category, optional note, optional photo). Reports round GPS coordinates to 4 decimal places (~11 m) before storing them — precise device location is never collected. Tapping an open pin lets anyone claim the cleanup (`POST /api/reports/{id}/clean`); a report can only be claimed once, and the `hazard` category is deliberately **report-only** — the API returns `403` on any cleanup attempt so hazardous waste gets flagged rather than handled by an untrained user. A report submitted with a photo starts in a `pending` state; a `moderate` endpoint stub exists to approve or flag it later.

**Impact math.** Every trash category and eco action carries fixed (kg waste diverted, kg CO₂e avoided, points) values, defined in `main.py`:

| Trash category | kg waste | kg CO₂e | points |
|---|---|---|---|
| litter | 0.5 | 0.0 | 10 |
| bag | 4.0 | 0.0 | 40 |
| plastic | 1.0 | 0.5 | 15 |
| e-waste | 2.0 | 5.0 | 30 |
| hazard *(report-only)* | 0.0 | 0.0 | 5 |

| Eco action | kg waste | kg CO₂e | points |
|---|---|---|---|
| lights off | 0.0 | 0.12 | 3 |
| bike instead of drive | 0.0 | 2.0 | 12 |
| shorter shower | 0.0 | 0.3 | 4 |
| reusable bottle | 0.02 | 0.08 | 2 |

These are estimates from EPA/DOE averages, not measured emissions. The site-wide **"world fixed" meter** is `min(100, 100 × total_kg_CO2e_avoided / 500)` — 500 kg CO₂e avoided across every cleanup and logged action reads as 100%.

**Streaks, badges, challenges.** A user's streak counts consecutive days, ending today, with at least one logged action or claimed cleanup (`/api/users/{user}/streak`). Five badges unlock on cumulative milestones (first cleanup, five cleanups, first report, a 3-day streak, 10 kg CO₂e avoided). Three challenges reset daily or weekly — log any action today (+10 pts), avoid 5 kg CO₂e in a week (+50 pts), or clean 3 reports in a week (+100 pts) — and are claimed explicitly via `POST /api/challenges/claim`, which re-checks completion server-side and blocks double-claiming.

**Leaderboard & teams.** The global leaderboard (`/api/impact`) ranks the top 10 users by total points across cleanups and actions. Users can optionally join a free-text team name; `/api/teams` sums member points into a team leaderboard (`leaderboard_logic.py`).

**Frontend.** `static/index.html` is a single-page Leaflet map (dark CARTO basemap, OpenStreetMap data) with a pin/heatmap toggle, an animated progress ring for the world-fixed %, count-up stat tiles, toast notifications, and a confetti burst on badge/challenge unlocks. It registers a service worker for offline map caching and installs as a PWA via `static/manifest.webmanifest`.

## API

| Method | Path | Does |
|---|---|---|
| GET | `/` | Serves the app (`static/index.html`) |
| GET | `/api/reports` | List reports, optional `?status=` filter, newest 500 |
| POST | `/api/reports` | File a litter report (lat, lng, category, note, optional photo) |
| POST | `/api/reports/{id}/clean` | Claim a cleanup on an open, non-hazard report |
| POST | `/api/reports/{id}/moderate` | Approve/flag a pending photo report (moderation stub) |
| POST | `/api/actions` | Log an eco action or claimed-challenge type |
| GET | `/api/impact` | Global totals, world-fixed %, top-10 leaderboard |
| GET | `/api/users/{user}/impact` | Per-user totals, weekly rollup, leaderboard rank |
| GET | `/api/users/{user}/streak` | Consecutive-day activity streak |
| GET | `/api/users/{user}/badges` | Earned/unearned badge status |
| GET | `/api/users/{user}/challenges` | Claim status of the 3 active challenges |
| POST | `/api/challenges/claim` | Claim a completed challenge's reward |
| POST | `/api/users/{user}/team` | Join/set a team name |
| GET | `/api/teams` | Team leaderboard |

## Design notes

- **Privacy:** GPS is never collected; trash coordinates are rounded to 4 decimals (~11 m). Usernames and team names are free-text, truncated server-side.
- **Safety:** the `hazard` category is report-only — the API rejects cleanup claims on it so it can be routed to proper disposal instead of handled by hand.
- Impact factors are EPA/DOE-average estimates, not measured results.

## Status

Personal project, early stage. Single-file FastAPI backend, SQLite storage, no auth, no deployment — it runs locally for demos and portfolio review. Verified by a 12-case `pytest` suite covering the report/claim/impact flow, hazard rejection, streaks, badges, challenges, teams, and photo uploads. No claims of users, installs, or real-world cleanups performed.

## Links

- Project page: <https://yusuf-gadelrab.github.io/ecoimpact.html>
- Portfolio: <https://yusuf-gadelrab.github.io/>

## More from this author

- [DIRA](https://github.com/Yusuf-Gadelrab/dira) — zero-dependency security scanner for startup codebases
- [EventReels](https://github.com/Yusuf-Gadelrab/eventreels) — local ffmpeg highlight-reel automation
- [EdgeLog](https://github.com/Yusuf-Gadelrab/edgelog) — trade journal analyzer

## License

© 2026 Yusuf Gadelrab. All rights reserved. Source is public for portfolio and evaluation purposes only: no license is granted to copy, modify, or redistribute this code.

## About the author

Built by **Yusuf Gadelrab** — computer science student at San José State University (BS Computer Science, expected May 2028), AI/ML builder, and co-author of two peer-reviewed SIGCSE Technical Symposium 2026 papers on computer science education ([DOI 10.1145/3770761.3777339](https://doi.org/10.1145/3770761.3777339)).

- About / FAQ: <https://yusuf-gadelrab.github.io/about.html>
- Guides: <https://yusuf-gadelrab.github.io/guides.html>
- Contact: yusuf.gadelrab06@gmail.com
