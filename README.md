# EcoImpact MVP

Trash map + "world fixed" impact meter. FastAPI + SQLite + Leaflet/OpenStreetMap, fully local.

## Run
```bash
./run.sh        # → http://127.0.0.1:8900
```
Tap the map → report trash. Tap a red pin → "I cleaned this" → impact credited.
Sidebar logs daily eco actions (lights off, bike, shower, bottle) and shows the
world-fixed meter, totals, and leaderboard.

## Tests
```bash
uv run pytest tests/
```

## Design notes
- **Privacy:** user GPS is never collected; trash coords rounded to 4 decimals (~11 m).
- **Safety:** `hazard` category is report-only — the API refuses cleanup claims on it.
- Impact factors are EPA/DOE-average estimates (lights-off kWh, bike-vs-drive per mile,
  shower water heating, single-use bottle production).
