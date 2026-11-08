"""Connection to an LG TV's remote-control service (wss://TV:3001), the one LG's phone app uses.

The first connection shows a prompt on the TV: accept it. The key and the TV's certificate
fingerprint are kept in .lgtv-key.json; when the certificate changes (new firmware), the TV asks
again.
"""
import asyncio
import hashlib
import json
import os
import ssl
import sys

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, ".lgtv-key.json")

# Unsigned on purpose: newer firmware rejects the signed manifest that open-source clients share
# ("403 Pairing rejected: blacklisted certificate detected") but still accepts an unsigned one.
PERMISSIONS = [
    "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "TEST_OPEN", "TEST_PROTECTED", "CONTROL_AUDIO",
    "CONTROL_DISPLAY", "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_RECORDING",
    "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV", "CONTROL_POWER", "CONTROL_TV_SCREEN",
    "READ_APP_STATUS", "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST", "READ_NETWORK_STATE",
    "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST", "WRITE_NOTIFICATION_TOAST", "READ_POWER_STATE",
    "READ_COUNTRY_INFO", "CONTROL_INPUT_TEXT", "CONTROL_MOUSE_AND_KEYBOARD", "READ_INSTALLED_APPS",
    "READ_SETTINGS", "READ_STORAGE_DEVICE_LIST",
]


def insecure_ctx():
    # The TV uses a certificate from LG's own CA, so session() pins it on first use instead.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def load_keys():
    try:
        with open(KEY_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


async def session(host, repair=True, **connect_args):
    keys = load_keys()
    ws = await websockets.connect(f"wss://{host}:3001", ssl=insecure_ctx(), open_timeout=10, max_size=None,
                                  **connect_args)
    der = ws.transport.get_extra_info("ssl_object").getpeercert(binary_form=True)
    cert, pin = hashlib.sha256(der).hexdigest(), f"{host} sha256"
    payload = {
        "forcePairing": False,
        "pairingType": "PROMPT",
        "manifest": {"manifestVersion": 1, "appVersion": "1.1", "permissions": PERMISSIONS},
    }
    if keys.get(pin, cert) != cert:
        # A new certificate never gets the stored key: pair again through the TV's prompt, or stop.
        if not repair:
            await ws.close()
            sys.exit(f"{host} has a new certificate. If you expected that (new firmware), run "
                     "sync-apps.py once to pair again, then retry.")
        print(f"{host} has a new certificate (new firmware?). Accept the prompt on the TV.", flush=True)
    elif host in keys:
        payload["client-key"] = keys[host]
    else:
        print("Accept the prompt on the TV...", flush=True)
    await ws.send(json.dumps({"type": "register", "id": "register_0", "payload": payload}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 60))
        if msg["type"] == "registered":
            break
        if msg["type"] == "error":
            await ws.close()
            sys.exit(f"Pairing failed: {msg.get('error')}")
    key = msg["payload"]["client-key"]
    if keys.get(host) != key or keys.get(pin) != cert:
        keys[host], keys[pin] = key, cert
        with open(KEY_FILE, "w") as f:
            json.dump(keys, f, indent=1)
    return ws


async def call(ws, uri, payload=None, n=[0]):
    n[0] += 1
    rid = f"c{n[0]}"
    await ws.send(json.dumps({"type": "request", "id": rid, "uri": uri, "payload": payload or {}}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if msg.get("id") == rid:
            return msg.get("payload", {})
