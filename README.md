# FCDex 3.0 — BallsDex V3 Extra Package

Official **FCDex 3.0** feature pack for [BallsDex V3](https://github.com/Ballsdex-Team/BallsDex-DiscordBot). Adds tournaments, clubball battles, achievements, and merging — built as a pip-installable Django extra with Discord.py Components v2 UI.

## Features

### ⚔️ Battle System

Challenge friends to clubball battles. Fill your deck randomly or with your strongest cards, then fight until one player stands.

| Command | Description |
| ------- | ----------- |
| `/battle challenge @user` | Challenge a friend to a battle |
| `/battle all` | Fill your deck with random clubballs |
| `/battle best` | Fill your deck with your strongest clubballs |
| `/battle add` / `/battle remove` | Manually manage your battle deck |

### 🏟️ Tournaments

Legacy & Main group tournaments with registration, group stage scoring, semifinals, and finals.

| Command | Description |
| ------- | ----------- |
| `/tournament create` | Create a tournament (Manage Server) |
| `/tournament join` | Join as Legacy or Main group |
| `/tournament info` | Tournament details |
| `/tournament standings` | Group leaderboards |
| `/tournament score` | Report match points |
| `/tournament start` | Begin group stage (Manage Server) |
| `/tournament advance` | Move to semifinals/finals (Manage Server) |
| `/tournament bracket` | View bracket |

### 🏅 Achievements

Player achievements with progress tracking and claimable rewards (coins / clubballs).

| Command | Description |
| ------- | ----------- |
| `/achievement list` | Browse achievements |
| `/achievement progress` | View your (or another player's) progress |
| `/achievement claim` | Claim a completed achievement |

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
location = "git+https://github.com/TheFCProject/FCDex-3.0.git@1.0.4"
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
