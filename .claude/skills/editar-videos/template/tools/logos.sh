#!/bin/bash
# Copy the icons of the apps you have installed (CapCut, Claude, Chrome, Cursor…) to motion/src/logos/ as PNG, for
# the graphics that show them (capcut.html). They are not shipped in the repo: they are their owners' trademarks.
# Usage (from videos/<name>/ or from the template): bash tools/logos.sh
set -uo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)/motion/src/logos"; mkdir -p "$D"
for app in "CapCut" "Claude" "Google Chrome" "Cursor" "Visual Studio Code"; do
  p="/Applications/$app.app"; [ -d "$p" ] || { echo "· $app: no está instalada"; continue; }
  icn=$(defaults read "$p/Contents/Info" CFBundleIconFile 2>/dev/null || true)
  [ -z "$icn" ] && icn=$(ls "$p/Contents/Resources/" | grep -m1 -i '\.icns$')
  f="$p/Contents/Resources/${icn%.icns}.icns"; n="app-$(echo "$app" | tr 'A-Z ' 'a-z-').png"
  if [ -f "$f" ] && sips -s format png -Z 512 "$f" --out "$D/$n" >/dev/null 2>&1; then echo "✓ $app → logos/$n"; else echo "· $app: sin icono"; fi
done
