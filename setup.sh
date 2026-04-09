#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="claude_limits.1m.py"
PLUGIN_SRC="$SCRIPT_DIR/$PLUGIN_NAME"
XBAR_PLUGIN_DIR="$HOME/Library/Application Support/xbar/plugins"

echo "=== Claude Limit Tracker – Setup ==="
echo ""

# --- 1. Kontrola Pythonu ---
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 nenalezen. Nainstaluj ho z https://python.org"
  exit 1
fi
echo "✅ Python 3: $(python3 --version)"

# --- 2. Instalace závislostí ---
echo ""
echo "📦 Instaluji Python závislosti..."
pip3 install tls-client cryptography --quiet
echo "✅ tls-client + cryptography nainstalovány"

# --- 3. Instalace xbar ---
if ! command -v xbar &>/dev/null && [ ! -d "/Applications/xbar.app" ]; then
  echo ""
  echo "📦 Instaluji xbar přes Homebrew..."
  if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew není nainstalovaný. Nainstaluj ho z https://brew.sh"
    exit 1
  fi
  brew install --cask xbar
  echo "✅ xbar nainstalován"
else
  echo "✅ xbar již nainstalován"
fi

# --- 4. Otevřít xbar a nastavit plugin dir ---
open -a xbar 2>/dev/null || true
sleep 2

if [ ! -d "$XBAR_PLUGIN_DIR" ]; then
  mkdir -p "$XBAR_PLUGIN_DIR"
  echo "📁 Vytvořen plugin adresář: $XBAR_PLUGIN_DIR"
fi

# --- 5. Symlink pluginu ---
echo ""
PLUGIN_LINK="$XBAR_PLUGIN_DIR/$PLUGIN_NAME"

if [ -L "$PLUGIN_LINK" ]; then
  rm "$PLUGIN_LINK"
fi

ln -s "$PLUGIN_SRC" "$PLUGIN_LINK"
chmod +x "$PLUGIN_SRC"
echo "✅ Plugin propojen: $PLUGIN_LINK → $PLUGIN_SRC"

# --- 6. Test skriptu ---
echo ""
echo "🔍 Testuju skript..."
python3 "$PLUGIN_SRC" && echo "" && echo "✅ Skript funguje"

# --- 7. Refresh xbar ---
echo ""
echo "🔄 Restartuji xbar pluginy..."
open "xbar://app.xbar.open?pluginPath=$PLUGIN_NAME" 2>/dev/null || true

echo ""
echo "=== Hotovo! ==="
echo "V menu baru bys měl vidět ikonu 🤖 s procentem využití."
echo "Při prvním spuštění tě macOS požádá o heslo pro přístup k Keychain – klikni Always Allow."
