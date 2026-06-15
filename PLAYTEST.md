# Playtest Guide — Royal Succession Simulation

_Prepared overnight 2026-06-15 so you can jump straight into playing/testing the UI._

## TL;DR — start playing in 30 seconds
```bash
cd /Users/barakganon/personal_projects/Royal-Succession-Simulation
source .venv/bin/activate
python main_flask_app.py        # then open the URL it prints (http://127.0.0.1:8091)
```
- **Login:** `test_user` / `password`
- **A fresh clean game is already set up for you:** **House Aldermoor Dynasty** (year 1000, 10 territories, 3 AI rivals). After login you land on the **World Map** — that's the main screen.

> You no longer need `MPLBACKEND=Agg` — the app now forces the non-GUI matplotlib backend itself (this was crashing the server the moment you opened a chart page on macOS; fixed tonight).

## What I verified tonight (so it actually works when you open it)
- **All 20 player-facing pages load** for the fresh game (was: the Economy page hard-crashed the whole server process). Fixes: forced matplotlib `Agg` backend; founders now get a `reign_start_year` (a `None` there was 500-ing the dynasty view and cascading into a chart-thread crash); `world_economy` bad `slice` filter; missing `TimeSystem.get_current_phase`.
- **650 automated tests green.**
- Screenshots of the key screens are in **`playtest-screenshots/`** (gitignored) if you want a preview before launching — world map, dynasty view, economy, military, diplomacy, espionage, family tree, chronicle book, banking.

## The core loop to try
1. **World Map** (`/world/map`) — the main screen. Hex world; click a territory for details. Right panel shows your monarch, **3 Action Points**, and **Queue Action** buttons (Recruit / Build / Develop / March / War). Bottom tabs switch overlays (Terrain / Armies / Economy / Threats / Projects).
2. **Queue a few actions**, then hit **END TURN** (top right). Turns advance ~5 years and run births/deaths/marriages + the AI rivals.
3. **Turn Report** — see what happened. (New: a 🔊 **Narrate** button reads the turn's chronicle aloud via your browser's built-in voice — no API key needed. Add an `ELEVENLABS_API_KEY` for premium narration.)
4. Advance several turns to watch the dynasty live: heirs born, the monarch ages, succession when they die (you'll be asked to crown an heir), AI rivals act.

## Feature tour (links from the dynasty view / left rail)
| Feature | Where | What to try |
|---|---|---|
| **Dynasty view** | `/dynasty/2/view` | Ruler card, family, events, interactive family tree |
| **Economy** | `/dynasty/2/economy` | Treasury, production chart, territories; build/develop |
| **Banking** | `/dynasty/2/banking` | Borrow gold vs. interest, repay |
| **Military** | `/dynasty/2/military` | Recruit units, form armies, march, battle |
| **Diplomacy** | `/dynasty/2/diplomacy` | Relations, treaties, declare war, negotiate peace |
| **🗡️ Espionage** (new) | `/dynasty/2/espionage` | Pick a court agent → dispatch **Intel / Sabotage / Assassinate** against a rival. Resolves over several turns; assassination really kills, sabotage damages a building, intel reveals hidden info. |
| **📜 Chronicle Book** (new) | `/dynasty/2/chronicle_book` | Your saga as a formatted book + **Download PDF**. Fills in as you play more turns. |
| **Family tree** | `/dynasty/2/family_tree` | Pan/zoom/search the bloodline |
| **World map / news / advisor** | top nav | The wider world + an AI advisor |

> The dynasty id is **2** (House Aldermoor). If you create your own dynasty (top nav → "New Dynasty"), it gets a new id — adjust the URLs accordingly, or just use the on-screen links.

## Known limitations / rough edges (so they don't surprise you)
- **No LLM key set** → narrative text (chronicle paragraphs, foreword/epilogue, advisor) uses **deterministic fallback prose**, not AI-written. Set `GOOGLE_API_KEY` for AI narration. Everything still works without it.
- **Chronicle Book is sparse at year 1000** — it grows a chapter per reign and fills with events as you play. Advance ~10+ turns (and through a succession) to see it become a real book.
- **Secondary matplotlib map images** on some pages fall back to no-image (the main canvas map is unaffected) — `visualization/map_renderer.py` has two methods physically defined outside the class (`render_territory_map`, `_get_dynasty_colors`); a known cosmetic bug, deferred (didn't risk a refactor right before your session). The primary play surface (the hex canvas) is fine.
- Some monarch display names read a bit awkwardly (e.g. "Lady Yuj the Strong House Aldermoor Dynasty") — the name concatenates given name + surname where the surname is the house name. Cosmetic.

## If something breaks
- The app picks a free port in **8091–8100** if 8091 is taken — read the actual URL from the startup log.
- Logs print to the console; `flask_app.log` (rotating) also captures them.
- A backup of the pre-Alembic DB is at `instance/dynastysim.db.pre-alembic-bak` if you ever need it.
- To start completely fresh, delete your dynasties from the dashboard (the delete now cleanly handles cross-dynasty marriages/trade routes).

Have fun, Barakganon. 👑
