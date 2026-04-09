# Claude Limit Tracker

macOS menu bar plugin for tracking your [Claude.ai](https://claude.ai) usage limits (5-hour and 7-day windows) — powered by [xbar](https://xbarapp.com).

## Features

- Live usage percentage always visible in the menu bar
- Shows both 5-hour and 7-day limit windows with progress bars
- Color-coded icons: 🤖 normal · 🟠 50%+ · ⚠️ 75%+ · 🔴 90%+
- Refreshes every minute automatically
- Falls back to cached data if the API is unreachable
- No Chrome window ever opens — reads cookies directly from Chrome's local database

## Requirements

- macOS
- [Google Chrome](https://www.google.com/chrome/) (must be logged into claude.ai at least once)
- [xbar](https://xbarapp.com) (`brew install --cask xbar`)
- Python 3 with two packages:

```bash
pip3 install tls-client cryptography
```

## Installation

### 1. Install xbar

```bash
brew install --cask xbar
```

Or download from [xbarapp.com](https://xbarapp.com).

### 2. Install Python dependencies

```bash
pip3 install tls-client cryptography
```

### 3. Clone this repo

```bash
git clone https://github.com/hudcovic-ux/claude-limit-tracker.git
cd claude-limit-tracker
```

### 4. Run the setup script

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Verify Python 3 and xbar are installed
- Install Python dependencies (`tls-client`, `cryptography`)
- Create a symlink from the plugin to xbar's plugin directory
- Run the script once to verify it works

### 5. Log into Claude.ai in Chrome

Open [claude.ai](https://claude.ai) in Chrome and log in. The plugin reads your session cookies automatically from Chrome's local database — no manual copying required.

### 6. Allow Keychain access

On first run, macOS will ask for your login password to let the script read Chrome's encryption key from Keychain. Click **Always Allow** so it doesn't ask again on every refresh.

## How it works

The plugin uses two methods to fetch data, in order:

1. **Chrome tab (AppleScript):** If you have a claude.ai tab open in Chrome, it makes the API call through that tab via JavaScript — Cloudflare lets it through because it comes from a real browser session.

2. **Direct HTTP (tls-client):** Reads your session cookies directly from Chrome's local SQLite database (decrypting them with your Keychain key), then makes the API request using a TLS fingerprint that matches Chrome — bypassing Cloudflare without needing an open browser window.

3. **Cache fallback:** If both methods fail, the last successful data is shown with a timestamp indicating how old it is.

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
| `Keychain denied` | Open Keychain Access, find "Chrome Safe Storage", grant access |
| `Cloudflare block` | Open claude.ai in Chrome — the direct cookie method needs a fresh `cf_clearance` cookie |
| `Session expired` | Log into claude.ai in Chrome again |
| `JS disabled` | In Chrome: View → Developer → Allow JavaScript from Apple Events |
| Plugin not showing | Make sure xbar is running and the symlink is in `~/Library/Application Support/xbar/plugins/` |
