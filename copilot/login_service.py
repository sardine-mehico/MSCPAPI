"""Container-friendly interactive Microsoft sign-in for headless hosts.

Runs inside the Docker image's ``login`` mode (see ``docker/entrypoint.sh``): a
real, visible Chromium is rendered to a virtual display (Xvfb) and streamed to
your browser over noVNC, so you complete the Microsoft sign-in (password, MFA,
Cloudflare) by hand. Unlike :meth:`BrowserCopilot.login`, there is no console
``input()`` to press — this polls until a signed-in token appears, snapshots the
session into the shared volume (``session/``), and exits 0. The server container
then reuses that session headlessly.

    python -m copilot.login_service     # under DISPLAY=:99 inside the container

Tunables (env): ``COPILOT_LOGIN_TIMEOUT`` (default 900s), ``COPILOT_PROXY``,
``NOVNC_PORT`` (display only, default 6080).
"""

import os
import time

from .auth import DEFAULT_AUTH_FILE, DEFAULT_PROFILE_DIR
from .browser import BrowserCopilot


def _looks_signed_in(bot: BrowserCopilot) -> bool:
    """True once MSAL has written an access token and the region isn't blocked."""
    try:
        return bool(bot.access_token()) and not bot.region_blocked()
    except Exception:
        return False


def main() -> int:
    timeout = int(os.environ.get("COPILOT_LOGIN_TIMEOUT", "900"))
    proxy = os.environ.get("COPILOT_PROXY") or None
    novnc_port = os.environ.get("NOVNC_PORT", "6080")
    poll_seconds = 3

    banner = "=" * 68
    print(banner, flush=True)
    print("Microsoft Copilot — one-time interactive login", flush=True)
    print(f"  1. Tunnel the noVNC port:  ssh -L {novnc_port}:localhost:{novnc_port} <vps>", flush=True)
    print(f"  2. Open in your browser:   http://localhost:{novnc_port}/vnc.html", flush=True)
    print("  3. Sign in to your Microsoft account in the browser window.", flush=True)
    print("  The session saves automatically once you're signed in.", flush=True)
    print(banner, flush=True)

    bot = BrowserCopilot(profile_dir=DEFAULT_PROFILE_DIR, headless=False, proxy=proxy)
    try:
        bot.start()
    except Exception as exc:
        print(f"ERROR: could not start the browser: {exc}", flush=True)
        return 1

    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            if _looks_signed_in(bot):
                # Let MSAL settle so the chat-scoped (ChatAI) token is minted
                # before we snapshot; the server also re-mints on each refresh.
                time.sleep(5)
                try:
                    auth = bot.export_auth(path=DEFAULT_AUTH_FILE, stamp=time.time())
                except Exception as exc:
                    print(f"ERROR: signed in but could not snapshot auth: {exc}", flush=True)
                    return 1
                if auth.get("access_token"):
                    print("\n[OK] Signed in. Session saved to the volume.", flush=True)
                    print("     Remove this login stack, then start the server stack.", flush=True)
                    time.sleep(3)  # let the message show in noVNC before the window closes
                    return 0
            remaining = int(deadline - time.time())
            print(f"  ...waiting for sign-in ({remaining}s left)", flush=True)
            time.sleep(poll_seconds)
    finally:
        # Clean close flushes the persistent profile (cookies + refresh token)
        # to the mounted volume. Required — a dirty exit can corrupt the profile.
        bot.close()

    print(f"\nTIMED OUT after {timeout}s without a completed sign-in.", flush=True)
    print("Re-deploy the login stack and try again.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
