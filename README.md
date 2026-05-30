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

| Command | Description |
| ------- | ----------- |
| `/tournament manage` | Ephemeral admin hub — create, edit, host, delete, announce |
| `/tournament bounty` | Ephemeral admin vault — drop/stash loot, rules, betting |
| `/tournament view` | Player hub — overview, standings, bracket, join |
| `/tournament match` | Pending matches — **Start battle**, verify win, claim bounties |
| `/tournament bet` | Wager coins on a match participant |
| `/tournament rules` | Read tournament rules and betting info |

### 🏅 Achievements

Player achievements with progress tracking and claimable rewards (coins / clubballs).

| Command | Description |
| ------- | ----------- |
| `/achievement menu` | Hub — catalog, progress, claim |

Configure achievements in the **admin panel** under FCDex 3.0.

### ✨ Merge System

Sacrifice two clubballs to receive a random new clubball.

| Command | Description |
| ------- | ----------- |
| `/merge clubs` | Merge two clubballs into a random club |

## Installation

This package uses the [BallsDex V3 extras system](https://wiki.ballsdex.com/dev/custom-package/).

### 1 — Configure `extra.toml`

Add to `config/extra.toml` in your BallsDex directory:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/ariel-aram/FCDex-3.0.git@1.5.0"
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

### 3 — Configure achievements (optional)

Open the admin panel and create `Achievement` entries under **FCDex 3.0**. Set type, required count, and rewards.

## Requirements

- BallsDex **V3** (3.0.0+) — must already be installed; this extra does not pull `ballsdex` from PyPI
- Python **3.12+**

## License

MIT — credits to the original BallsDex authors must not be removed when distributing.
