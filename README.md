# EcoImpact MVP

EcoImpact is a local-first web app that lets people report litter on a shared map, claim cleanups,
and log daily eco actions, then turns those actions into a quantified "world fixed" impact meter and
leaderboard. Built with FastAPI, SQLite, and Leaflet/OpenStreetMap.

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

## License
© 2026 Yusuf Gadelrab. All rights reserved. Source is public for portfolio and evaluation
purposes only: no license is granted to copy, modify, or redistribute this code.

---

## About the author

Built by **Yusuf Gadelrab** — computer science student at San José State University (BS Computer Science, expected May 2028), AI/ML builder, and co-author of two peer-reviewed SIGCSE Technical Symposium 2026 papers on computer science education ([DOI 10.1145/3770761.3777339](https://doi.org/10.1145/3770761.3777339)).

- Portfolio: <https://yusuf-gadelrab.github.io/>
- About / FAQ: <https://yusuf-gadelrab.github.io/about.html>
- Guides: <https://yusuf-gadelrab.github.io/guides.html>
- Contact: yusuf.gadelrab06@gmail.com
