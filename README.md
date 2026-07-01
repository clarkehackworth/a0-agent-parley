# AgentParley — Chat Plugin for Agent Zero

Bring [Agent Zero](https://github.com/frdel/agent-zero) into Stoat/Revolt, Discord, and Slack as a teammate, not a bolted-on bot. It listens for @mentions over WebSocket/Socket Mode, builds smart context-aware conversations from channel history, and replies right in-thread — without any browser or manual polling.

## Features

- **Three platforms, one agent** — Stoat/Revolt, Discord, and Slack all wired through the same listener and context-window pipeline
- **WebSocket / Socket Mode listener** — persistent background connection per platform; responds to @mentions automatically
- **Context-aware backfill** — combines recent messages, keyword-searched history, pinned messages, and neighbor expansion into a single rich context window
- **Shell command gating** — commands are disabled by default; when enabled, they can require a password embedded in the request
- **DM password challenge** — if a password is set, the bot DMs the requester to confirm it out-of-band instead of trusting a password typed in a public channel
- **Three Agent Zero tools**
  - `revolt_read` — fetch a channel's context window on demand
  - `revolt_send` — post a message (auto-splits long replies)
  - `revolt_channels` — list every channel in the server
- **Web UI config panel** — configure credentials and tuning knobs from the Agent Zero sidebar
- **Echo prevention** — the bot never triggers itself on its own messages

## Requirements

- Agent Zero running in Docker (container name `agent-zero` by default)
- A self-hosted Revolt instance accessible from the container
- A Revolt bot account with a token
- Docker accessible via SSH at `docker.lan` (or adjust `deploy.sh`)

## Installation

### 1. Clone

```bash
git clone https://github.com/clarkehackworth/a0-agent-parley.git
cd a0-agent-parley
```

### 2. Deploy to Agent Zero

```bash
./deploy.sh
```

This copies the plugin into the container at `/a0/usr/plugins/revolt/`, then runs `initialize.py` to install Python dependencies (`aiohttp`, `pyyaml`) inside the container's virtualenv.

Add `--restart` to also bounce the container after deploy:

```bash
./deploy.sh --restart
```

> **Default target**: `docker -H ssh://docker.lan` / container `agent-zero`. Edit `deploy.sh` if your setup differs.

### 3. Configure credentials

Open Agent Zero's web UI → **Settings** → **Plugins** → **Parley (Revolt)**. Fill in:

| Field | Description |
|---|---|
| `REVOLT_URL` | Base URL of your Revolt instance, e.g. `http://stoat.lan:13080` |
| `REVOLT_BOT_TOKEN` | Token from your Revolt bot settings page |
| `REVOLT_BOT_ID` | The bot's user ID (filters the bot's own messages) |
| `REVOLT_SERVER_ID` | ID of the Revolt server (guild) to connect to |

These can also be set as environment variables on the container.

## Bot setup per platform

Each platform needs a bot account created and invited before AgentParley can connect. Minimal steps and required permissions/scopes below.

### Stoat / Revolt

1. In your Revolt server, go to **Server Settings → Bots → Create Bot** and copy the generated **token** (`REVOLT_BOT_TOKEN`) and **bot user ID** (`REVOLT_BOT_ID`).
2. Invite the bot to your server via the bot's invite link, then note the server's ID (`REVOLT_SERVER_ID`, visible in **Server Settings → Overview**).
3. Give the bot's role permission to **View Channel**, **Send Messages**, and **Read Message History** in any channel it should watch.

### Discord

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications) → **Bot** tab → **Add Bot**, then copy the **bot token** (`DISCORD_BOT_TOKEN`).
2. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent** — AgentParley requests the `GUILD_MESSAGES`, `MESSAGE_CONTENT`, and `DIRECT_MESSAGES` intents to read @mentions and DM replies.
3. Under **OAuth2 → URL Generator**, select the `bot` scope and grant **View Channels**, **Send Messages**, and **Read Message History**, then open the generated URL to invite the bot to your server (`DISCORD_GUILD_ID`).

### Slack

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps) (from scratch), then under **OAuth & Permissions → Bot Token Scopes** add: `chat:write`, `channels:read`, `channels:history`, `groups:read`, `groups:history`, `im:read`, `im:history`, `users:read`. Add `search:read` too if you want keyword backfill.
2. Under **Socket Mode**, enable it and generate an **app-level token** with the `connections:write` scope (`SLACK_APP_TOKEN`).
3. Under **Event Subscriptions**, subscribe to the `message.channels` (and `message.im` for DMs) bot events, then **Install App to Workspace** and copy the **Bot User OAuth Token** (`SLACK_BOT_TOKEN`) and workspace **Team ID** (`SLACK_TEAM_ID`).
4. Invite the bot to any channels it should watch with `/invite @yourbot`.

### 4. Enable the plugin

In the Agent Zero sidebar, enable **Parley (Revolt)**. The WebSocket listener starts automatically (`auto_start: true` by default). The bot is now online.

## Configuration reference

All settings live in `default_config.yaml` and are overridable via env vars or the web UI.

| Key / Env var | Default | Description |
|---|---|---|
| `enable_commands` | `false` | Allow Agent Zero to run shell commands when triggered by a chat message |
| `commands_password` | _(empty)_ | If `enable_commands` is true and this is set, the requester must confirm this password via a DM challenge before commands run |
| `auto_start` / `REVOLT_AUTO_START` | `true` | Start listener automatically with Agent Zero |
| `watched_channels` / `REVOLT_WATCHED_CHANNELS` | _(empty = all)_ | Comma-separated channel IDs to respond to |
| `recent_limit` / `REVOLT_RECENT_LIMIT` | `25` | Recent messages to anchor the context window |
| `search_limit` / `REVOLT_SEARCH_LIMIT` | `15` | Keyword-backfill messages to include |
| `max_age_days` / `REVOLT_MAX_AGE_DAYS` | `30` | Drop backfill hits older than N days (0 = no limit) |
| `neighbors` / `REVOLT_NEIGHBORS` | `2` | Messages fetched either side of each backfill hit |
| `expand_top` / `REVOLT_EXPAND_TOP` | `3` | Top backfill hits to expand with neighbor messages |
| `include_first` / `REVOLT_INCLUDE_FIRST` | `true` | Include the channel's oldest message in every context |
| `include_pinned` / `REVOLT_INCLUDE_PINNED` | `true` | Include pinned messages in every context |

## Project layout

```
AgentParley/
├── plugin.yaml          # Plugin manifest (name, credentials, settings)
├── default_config.yaml  # Default values for all config knobs
├── hooks.py             # Agent Zero hook: reconnect on config save
├── initialize.py        # Dependency installer (aiohttp, pyyaml)
├── deploy.sh            # One-command deploy to Docker container
│
├── tools/               # Agent Zero tools
│   ├── revolt_read.py
│   ├── revolt_send.py
│   └── revolt_channels.py
│
├── helpers/             # Shared runtime state
│   ├── revolt_listener.py   # WebSocket listener (background task)
│   ├── revolt_constants.py
│   └── revolt_sent_ids.py   # Echo prevention
│
├── core/                # Context window logic
│   ├── context_window.py
│   ├── context_config.py
│   ├── keywords.py
│   ├── formatting.py
│   └── message_split.py
│
├── infrastructure/      # Revolt API client
├── ports/               # Chat platform abstraction
├── webui/               # config.html panel
└── tests/
```

## Updating

Re-run `deploy.sh` after any code change. Add `--restart` if you changed listener startup logic or added new dependencies.

```bash
./deploy.sh --restart
```
