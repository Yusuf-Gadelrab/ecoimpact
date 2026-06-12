"""EcoImpact MVP — trash map + quantified impact meter.

Privacy by design: only trash coordinates are stored (rounded to ~11 m); user GPS is never
collected. Impact factors are estimates from EPA/DOE averages — see docs/PLAN.md.
"""

import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import shutil
from leaderboard_logic import get_team_leaderboard

DB_PATH = Path(__file__).parent / "ecoimpact.db"
STATIC = Path(__file__).parent / "static"
UPLOADS_DIR = STATIC / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# (kg waste diverted, kg CO2e avoided, points) per action
TRASH_IMPACT = {
    "litter": (0.5, 0.0, 10),
    "bag": (4.0, 0.0, 40),
    "plastic": (1.0, 0.5, 15),
    "ewaste": (2.0, 5.0, 30),
    "hazard": (0.0, 0.0, 5),  # report-only: "don't touch", routed to city services
}
ACTION_IMPACT = {
    "lights_off": (0.0, 0.12, 3),
    "bike_commute": (0.0, 2.0, 12),
    "shorter_shower": (0.0, 0.3, 4),
    "reusable_bottle": (0.02, 0.08, 2),
    "challenge_daily": (0.0, 0.0, 10),
    "challenge_co2": (0.0, 0.0, 50),
    "challenge_sweeper": (0.0, 0.0, 100),
}
WORLD_FIXED_CAP = 500.0  # kg CO2e at which the playful meter reads 100%

app = FastAPI(title="EcoImpact")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS reports(
            id INTEGER PRIMARY KEY,
            lat REAL NOT NULL, lng REAL NOT NULL,
            category TEXT NOT NULL, note TEXT DEFAULT '',
            reporter TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            cleaned_by TEXT, created_at REAL NOT NULL, cleaned_at REAL
        );
        CREATE TABLE IF NOT EXISTS actions(
            id INTEGER PRIMARY KEY,
            user TEXT NOT NULL, type TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users(
            user TEXT PRIMARY KEY, team TEXT
        );
        """)
        try:
            c.execute("ALTER TABLE reports ADD COLUMN photo_report TEXT")
            c.execute("ALTER TABLE reports ADD COLUMN photo_clean TEXT")
        except sqlite3.OperationalError:
            pass

# ... existing code ...

@app.post("/api/users/{user}/team")
def set_team(user: str, body: dict):
    team = str(body.get("team", "")).strip()[:24]
    with db() as c:
        c.execute("INSERT OR REPLACE INTO users(user, team) VALUES(?,?)", (user, team))
    return {"ok": True}

@app.get("/api/teams")
def list_teams():
    return sorted(get_team_leaderboard(DB_PATH), key=lambda x: x["points"], reverse=True)


init_db()


class ActionIn(BaseModel):
    user: str = "anonymous"
    type: str


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/reports", status_code=201)
def create_report(lat: float = Form(...), lng: float = Form(...),
                  category: str = Form(...), note: str = Form(""),
                  reporter: str = Form("anonymous"),
                  photo: UploadFile | None = File(None)):
    if category not in TRASH_IMPACT:
        raise HTTPException(422, f"category must be one of {sorted(TRASH_IMPACT)}")
        
    photo_path = None
    if photo and photo.filename:
        photo_path = f"report_{time.time()}_{photo.filename.replace(' ', '_')}"
        with open(UPLOADS_DIR / photo_path, "wb") as f:
            shutil.copyfileobj(photo.file, f)

    with db() as c:
        cur = c.execute(
            "INSERT INTO reports(lat,lng,category,note,reporter,created_at,photo_report) VALUES(?,?,?,?,?,?,?)",
            (round(lat, 4), round(lng, 4), category, note[:280], reporter[:40], time.time(), photo_path),
        )
        assert cur.lastrowid is not None
        return get_report_row(c, cur.lastrowid)


@app.get("/api/reports")
def list_reports(status: str | None = None):
    q = "SELECT * FROM reports"
    args: tuple = ()
    if status:
        q += " WHERE status=?"
        args = (status,)
    with db() as c:
        return [dict(row) for row in c.execute(q + " ORDER BY created_at DESC LIMIT 500", args)]


@app.post("/api/reports/{rid}/clean")
def clean_report(rid: int, user: str = Form("anonymous"), photo: UploadFile | None = File(None)):
    with db() as c:
        row = c.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
        if not row:
            raise HTTPException(404, "no such report")
        if row["status"] == "cleaned":
            raise HTTPException(409, "already cleaned")
        if row["category"] == "hazard":
            raise HTTPException(403, "hazardous waste is report-only — don't touch it")
            
        photo_path = None
        if photo and photo.filename:
            photo_path = f"clean_{time.time()}_{photo.filename.replace(' ', '_')}"
            with open(UPLOADS_DIR / photo_path, "wb") as f:
                shutil.copyfileobj(photo.file, f)

        c.execute("UPDATE reports SET status='cleaned', cleaned_by=?, cleaned_at=?, photo_clean=? WHERE id=?",
                  (user[:40], time.time(), photo_path, rid))
        return get_report_row(c, rid)


@app.post("/api/actions", status_code=201)
def log_action(a: ActionIn):
    if a.type not in ACTION_IMPACT:
        raise HTTPException(422, f"type must be one of {sorted(ACTION_IMPACT)}")
    with db() as c:
        c.execute("INSERT INTO actions(user,type,created_at) VALUES(?,?,?)",
                  (a.user[:40], a.type, time.time()))
    waste, co2, pts = ACTION_IMPACT[a.type]
    return {"ok": True, "type": a.type, "kg_waste": waste, "kg_co2e": co2, "points": pts}


@app.get("/api/users/{user}/streak")
def streak(user: str):
    """Consecutive days (ending today) with at least one logged action or cleanup."""
    days: set[str] = set()
    with db() as c:
        for (ts,) in c.execute("SELECT created_at FROM actions WHERE user=?", (user,)):
            days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        for (ts,) in c.execute(
                "SELECT cleaned_at FROM reports WHERE cleaned_by=? AND cleaned_at IS NOT NULL",
                (user,)):
            days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
    n = 0
    t = time.time()
    while time.strftime("%Y-%m-%d", time.localtime(t)) in days:
        n += 1
        t -= 86400
    return {"user": user, "streak_days": n, "active_today": n > 0}


def _leaderboard_map(c: sqlite3.Connection) -> dict[str, float]:
    """Returns {user: total_points} across all cleanups and actions."""
    per_user: dict[str, float] = {}
    for row in c.execute("SELECT category, cleaned_by FROM reports WHERE status='cleaned'"):
        per_user[row["cleaned_by"]] = per_user.get(row["cleaned_by"], 0) + TRASH_IMPACT[row["category"]][2]
    for row in c.execute("SELECT user, type FROM actions"):
        per_user[row["user"]] = per_user.get(row["user"], 0) + ACTION_IMPACT[row["type"]][2]
    return per_user


@app.get("/api/impact")
def impact():
    waste = co2 = 0.0
    with db() as c:
        for row in c.execute("SELECT category FROM reports WHERE status='cleaned'"):
            w, cg, _ = TRASH_IMPACT[row["category"]]
            waste += w; co2 += cg
        for row in c.execute("SELECT type FROM actions"):
            w, cg, _ = ACTION_IMPACT[row["type"]]
            waste += w; co2 += cg
        open_count = c.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0]
        cleaned_count = c.execute("SELECT COUNT(*) FROM reports WHERE status='cleaned'").fetchone()[0]
        per_user = _leaderboard_map(c)
    leaderboard = sorted(per_user.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "kg_waste_diverted": round(waste, 2),
        "kg_co2e_avoided": round(co2, 2),
        "points": int(sum(per_user.values())),
        "world_fixed_pct": round(min(100.0, 100.0 * co2 / WORLD_FIXED_CAP), 1),
        "open_reports": open_count,
        "cleaned_reports": cleaned_count,
        "leaderboard": [{"user": u, "points": int(p)} for u, p in leaderboard],
    }


@app.get("/api/users/{user}/impact")
def user_impact(user: str):
    week_cutoff = time.time() - 7 * 86400
    waste = co2 = pts = 0.0
    cleanups = reports_filed = actions_logged = 0
    week_co2 = 0.0
    week_cleanups = week_actions = 0

    with db() as c:
        for row in c.execute(
            "SELECT category, cleaned_at FROM reports WHERE status='cleaned' AND cleaned_by=?",
            (user,),
        ):
            w, cg, p = TRASH_IMPACT[row["category"]]
            waste += w; co2 += cg; pts += p
            cleanups += 1
            if row["cleaned_at"] and row["cleaned_at"] >= week_cutoff:
                week_co2 += cg
                week_cleanups += 1

        reports_filed = c.execute(
            "SELECT COUNT(*) FROM reports WHERE reporter=?", (user,)
        ).fetchone()[0]

        for row in c.execute(
            "SELECT type, created_at FROM actions WHERE user=?", (user,)
        ):
            w, cg, p = ACTION_IMPACT[row["type"]]
            waste += w; co2 += cg; pts += p
            actions_logged += 1
            if row["created_at"] >= week_cutoff:
                week_co2 += cg
                week_actions += 1

        lb = _leaderboard_map(c)

    rank = None
    if pts > 0:
        for i, (u, _) in enumerate(sorted(lb.items(), key=lambda kv: kv[1], reverse=True), 1):
            if u == user:
                rank = i
                break

    return {
        "user": user,
        "points": int(pts),
        "kg_waste_diverted": round(waste, 2),
        "kg_co2e_avoided": round(co2, 2),
        "cleanups": cleanups,
        "reports_filed": reports_filed,
        "actions_logged": actions_logged,
        "rank": rank,
        "week": {
            "kg_co2e_avoided": round(week_co2, 2),
            "cleanups": week_cleanups,
            "actions_logged": week_actions,
        },
    }

@app.get("/api/users/{user}/badges")
def user_badges(user: str):
    imp = user_impact(user)
    st = streak(user)["streak_days"]
    
    badges = [
        {"id": "first-cleanup", "name": "First Cleanup", "emoji": "🧹", "earned_hint": "Clean up your first trash"},
        {"id": "five-cleanups", "name": "Five Cleanups", "emoji": "🏆", "earned_hint": "Clean up 5 pieces of trash"},
        {"id": "first-report", "name": "First Report", "emoji": "📍", "earned_hint": "Report your first trash"},
        {"id": "week-streak-3", "name": "3-Day Streak", "emoji": "🔥", "earned_hint": "Log actions 3 days in a row"},
        {"id": "kg10-co2e", "name": "10kg CO2e", "emoji": "🌍", "earned_hint": "Avoid 10kg of CO2e"},
    ]
    
    earned_ids = set()
    if imp["cleanups"] >= 1: earned_ids.add("first-cleanup")
    if imp["cleanups"] >= 5: earned_ids.add("five-cleanups")
    if imp["reports_filed"] >= 1: earned_ids.add("first-report")
    if st >= 3: earned_ids.add("week-streak-3")
    if imp["kg_co2e_avoided"] >= 10.0: earned_ids.add("kg10-co2e")
    
    for b in badges:
        b["earned"] = b["id"] in earned_ids
        
    return badges


def get_report_row(c: sqlite3.Connection, rid: int) -> dict:
    return dict(c.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone())


@app.get("/api/users/{user}/challenges")
def get_user_challenges(user: str):
    today_start = time.time() - (time.time() % 86400)
    week_start = time.time() - 7 * 86400
    
    with db() as c:
        daily_claimed = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type='challenge_daily' AND created_at >= ?", 
                                  (user, today_start)).fetchone()[0] > 0
        co2_claimed = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type='challenge_co2' AND created_at >= ?", 
                                (user, week_start)).fetchone()[0] > 0
        sweeper_claimed = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type='challenge_sweeper' AND created_at >= ?", 
                                    (user, week_start)).fetchone()[0] > 0
                                    
    return {
        "daily": {"claimed": daily_claimed},
        "co2": {"claimed": co2_claimed},
        "sweeper": {"claimed": sweeper_claimed}
    }


@app.post("/api/challenges/claim")
def claim_challenge(body: dict):
    user = str(body.get("user", "")).strip()[:40]
    ctype = str(body.get("challenge", ""))
    
    if ctype not in ["daily", "co2", "sweeper"]:
        raise HTTPException(400, "Invalid challenge type")
        
    action_type = f"challenge_{ctype}"
    
    with db() as c:
        # For daily, check today
        if ctype == "daily":
            today_start = time.time() - (time.time() % 86400)
            cnt = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type=? AND created_at >= ?", 
                            (user, action_type, today_start)).fetchone()[0]
            if cnt > 0:
                raise HTTPException(409, "Daily challenge reward already claimed today")
                
            action_cnt = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type NOT LIKE 'challenge_%' AND created_at >= ?",
                                   (user, today_start)).fetchone()[0]
            cleanup_cnt = c.execute("SELECT COUNT(*) FROM reports WHERE cleaned_by=? AND status='cleaned' AND cleaned_at >= ?",
                                    (user, today_start)).fetchone()[0]
            if action_cnt + cleanup_cnt == 0:
                raise HTTPException(400, "Daily challenge is not completed yet")
                
        elif ctype == "co2":
            week_start = time.time() - 7 * 86400
            cnt = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type=? AND created_at >= ?", 
                            (user, action_type, week_start)).fetchone()[0]
            if cnt > 0:
                raise HTTPException(409, "Weekly CO2 challenge reward already claimed this week")
                
            co2 = 0.0
            for row in c.execute("SELECT category FROM reports WHERE status='cleaned' AND cleaned_by=? AND cleaned_at >= ?",
                                 (user, week_start)):
                co2 += TRASH_IMPACT[row["category"]][1]
            for row in c.execute("SELECT type FROM actions WHERE user=? AND created_at >= ?",
                                 (user, week_start)):
                co2 += ACTION_IMPACT[row["type"]][1]
                
            if co2 < 5.0:
                raise HTTPException(400, "Weekly CO2 challenge is not completed yet")
                
        elif ctype == "sweeper":
            week_start = time.time() - 7 * 86400
            cnt = c.execute("SELECT COUNT(*) FROM actions WHERE user=? AND type=? AND created_at >= ?", 
                            (user, action_type, week_start)).fetchone()[0]
            if cnt > 0:
                raise HTTPException(409, "Weekly Sweeper challenge reward already claimed this week")
                
            cleanups = c.execute("SELECT COUNT(*) FROM reports WHERE cleaned_by=? AND status='cleaned' AND cleaned_at >= ?",
                                 (user, week_start)).fetchone()[0]
            if cleanups < 3:
                raise HTTPException(400, "Weekly Sweeper challenge is not completed yet")
                
        c.execute("INSERT INTO actions(user, type, created_at) VALUES(?,?,?)",
                  (user, action_type, time.time()))
                  
    return {"ok": True, "reward_points": ACTION_IMPACT[action_type][2]}
