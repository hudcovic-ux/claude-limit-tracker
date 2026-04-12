# Claude Limit Tracker

macOS menu bar plugin for tracking your [Claude.ai](https://claude.ai) usage limits (5-hour and 7-day windows) — powered by [xbar](https://xbarapp.com).

## Features

- Both limits always visible in the menu bar: `D:🤖10% · W:⚠️79%`
- Independent color-coded icons for each limit: 🤖 normal · 🟠 50%+ · ⚠️ 75%+ · 🔴 90%+
- Dropdown with progress bars, reset times, and org name
- Refreshes every minute automatically
- Falls back to cached data if the API is unreachable
- No Chrome window ever opens — reads cookies directly from Chrome's local database

## Requirements

- macOS
- [Google Chrome](https://www.google.com/chrome/) (must be logged into claude.ai at least once)
- [xbar](https://xbarapp.com) (`brew install --cask xbar`)
- Python 3

## Installation

### One command setup

```bash
git clone https://github.com/hudcovic-ux/claude-limit-tracker.git
cd claude-limit-tracker
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Verify Python 3 is available
- Install dependencies (`tls-client`, `cryptography`) automatically
- Install xbar if missing (via Homebrew)
- Fix the Python shebang to match your system
- Clean up stale symlinks and create a fresh one in xbar's plugin directory
- Run the script once to verify it works
- Refresh xbar

### After a restart

Just run `./setup.sh` again — it's idempotent and takes a few seconds.
Or if everything was already set up, simply:

```bash
open -a xbar
```

### Log into Claude.ai in Chrome

Open [claude.ai](https://claude.ai) in Chrome and log in. The plugin reads your session cookies automatically from Chrome's local database — no manual copying required.

### Allow Keychain access

On first run, macOS will ask for your login password to let the script read Chrome's encryption key from Keychain. Click **Always Allow** so it doesn't ask again.

## How it works

The plugin uses two methods to fetch data, in order:

1. **Chrome tab (AppleScript):** If you have a claude.ai tab open in Chrome, it makes the API call through that tab via JavaScript — Cloudflare lets it through because it comes from a real browser session.

2. **Direct HTTP (tls-client):** Reads your session cookies directly from Chrome's local SQLite database (decrypting them with your Keychain key), then makes the API request using a TLS fingerprint that matches Chrome — bypassing Cloudflare without needing an open browser window.

3. **Cache fallback:** If both methods fail, the last successful data is shown with a timestamp indicating how old it is.

## Menu bar format

```
D:🤖10% · W:⚠️79%
```

- **D** = daily (5-hour rolling window)
- **W** = weekly (7-day rolling window)
- Each has its own icon based on utilization level

Click the menu bar item for details: progress bars, reset times, and last update timestamp.

## Configuration

`config.json` is optional. If you have multiple Claude organizations, you can pin a specific one:

```json
{
  "org_uuid": "your-organization-uuid-here"
}
```

Leave `org_uuid` empty (default) to auto-select the organization with the highest usage.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: tls_client` | Run `./setup.sh` — it installs dependencies automatically |
| `Keychain denied` | Open Keychain Access, find "Chrome Safe Storage", grant access |
| `Cloudflare block` | Open claude.ai in Chrome — needs a fresh `cf_clearance` cookie |
| `Session expired` | Log into claude.ai in Chrome again |
| `JS disabled` | In Chrome: View → Developer → Allow JavaScript from Apple Events |
| Plugin not showing | Run `./setup.sh` to recreate the symlink and restart xbar |
| Wrong Python after update | Run `./setup.sh` — it auto-fixes the shebang |
