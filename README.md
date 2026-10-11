# Fourth Down — TeamRankings auto-import starter

This project adds a backend endpoint that fetches the public TeamRankings NFL team-stat pages and lets the website import the stats into its saved team database.

## Important
- TeamRankings does not advertise an official public API on the page used here. This starter reads public HTML pages, so it can break if their layout changes.
- Check TeamRankings' terms and any applicable access rules before deploying or using automated collection. This starter uses a low request rate and caches the result for 30 minutes.
- This is an experimental personal-use integration. It is not an official TeamRankings integration and does not guarantee that every stat will be available.
- It imports team stats only. Player stats from NFL.com remain manual for now.
- Do not open `index.html` by double-clicking it. The import button needs the backend server.

## Test on your Mac
1. Install Python 3 if you do not have it.
2. Open Terminal and `cd` into this folder.
3. Run:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
4. Open `http://127.0.0.1:5000` in your browser.
5. Go to Teams & Stats and click **Import TeamRankings stats**.

The first import may take around 10–30 seconds because it retrieves several stat pages. Subsequent imports are cached for 30 minutes.

## Deploy it online
Push this folder to a private or public GitHub repository, then create a Python web service on a host that supports Flask (for example, Render). The included `Procfile` uses Gunicorn. Set the build/install command to `pip install -r requirements.txt` and the start command to `gunicorn app:app`. Once deployed, open the public service URL.

If you deploy publicly, consider adding a cache, usage limits, and an explicit data-source attribution note. This backend has no authentication and is intended as a starter, not a production service.
