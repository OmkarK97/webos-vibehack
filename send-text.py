#!/usr/bin/env python3
"""Type into the focused text field on the TV.

Focus the field with the remote first, then paste here and press Enter.
The text is not printed. Pair once first (sync-apps.py does it).

    TV_HOST=192.168.1.50 ./venv/bin/python send-text.py
"""
import asyncio
import getpass
import json
import os
import sys

import lgtv


async def recv_for(ws, seconds, rid=None):
    """The next message (with this id, if given), or None after `seconds`."""
    async def recv():
        while True:
            msg = json.loads(await ws.recv())
            if rid is None or msg.get("id") == rid:
                return msg
    try:
        return await asyncio.wait_for(recv(), seconds)
    except (TimeoutError, asyncio.TimeoutError):
        return None


def field_focused(msg):
    if not msg:
        return False
    return bool(((msg.get("payload") or {}).get("currentWidget") or {}).get("focus"))


async def main(host):
    print("Focus the text field on the TV, then paste here and press Enter.", flush=True)
    text = getpass.getpass("") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
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
        elif msg.get("type") == "error":
            print(f"Keyboard service error: {msg.get('error')}. Sending anyway.", flush=True)
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
        msg = await recv_for(ws, 15, "ins")
        if msg is None:
            sys.exit("The TV did not confirm. Check the field before running this again.")
        payload = msg.get("payload") or {}
        if msg.get("type") == "error" or not payload.get("returnValue"):
            reason = msg.get("error") or payload.get("errorText", "no reason given")
            sys.exit(f"TV rejected the text: {reason}")
        print("sent", flush=True)
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
