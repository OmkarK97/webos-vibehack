#!/usr/bin/env bash
# Sync the TV's apps, package the launcher and install it on an LG TV in Developer Mode.
#   TV_HOST=192.168.1.50 ./install.sh
# On a 21:9 ultrawide screen, also set the resolution webOS renders the app at (default 1920x1080):
#   TV_HOST=192.168.1.50 RESOLUTION=2560x1080 ./install.sh
# One-time setup (Developer Mode app open on the TV, Key Server on):
#   ares-setup-device -a lgtv -i "{'host':'$TV_HOST','port':'9922','username':'prisoner'}"
#   ares-novacom --device lgtv --getkey          # enter the passphrase shown on the TV
#   ares-setup-device -m lgtv -i "{'privatekey':'lgtv_webos','passphrase':'<passphrase>'}"
set -euo pipefail
cd "$(dirname "$0")"
: "${TV_HOST:?set TV_HOST to the TV IP address, e.g. TV_HOST=192.168.1.50 $0}"
DEVICE="${DEVICE:-lgtv}"
APP_ID=com.gathin.tvhome
RESOLUTION="${RESOLUTION:-1920x1080}"
[[ "$RESOLUTION" =~ ^[0-9]+x[0-9]+$ ]] || { echo "RESOLUTION must look like 1920x1080, got '$RESOLUTION'" >&2; exit 1; }

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
  sips -s format png -z 80 80 assets/icon.jpg --out app/icon.png >/dev/null
  sips -s format png -z 130 130 assets/icon.jpg --out app/largeIcon.png >/dev/null
fi

rm -rf build && mkdir build
# Package a copy, so app/appinfo.json stays as it is while the resolution follows RESOLUTION.
cp -R app build/app
sed -E "s/(\"resolution\": *\")[0-9]+x[0-9]+\"/\1$RESOLUTION\"/" app/appinfo.json > build/app/appinfo.json
ares package build/app -o build
ares install -d "$DEVICE" build/${APP_ID}_*.ipk
ares launch -d "$DEVICE" "$APP_ID"
echo "Installed. Hold a number key on the remote while it is open to make it a one-press shortcut."
