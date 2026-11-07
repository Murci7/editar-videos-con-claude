"""Build YouTube closed captions (SRT) from the burned-in captions: merge the 2-3-word lines into ~42-char cues.

Usage (from edit/): python ../tools/make_srt.py work/captions.ass ../subtitulos.srt
"""
import re
import sys
from pathlib import Path

MAX = 42


def secs(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def stamp(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


lines = []
for row in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if row.startswith("Dialogue:"):
        f = row.split(",", 9)
        lines.append((secs(f[1]), secs(f[2]), re.sub(r"\{[^}]*\}", "", f[9]).strip()))

cues, cur = [], None
for a, b, t in lines:
    if cur and len(cur[2]) + 1 + len(t) <= MAX and a - cur[1] < 0.8 and not cur[2].endswith((".", "?", "!")):
        cur = (cur[0], b, cur[2] + " " + t)
    else:
        if cur:
            cues.append(cur)
        cur = (a, b, t)
if cur:
    cues.append(cur)
out = "\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1))
Path(sys.argv[2]).write_text(out, encoding="utf-8")
print(f"{len(cues)} subtítulos → {sys.argv[2]}")
