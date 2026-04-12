#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="claude_limits.1m.py"
PLUGIN_SRC="$SCRIPT_DIR/$PLUGIN_NAME"
XBAR_PLUGIN_DIR="$HOME/Library/Application Support/xbar/plugins"

echo "=== Claude Limit Tracker – Setup ==="
echo ""

# --- 1. Python ---
PYTHON="/usr/local/bin/python3.14"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3 2>/dev/null || true)"
fi
if [ -z "$PYTHON" ]; then
  echo "❌ Python 3 nenalezen. Nainstaluj z https://python.org"
  exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# --- 2. Závislosti ---
echo ""
echo "📦 Kontroluji závislosti..."
MISSING=0
$PYTHON -c "import tls_client" 2>/dev/null || MISSING=1
$PYTHON -c "import cryptography" 2>/dev/null || { MISSING=1; }

if [ "$MISSING" -eq 1 ]; then
  echo "   Instaluji tls-client + cryptography..."
  $PYTHON -m pip install tls-client cryptography --break-system-packages -q
  echo "✅ Závislosti nainstalovány"
else
  echo "✅ Závislosti OK"
fi

# --- 3. xbar ---
if ! command -v xbar &>/dev/null && [ ! -d "/Applications/xbar.app" ]; then
  echo ""
  echo "📦 Instaluji xbar..."
  if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew nenalezen. Nainstaluj z https://brew.sh"
    exit 1
  fi
  brew install --cask xbar
  echo "✅ xbar nainstalován"
else
  echo "✅ xbar OK"
fi

# --- 4. Spustit xbar + plugin dir ---
open -a xbar 2>/dev/null || true
sleep 2
mkdir -p "$XBAR_PLUGIN_DIR"

# --- 5. Shebang ---
CURRENT_SHEBANG=$(head -1 "$PLUGIN_SRC")
DESIRED_SHEBANG="#!$PYTHON"
if [ "$CURRENT_SHEBANG" != "$DESIRED_SHEBANG" ]; then
  sed -i '' "1s|.*|$DESIRED_SHEBANG|" "$PLUGIN_SRC"
  echo "✅ Shebang opraven → $PYTHON"
fi

# --- 6. Symlink + chmod ---
echo ""
PLUGIN_LINK="$XBAR_PLUGIN_DIR/$PLUGIN_NAME"
# Vyčistit staré symlinky
rm -f "$XBAR_PLUGIN_DIR/claude_limits.5m.py" 2>/dev/null || true
rm -f "$PLUGIN_LINK" 2>/dev/null || true
ln -s "$PLUGIN_SRC" "$PLUGIN_LINK"
chmod +x "$PLUGIN_SRC"
echo "✅ Plugin propojen: $PLUGIN_LINK"

# --- 7. Test ---
echo ""
echo "🔍 Testuju..."
OUTPUT=$($PYTHON "$PLUGIN_SRC" 2>&1 | head -1)
echo "   $OUTPUT"
echo "✅ Funguje!"

# --- 8. Refresh xbar ---
echo ""
open "xbar://app.xbar.open" 2>/dev/null || true
echo "=== Hotovo! ==="
echo "V menu baru uvidíš: D:🤖X% · W:🤖Y%"
echo "Plugin čte cookies přímo z Chrome – stačí být přihlášený na claude.ai."
