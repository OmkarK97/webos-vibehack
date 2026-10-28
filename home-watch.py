#!/usr/bin/env python3
"""Make the Home button open the launcher instead of LG's home.

webOS does not let an app replace Home, or even see which app is in front, so this runs on
another always-on device on the same network (a Mac, a Raspberry Pi, a phone in Termux). It
watches the foreground app over the TV's remote-control service and, the moment LG's home
appears, launches the launcher on top. LG's home shows for about half a second.

Press Home twice within ESCAPE_SECONDS to stay on LG's home (for its menus).

    python3 home-watch.py 192.168.1.50

Needs: pip install websockets. Pair once first (sync-apps.py does it).
"""
import asyncio
import json
import os
import sys
import time

import lgtv

LAUNCHER = "com.gathin.tvhome"
LG_HOME = {"com.webos.app.home", "com.webos.app.fullhome"}   # fullhome: webOS 5's overlay home bar
ESCAPE_SECONDS = 3.0


def log(*args):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


async def launch(ws):
    await ws.send(json.dumps({"type": "request", "id": "launch", "uri": "ssap://system.launcher/launch",
                              "payload": {"id": LAUNCHER}}))


async def watch(ws, just_on):
    last_redirect = float("-inf")
    try:
        await ws.send(json.dumps({"type": "subscribe", "id": "fg",
                                  "uri": "ssap://com.webos.applicationManager/getForegroundAppInfo",
                                  "payload": {"extraInfo": True}}))
        # webOS 5 hides its boot-time home bar after a few seconds, often before we reconnect, so
        # watch the power state too: the TV coming on (from standby, or right after it was
        # unreachable) opens the launcher.
        await ws.send(json.dumps({"type": "subscribe", "id": "power",
                                  "uri": "ssap://com.webos.service.tvpower/power/getPowerState"}))
        home_open = False
        active = not just_on
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("id") == "power":
                payload = msg.get("payload", {})
                if payload.get("processing"):
                    continue
                was_active, active = active, payload.get("state") == "Active"
                if active != was_active:
                    log("power:", payload.get("state"))
                if active and not was_active:
                    await launch(ws)
                    log("TV turned on -> launcher")
                continue
            if msg.get("id") != "fg":
                continue
            # extraInfo lists every foreground window: on webOS 5 the home bar opens over the app
            # instead of replacing it, so the plain appId never changes.
            payload = msg.get("payload", {})
            windows = payload.get("foregroundAppInfo") or [payload]
            was_open, home_open = home_open, any(
                w.get("appId") in LG_HOME or w.get("windowType") == "_WEBOS_WINDOW_TYPE_HOME" for w in windows)
            if not home_open or was_open:
                continue
            now = time.monotonic()
            if now - last_redirect < ESCAPE_SECONDS:
                log("Home pressed twice: staying on LG home")
                last_redirect = float("-inf")
                continue
            last_redirect = now
            await launch(ws)
            log("LG home -> launcher")
    finally:
        await ws.close()


async def main(host):
    failures, last_failure = 0, float("-inf")
    while True:
        # Connecting right after a run of failures means the TV just came on. A single failure is
        # a network blip, and a long gap since the last failure means this Mac was asleep; either
        # way the TV may be mid-show, so leave it alone.
        just_on = failures >= 2 and time.time() - last_failure < 60
        try:
            ws = await lgtv.session(host, ping_interval=10, ping_timeout=10)
            log("connected to", host)
            failures = 0
            await watch(ws, just_on)
        except (OSError, asyncio.TimeoutError, lgtv.websockets.WebSocketException) as e:
            # TV off, in standby or off the network: keep trying, quickly enough to catch it waking.
            log("not connected:", type(e).__name__, e)
            failures, last_failure = failures + 1, time.time()
        await asyncio.sleep(3)


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TV_HOST")
    if not host:
        sys.exit("usage: home-watch.py <TV IP>")
    try:
        asyncio.run(main(host))
    except KeyboardInterrupt:
        pass
