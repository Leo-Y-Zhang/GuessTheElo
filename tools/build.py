"""Build the standalone page: src/app.html -> index.html.

Inlines the cburnett piece SVGs as data URIs (no extra requests), moves the
head-only tags into <head>, and wraps everything in a complete HTML document.
Run from the repository root:  python tools/build.py
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "app.html"
OUT = ROOT / "index.html"
PIECES = ROOT / "assets" / "pieces"

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='6' fill='%236E1622'/%3E"
    "%3Crect x='5' y='9' width='22' height='14' rx='2' fill='%23B9C2A6'/%3E"
    "%3Ctext x='16' y='20.5' font-family='monospace' font-size='10' font-weight='700' "
    "text-anchor='middle' fill='%231C2418'%3EELO%3C/text%3E%3C/svg%3E"
)

DESCRIPTION = (
    "Watch a real rated Lichess game move by move with the players' real clocks, "
    "then guess their average rating and try to beat the model."
)


def pieces() -> dict:
    out = {}
    for colour in "wb":
        for piece in "KQRBNP":
            svg = (PIECES / f"{colour}{piece}.svg").read_bytes()
            out[colour + piece] = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
    return out


def build() -> str:
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if src.count("__PIECES__") != 1:
        raise SystemExit("expected exactly one __PIECES__ placeholder in src/app.html")
    src = src.replace("__PIECES__", json.dumps(pieces()))
    split = src.index("<style>")
    head_part, body_part = src[:split], src[split:]
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        f'<meta name="description" content="{DESCRIPTION}">\n'
        f'<link rel="icon" href="{FAVICON}">\n'
        "<style>body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}"
        "[hidden]{display:none!important}</style>\n"
        + head_part.strip() + "\n</head>\n<body>\n"
        + body_part.strip() + "\n</body>\n</html>\n"
    )


if __name__ == "__main__":
    html = build()
    OUT.write_bytes(html.encode("utf-8"))
    print(f"wrote {OUT.name}: {len(html):,} bytes")
