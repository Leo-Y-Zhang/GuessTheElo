"""Serve the repo root and screenshot every screen of index.html with Playwright (Edge).

python tools/review.py OUTDIR [widths] [themes]
Reports console errors and sideways scrolling per screen.
"""
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
WIDTHS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "390,1366").split(",")]
THEMES = (sys.argv[3] if len(sys.argv) > 3 else "light,dark").split(",")
HEIGHT = {320: 568, 390: 844, 768: 1024, 1366: 768, 1920: 1080}


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a: None
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def click(page, name):
    for role in ("button", "tab", "link"):
        loc = page.get_by_role(role, name=name)
        if loc.count():
            loc.first.click()
            page.wait_for_timeout(700)
            return True
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{serve()}/index.html"
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        for theme in THEMES:
            for width in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": HEIGHT.get(width, 900)},
                                          color_scheme=theme)
                page = ctx.new_page()
                errors = []
                page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
                page.goto(url)
                page.wait_for_timeout(1500)
                tag = f"{theme}-{width}"
                shots = {}

                def snap(name, full=True):
                    page.screenshot(path=str(OUT / f"{tag}-{name}.png"), full_page=full)
                    shots[name] = page.evaluate(
                        "document.documentElement.scrollWidth > document.documentElement.clientWidth")

                snap("1home")
                click(page, "Start practice")
                page.wait_for_timeout(1500)
                snap("2game", full=False)
                for _ in range(20):
                    page.keyboard.press("ArrowRight")
                page.wait_for_timeout(500)
                snap("3midgame", full=False)
                page.keyboard.press("End")
                num = page.locator("input[type=number]")
                if num.count():
                    num.first.fill("1500")
                    num.first.dispatch_event("input")
                click(page, "Lock in")
                page.wait_for_timeout(2600)
                snap("4reveal")
                click(page, "Stats")
                snap("5stats")
                click(page, "About")
                snap("6about")
                click(page, "Play")
                click(page, "Play today's five")
                page.wait_for_timeout(1200)
                snap("7daily", full=False)
                report.append({"tag": tag, "sideways": shots, "errors": errors[:5]})
                ctx.close()
        browser.close()
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
