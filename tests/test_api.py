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


def test_user_impact_empty(tmp_path):
    c = fresh_client(tmp_path)
    r = c.get("/api/users/ghost/impact")
    assert r.status_code == 200
    d = r.json()
    assert d["points"] == 0
    assert d["kg_waste_diverted"] == 0.0
    assert d["kg_co2e_avoided"] == 0.0
    assert d["cleanups"] == 0
    assert d["reports_filed"] == 0
    assert d["actions_logged"] == 0
    assert d["rank"] is None
    assert d["week"]["cleanups"] == 0
    assert d["week"]["actions_logged"] == 0


def test_user_impact_counts(tmp_path):
    c = fresh_client(tmp_path)
    rep = c.post("/api/reports", json={"lat": 37.3, "lng": -121.9,
                                       "category": "bag", "reporter": "alice"}).json()
    c.post(f"/api/reports/{rep['id']}/clean", json={"user": "bob"})
    c.post("/api/actions", json={"user": "bob", "type": "bike_commute"})
    c.post("/api/actions", json={"user": "bob", "type": "lights_off"})

    lb = c.get("/api/impact").json()["leaderboard"]
    bob_lb_pts = next(e["points"] for e in lb if e["user"] == "bob")

    b = c.get("/api/users/bob/impact").json()
    assert b["points"] == bob_lb_pts
    assert b["cleanups"] == 1
    assert b["actions_logged"] == 2
    assert b["rank"] == 1

    a = c.get("/api/users/alice/impact").json()
    assert a["reports_filed"] == 1
    assert a["cleanups"] == 0


def test_user_impact_week(tmp_path):
    c = fresh_client(tmp_path)
    rep = c.post("/api/reports", json={"lat": 37.3, "lng": -121.9,
                                       "category": "plastic", "reporter": "yusuf"}).json()
    c.post(f"/api/reports/{rep['id']}/clean", json={"user": "yusuf"})
    c.post("/api/actions", json={"user": "yusuf", "type": "bike_commute"})

    d = c.get("/api/users/yusuf/impact").json()
    assert d["week"]["cleanups"] == 1
    assert d["week"]["actions_logged"] == 1
    assert d["week"]["kg_co2e_avoided"] > 0


def test_bad_inputs(tmp_path):
    c = fresh_client(tmp_path)
    assert c.post("/api/reports", json={"lat": 95, "lng": 0, "category": "bag"}).status_code == 422
    assert c.post("/api/reports", json={"lat": 37.3, "lng": -121.9,
                                        "category": "nope"}).status_code == 422
    assert c.post("/api/reports/999/clean", json={"user": "x"}).status_code == 404

def test_user_badges(tmp_path):
    c = fresh_client(tmp_path)
    
    b0 = c.get("/api/users/yusuf/badges").json()
    assert all(not b["earned"] for b in b0)
    
    rep = c.post("/api/reports", json={"lat": 37.3, "lng": -121.9, "category": "bag", "reporter": "yusuf"}).json()
    c.post(f"/api/reports/{rep['id']}/clean", json={"user": "yusuf"})
    
    b1 = c.get("/api/users/yusuf/badges").json()
    earned = {b["id"] for b in b1 if b["earned"]}
    assert "first-report" in earned
    assert "first-cleanup" in earned
    assert "five-cleanups" not in earned
    assert "kg10-co2e" not in earned
    
    for _ in range(5):
        c.post("/api/actions", json={"user": "yusuf", "type": "bike_commute"})
    
    b2 = c.get("/api/users/yusuf/badges").json()
    earned2 = {b["id"] for b in b2 if b["earned"]}
    assert "kg10-co2e" in earned2
