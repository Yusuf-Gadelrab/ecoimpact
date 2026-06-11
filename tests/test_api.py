import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def fresh_client(tmp_path) -> TestClient:
    main.DB_PATH = Path(tmp_path) / "test.db"
    main.init_db()
    return TestClient(main.app)


def test_report_clean_impact_flow(tmp_path):
    c = fresh_client(tmp_path)
    r = c.post("/api/reports", json={"lat": 37.33521234, "lng": -121.88112345,
                                     "category": "bag", "reporter": "yusuf"})
    assert r.status_code == 201
    rep = r.json()
    assert rep["lat"] == 37.3352 and rep["lng"] == -121.8811  # privacy rounding
    assert rep["status"] == "open"

    before = c.get("/api/impact").json()
    assert before["kg_waste_diverted"] == 0

    r = c.post(f"/api/reports/{rep['id']}/clean", json={"user": "anas"})
    assert r.status_code == 200 and r.json()["status"] == "cleaned"

    after = c.get("/api/impact").json()
    assert after["kg_waste_diverted"] == 4.0
    assert after["cleaned_reports"] == 1 and after["open_reports"] == 0
    assert after["leaderboard"][0] == {"user": "anas", "points": 40}

    r = c.post(f"/api/reports/{rep['id']}/clean", json={"user": "again"})
    assert r.status_code == 409  # no double-claiming


def test_hazard_is_report_only(tmp_path):
    c = fresh_client(tmp_path)
    rep = c.post("/api/reports", json={"lat": 37.3, "lng": -121.9, "category": "hazard"}).json()
    r = c.post(f"/api/reports/{rep['id']}/clean", json={"user": "yusuf"})
    assert r.status_code == 403


def test_actions_credit_co2(tmp_path):
    c = fresh_client(tmp_path)
    assert c.post("/api/actions", json={"user": "yusuf", "type": "bike_commute"}).status_code == 201
    assert c.post("/api/actions", json={"user": "yusuf", "type": "lights_off"}).status_code == 201
    assert c.post("/api/actions", json={"user": "yusuf", "type": "nonsense"}).status_code == 422
    imp = c.get("/api/impact").json()
    assert imp["kg_co2e_avoided"] == 2.12
    assert imp["points"] == 15
    assert imp["world_fixed_pct"] > 0


def test_streak(tmp_path):
    c = fresh_client(tmp_path)
    assert c.get("/api/users/yusuf/streak").json()["streak_days"] == 0
    c.post("/api/actions", json={"user": "yusuf", "type": "lights_off"})
    s = c.get("/api/users/yusuf/streak").json()
    assert s["streak_days"] == 1 and s["active_today"] is True
    rep = c.post("/api/reports", json={"lat": 37.3, "lng": -121.9, "category": "litter"}).json()
    c.post(f"/api/reports/{rep['id']}/clean", json={"user": "anas"})
    assert c.get("/api/users/anas/streak").json()["streak_days"] == 1


def test_bad_inputs(tmp_path):
    c = fresh_client(tmp_path)
    assert c.post("/api/reports", json={"lat": 95, "lng": 0, "category": "bag"}).status_code == 422
    assert c.post("/api/reports", json={"lat": 37.3, "lng": -121.9,
                                        "category": "nope"}).status_code == 422
    assert c.post("/api/reports/999/clean", json={"user": "x"}).status_code == 404
