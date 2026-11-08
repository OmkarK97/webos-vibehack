#!/usr/bin/env bash
# Sync the TV's apps, package the launcher and install it on an LG TV in Developer Mode.
#   TV_HOST=192.168.1.50 ./install.sh
# One-time setup (Developer Mode app open on the TV, Key Server on):
#   ares-setup-device -a lgtv -i "{'host':'$TV_HOST','port':'9922','username':'prisoner'}"
#   ares-novacom --device lgtv --getkey          # enter the passphrase shown on the TV
#   ares-setup-device -m lgtv -i "{'privatekey':'lgtv_webos','passphrase':'<passphrase>'}"
set -euo pipefail
cd "$(dirname "$0")"
: "${TV_HOST:?set TV_HOST to the TV IP address, e.g. TV_HOST=192.168.1.50 $0}"
DEVICE="${DEVICE:-lgtv}"
APP_ID=com.gathin.tvhome
command -v ares-package >/dev/null || command -v npx >/dev/null ||
  { echo "Put Node.js (npx) or LG's webOS CLI on PATH first." >&2; exit 1; }

# LG's webOS CLI: use it from PATH, otherwise fetch it with npx.
ares() {
  if command -v "ares-$1" >/dev/null; then "ares-$1" "${@:2}"
  else npx -y -p @webos-tools/cli "ares-$1" "${@:2}"; fi
}

PY="${PY:-python3}"
[ -x venv/bin/python ] && PY=venv/bin/python
"$PY" sync-apps.py "$TV_HOST"

if [ ! -f app/icon.png ]; then
  # The webOS app list wants PNG icons: 80px and 130px.
  if command -v sips >/dev/null; then
    sips -s format png -z 80 80 assets/icon.jpg --out app/icon.png >/dev/null
    sips -s format png -z 130 130 assets/icon.jpg --out app/largeIcon.png >/dev/null
  else
    "$PY" - << 'PY'
from PIL import Image
im = Image.open("assets/icon.jpg").convert("RGBA")
im.resize((80, 80), Image.LANCZOS).save("app/icon.png")
im.resize((130, 130), Image.LANCZOS).save("app/largeIcon.png")
PY
  fi
fi

rm -rf build && mkdir build
ares package app -o build
ares install -d "$DEVICE" build/${APP_ID}_*.ipk
ares launch -d "$DEVICE" "$APP_ID"
echo "Installed. Hold a number key on the remote while it is open to make it a one-press shortcut."
