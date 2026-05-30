# FCDex 3.0 — BallsDex V3 Extra Package

Official **FCDex 3.0** feature pack for [BallsDex V3](https://github.com/Ballsdex-Team/BallsDex-DiscordBot). Adds tournaments, clubball battles, achievements, and merging — built as a pip-installable Django extra with Discord.py Components v2 UI.

## Features

### ⚔️ Battle System

Challenge friends to clubball matches. Pick lineups from the match panel, lock in, and watch live commentary.

| Command | Description |
| ------- | ----------- |
| `/battle challenge @user` | Start a match (Components v2 panel) |
| `/battle card` | Add or remove a specific clubball from your lineup |

Lineup buttons on the match panel: **Random**, **Strongest**, **Clear**, **Lock Selection**, **Cancel Match**.

### 🏟️ Tournaments

Legacy & Main group tournaments with battle-verified matches, bounties, betting, and bracket progression.

Points are earned only from verified match wins (**+3** each). Hosts advance rounds once all bracket matches are complete.

Registration stays open until the host **starts group stage** in `/tournament manage` (or scheduled end passes) — a passed scheduled start does not close signup.

| Command | Description |
| ------- | ----------- |
| `/tournament manage` | Ephemeral admin hub — create, edit, host, bounty vault, delete, announce |
| `/tournament view` | Player hub — overview, standings, bracket, join |
| `/tournament match` | Pending matches — **Start battle**, verify win, claim bounties |
| `/tournament bet` | Wager coins on a match participant |
| `/tournament rules` | Read tournament rules and betting info |

Use `/fcdex menu` for a single hub listing every FCDex command group.

### 🏅 Achievements

Player achievements with progress tracking and claimable rewards (coins / clubballs).

| Command | Description |
| ------- | ----------- |
| `/achievement menu` | Hub — catalog, progress, claim |

Configure achievements in the **admin panel** under FCDex 3.0.

### ✨ Merge forge

Sacrifice two clubballs to craft a new card with the **FCDex Merge** special (custom background from the extra’s merge card art). The result inherits one of your parent club types — not a random unrelated ball.

| Command | Description |
| ------- | ----------- |
| `/fcdex menu` | Directory of all FCDex 3.0 features |
| `/merge menu` | Step-by-step merge forge (Components v2) |
| `/merge clubs` | Quick merge with two chosen cards |
| `/merge info` | How merge specials work |

On install, the extra **creates or repairs** the merge special in your database and reloads the BallsDex cache automatically.

## Installation

This package uses the [BallsDex V3 extras system](https://wiki.ballsdex.com/dev/custom-package/).

### 1 — Configure `extra.toml`

Add to `config/extra.toml` in your BallsDex directory:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/ariel-aram/FCDex-3.0.git@1.6.0"
path = "fcdex_3_0"
enabled = true
```

**Local development** (with Docker):

```toml
[[ballsdex.packages]]
location = "/code/extra/FCDex-3.0"
path = "fcdex_3_0"
enabled = true
editable = true
```

### 2 — Rebuild and migrate

```bash
docker compose build
docker compose up -d
```

Migrations run automatically via the migration service.

Apply through **`0006`** if upgrading from an earlier 1.5.x install (schedule help-text sync only; no data changes).

### 3 — Configure achievements (optional)

Open the admin panel and create `Achievement` entries under **FCDex 3.0**. Set type, required count, and rewards.

## Requirements

- BallsDex **V3** (3.0.0+) — must already be installed; this extra does not pull `ballsdex` from PyPI
- Python **3.12+**

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check fcdex_3_0 tests
python -m ruff format fcdex_3_0 tests
python -m pytest tests -q
python -m pyright fcdex_3_0
```

## License

MIT — credits to the original BallsDex authors must not be removed when distributing.
