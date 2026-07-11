#!/bin/bash
# Smart Job Assistant — desktop app build
# Produces an installable app (DMG on macOS, NSIS on Windows, AppImage on Linux)
# in electron/release/.
set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}[1/4] Building frontend...${NC}"
cd "$SCRIPT_DIR/frontend"
[ -d node_modules ] || npm install
npm run build

echo -e "${BLUE}[2/4] Building backend binary (PyInstaller)...${NC}"
cd "$SCRIPT_DIR/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
pip install -q pyinstaller
rm -rf build dist
pyinstaller sja_backend.spec --noconfirm
deactivate

echo -e "${BLUE}[3/4] Installing Electron dependencies...${NC}"
cd "$SCRIPT_DIR/electron"
[ -d node_modules ] || npm install

echo -e "${BLUE}[4/4] Packaging desktop app (electron-builder)...${NC}"
npm run dist

echo ""
echo -e "${GREEN}Done. Installers are in electron/release/:${NC}"
ls -lh "$SCRIPT_DIR/electron/release" | grep -Ei '\.(dmg|zip|exe|AppImage)$' || true
