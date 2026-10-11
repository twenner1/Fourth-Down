from flask import Flask, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone
import re, time, threading

app = Flask(__name__, static_folder=".", static_url_path="")
BASE = "https://www.teamrankings.com/nfl/stat/"
CACHE = {"at": 0, "data": None}
LOCK = threading.Lock()
CACHE_SECONDS = 1800
USER_AGENT = "FourthDownPersonalStatsImporter/1.0 (personal use; polite request rate)"

# TeamRankings page slug -> output field. "Last 3" is used for recent form when available.
STATS = {
    "points-per-game": ("pf", "current"),
    "opponent-points-per-game": ("pa", "current"),
    "yards-per-game": ("yf", "current"),
    "opponent-yards-per-game": ("ya", "current"),
    "turnover-margin-per-game": ("to", "current"),
    "third-down-conversion-pct": ("tdo", "current"),
    "opponent-third-down-conversion-pct": ("tdd", "current"),
    "red-zone-scoring-pct-td-only": ("rzo", "current"),
    "opponent-red-zone-scoring-pct-td-only": ("rzd", "current"),
    "yards-per-play": ("ypp", "current"),
    "opponent-yards-per-play": ("dypp", "current"),
    "sacks-per-game": ("sm", "current"),
    "qb-sacked-per-game": ("sa", "current"),
    "points-per-game": ("rpf", "last3"),
    "opponent-points-per-game": ("rpa", "last3"),
}
# Separate recent-form fetches for duplicate slugs.
RECENT_STATS = {
    "points-per-game": "rpf",
    "opponent-points-per-game": "rpa",
}
TEAM_ALIASES = {
    "la rams": "los angeles rams", "la chargers": "los angeles chargers",
    "ny giants": "new york giants", "ny jets": "new york jets",
    "washington": "washington commanders", "san francisco": "san francisco 49ers",
    "new england": "new england patriots", "kansas city": "kansas city chiefs",
    "green bay": "green bay packers", "tampa bay": "tampa bay buccaneers",
    "new orleans": "new orleans saints", "las vegas": "las vegas raiders",
    "philadelphia": "philadelphia eagles", "buffalo": "buffalo bills",
    "dallas": "dallas cowboys", "chicago": "chicago bears", "detroit": "detroit lions",
    "baltimore": "baltimore ravens", "carolina": "carolina panthers",
    "cincinnati": "cincinnati bengals", "cleveland": "cleveland browns",
    "denver": "denver broncos", "houston": "houston texans", "indianapolis": "indianapolis colts",
    "jacksonville": "jacksonville jaguars", "miami": "miami dolphins", "minnesota": "minnesota vikings",
    "atlanta": "atlanta falcons", "arizona": "arizona cardinals", "pittsburgh": "pittsburgh steelers",
    "seattle": "seattle seahawks", "tennessee": "tennessee titans",
}

def number(s):
    if s is None: return None
    s = str(s).strip().replace(",", "").replace("%", "")
    if not s or s in {"-", "—", "N/A"}: return None
    try: return float(s)
    except ValueError: return None

def parse_stat(slug, mode="current"):
    url = BASE + slug
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(req, timeout=20) as response:
        body = response.read()
    soup = BeautifulSoup(body, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in candidate.find_all("th")]
        if any("team" == h or h.endswith("team") for h in headers) and len(headers) >= 3:
            table = candidate
            break
    if table is None:
        raise RuntimeError(f"Could not find the team table for {slug}. TeamRankings may have changed its page layout.")
    headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
    team_idx = next((i for i,h in enumerate(headers) if h == "team" or h.endswith("team")), 1)
    if mode == "last3":
        value_idx = next((i for i,h in enumerate(headers) if "last 3" in h), None)
    else:
        # Prefer the current season column (e.g. 2026), excluding last/home/away columns.
        value_idx = next((i for i,h in enumerate(headers) if re.fullmatch(r"20\d{2}", h)), None)
        if value_idx is None:
            value_idx = next((i for i,h in enumerate(headers) if h not in {"rank","team"} and not any(x in h for x in ["last","home","away"])), None)
    if value_idx is None:
        raise RuntimeError(f"Could not identify the requested value column for {slug}.")
    out = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td","th"], recursive=False)
        if len(cells) <= max(team_idx, value_idx) or cells[team_idx].name == "th":
            continue
        team = cells[team_idx].get_text(" ", strip=True)
        val = number(cells[value_idx].get_text(" ", strip=True))
        if team and val is not None:
            out[team] = val
    if not out:
        raise RuntimeError(f"No team values parsed from {slug}.")
    return out

def build_dataset():
    data = {}
    # Fetch each stat page once, with a short pause between requests.
    for slug, field in [
        ("points-per-game","pf"), ("opponent-points-per-game","pa"),
        ("yards-per-game","yf"), ("opponent-yards-per-game","ya"),
        ("turnover-margin-per-game","to"), ("third-down-conversion-pct","tdo"),
        ("opponent-third-down-conversion-pct","tdd"),
        ("red-zone-scoring-pct-td-only","rzo"),
        ("opponent-red-zone-scoring-pct-td-only","rzd"),
        ("yards-per-play","ypp"), ("opponent-yards-per-play","dypp"),
        ("sacks-per-game","sm"), ("qb-sacked-per-game","sa"),
    ]:
        values = parse_stat(slug)
        for name, value in values.items():
            data.setdefault(name, {})[field] = value
        time.sleep(0.8)
    for slug, field in RECENT_STATS.items():
        values = parse_stat(slug, "last3")
        for name, value in values.items():
            data.setdefault(name, {})[field] = value
        time.sleep(0.8)

    result = []
    for display_name, stats in data.items():
        canonical = TEAM_ALIASES.get(display_name.lower(), display_name)
        # Stats pages can abbreviate some names; provide the raw name too for matching.
        slug = re.sub(r"[^a-z0-9]+", "-", canonical.lower()).strip("-")
        result.append({
            "name": canonical, "slug": slug, "aliases": [display_name],
            "pf": stats.get("pf"), "pa": stats.get("pa"),
            "yf": stats.get("yf"), "ya": stats.get("ya"),
            "to": stats.get("to"), "tdo": stats.get("tdo"), "tdd": stats.get("tdd"),
            "rzo": stats.get("rzo"), "rzd": stats.get("rzd"),
            "ypp": stats.get("ypp"), "dypp": stats.get("dypp"),
            "sm": stats.get("sm"), "sa": stats.get("sa"),
            "rpf": stats.get("rpf", stats.get("pf")), "rpa": stats.get("rpa", stats.get("pa")),
        })
    if len(result) < 25:
        raise RuntimeError(f"Only {len(result)} teams were collected; refusing to import incomplete data.")
    return result

@app.get("/")
def index():
    return send_from_directory(".", "index.html")

@app.get("/api/team-stats")
def team_stats():
    now = time.time()
    with LOCK:
        if CACHE["data"] and now - CACHE["at"] < CACHE_SECONDS:
            return jsonify({"teams": CACHE["data"], "fetched_at": datetime.fromtimestamp(CACHE["at"], timezone.utc).isoformat(), "cached": True})
        try:
            teams = build_dataset()
            CACHE["data"] = teams
            CACHE["at"] = time.time()
            return jsonify({"teams": teams, "fetched_at": datetime.now(timezone.utc).isoformat(), "cached": False})
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 502

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
