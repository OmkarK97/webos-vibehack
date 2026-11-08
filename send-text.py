#!/usr/bin/env python3
"""Type into the focused text field on the TV.

Focus the field with the remote first, then paste here and press Enter.
The text is not printed. Pair once first (sync-apps.py does it).

    TV_HOST=192.168.1.50 ./venv/bin/python send-text.py
"""
import asyncio
import json
import os
import sys

import lgtv


async def recv_for(ws, seconds):
    try:
        return json.loads(await asyncio.wait_for(ws.recv(), seconds))
    except (TimeoutError, asyncio.TimeoutError):
        return None


def field_focused(msg):
    if not msg:
        return False
    return bool(((msg.get("payload") or {}).get("currentWidget") or {}).get("focus"))


async def main(host):
    print("Focus the text field on the TV, then paste here and press Enter.", flush=True)
    text = sys.stdin.readline().rstrip("\n")
    if not text:
        sys.exit("nothing to send")

    ws = await lgtv.session(host)
    try:
        await ws.send(json.dumps({
            "type": "subscribe",
            "id": "ime",
            "uri": "ssap://com.webos.service.ime/registerRemoteKeyboard",
            "payload": {},
        }))
        msg = await recv_for(ws, 3)
        if msg is None:
            print("Keyboard service was slow. Sending anyway.", flush=True)
        elif not field_focused(msg):
            print("Click the text field on the TV. Waiting 25s...", flush=True)
            deadline = asyncio.get_running_loop().time() + 25
            while asyncio.get_running_loop().time() < deadline:
                msg = await recv_for(ws, 2)
                if field_focused(msg):
                    break
            else:
                print("Still no text field. Sending anyway.", flush=True)

        # replace must be a boolean. An integer makes this firmware ignore the request.
        await ws.send(json.dumps({
            "type": "request",
            "id": "ins",
            "uri": "ssap://com.webos.service.ime/insertText",
            "payload": {"text": text, "replace": False},
        }))
        for _ in range(8):
            msg = await recv_for(ws, 2)
            if not msg or msg.get("id") != "ins":
                continue
            payload = msg.get("payload") or {}
            if payload.get("returnValue"):
                print("sent", flush=True)
            else:
                print(f"TV rejected the text: {payload.get('errorText', payload)}", flush=True)
            return
        print("The TV did not confirm. Focus the box and run this again.", flush=True)
    finally:
        await ws.close()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TV_HOST")
    if not host:
        sys.exit("usage: send-text.py <TV IP>")
    try:
        asyncio.run(main(host))
    except (OSError, TimeoutError, asyncio.TimeoutError, lgtv.websockets.WebSocketException) as e:
        sys.exit(f"Could not reach the TV: {type(e).__name__}: {e}")
