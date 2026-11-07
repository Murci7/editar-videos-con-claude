"""Render work/captions.ass onto a transparent 1080p PNG-in-MOV (work/captions.mov, full duration) for the CapCut
caption track. compose.py keeps burning the ASS directly; this file only feeds to_capcut.py.

Usage (from edit/): python captions_mov.py
"""
import json, subprocess
from pathlib import Path

WORK = Path("work")
total = json.loads((WORK / "plan.json").read_text())["total"]
fonts = Path("fonts").resolve()
# YUVA canvas, like the yuv420p video compose.py burns onto: on an RGB canvas libass maps white to TV range (235)
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", f"color=c=black@0.0:s=1920x1080:r=30:d={total},format=yuva444p",
                "-vf", f"subtitles={WORK / 'captions.ass'}:fontsdir={fonts}:alpha=1",
                "-frames:v", str(int(round(total * 30))), "-c:v", "png", "-pix_fmt", "rgba",
                str(WORK / "captions.mov")], check=True)
print(f"captions.mov listo ({total:.1f}s)")
