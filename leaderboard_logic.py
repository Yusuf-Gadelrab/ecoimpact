import sqlite3

def get_team_leaderboard(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get impact factors (hardcoded mirror of main.py)
        TRASH = {"litter": 10, "bag": 40, "plastic": 15, "ewaste": 30, "hazard": 5}
        ACTIONS = {"lights_off": 3, "bike_commute": 12, "shorter_shower": 4, "reusable_bottle": 2}
        
        teams = {}
        
        # Calculate points per user
        user_points = {}
        for row in c.execute("SELECT category, cleaned_by FROM reports WHERE status='cleaned'"):
            pts = TRASH.get(row["category"], 0)
            user_points[row["cleaned_by"]] = user_points.get(row["cleaned_by"], 0) + pts
        for row in c.execute("SELECT type, user FROM actions"):
            pts = ACTIONS.get(row["type"], 0)
            user_points[row["user"]] = user_points.get(row["user"], 0) + pts
            
        # Group by team
        # 1. Get all team members
        for row in c.execute("SELECT user, team FROM users"):
            team = row["team"] if row["team"] else "Individual"
            teams.setdefault(team, {"points": 0, "members": set()})
            teams[team]["members"].add(row["user"])
            
        # 2. Add points
        for user, pts in user_points.items():
            team_row = c.execute("SELECT team FROM users WHERE user=?", (user,)).fetchone()
            team = team_row["team"] if team_row and team_row["team"] else "Individual"
            teams[team]["points"] += pts
            
        return [{"team": k, "points": int(v["points"]), "members": len(v["members"])}
                for k, v in teams.items()]
