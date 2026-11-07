"""Brand colours for the Python side, read from motion/src/marca.css so the brand lives in one place.

Used for the title/end-screen holders (compose.py), the screen-recording cards (pantalla.py), the CapCut fill
(to_capcut.py) and the caption outline (timeline.py).
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "motion" / "src" / "marca.css"
DEFAULTS = {"bg": "#0E1116", "line": "#2A3140", "sky": "#2DD4BF", "deep": "#0F766E"}


def _read():
    vals = dict(DEFAULTS)
    if CSS.exists():
        vals.update(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", CSS.read_text(encoding="utf-8")))
    return vals


_V = _read()


def rgb(name):
    """(r, g, b) of a marca.css variable, e.g. rgb("bg")."""
    h = _V[name].lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ff(name):
    """Colour for ffmpeg filters (color=c=0xRRGGBB)."""
    return "0x" + _V[name].lstrip("#").upper()


def ass(name):
    """Colour for an ASS subtitle style (&H00BBGGRR)."""
    r, g, b = rgb(name)
    return f"&H00{b:02X}{g:02X}{r:02X}"
