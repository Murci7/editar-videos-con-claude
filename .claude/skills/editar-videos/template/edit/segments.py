"""Find speech segments in each take (silencedetect) and tighten pauses.

Keeps 0.12 s before speech and 0.22 s after it (so the room tail isn't chopped),
caps any internal pause at ~0.34 s, and writes segments.json: {take: [[in, out], ...]} in take time.
"""
import json, re, subprocess, sys
from pathlib import Path

import os
TAKES = Path(os.environ.get("TAKES_DIR") or ("takes" if Path("takes").is_dir() else Path.home() / "Downloads"))
PRE, POST = 0.12, 0.22
FPS = 30


def silences(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:a", "-af",
                        "silencedetect=noise=-40dB:d=0.35", "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    dur = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).groups()[2]) + \
        60 * float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).groups()[1])
    if len(ends) < len(starts):
        ends.append(dur)
    return list(zip(starts, ends)), dur


def speech(sil, dur):
    segs, cur = [], 0.0
    for s, e in sil:
        if s > cur:
            segs.append([cur, s])
        cur = e
    if cur < dur:
        segs.append([cur, dur])
    return [s for s in segs if s[1] - s[0] > 0.15]


# Optional edits.json, in take time: {"trim": {"1": [0, 24.75]}, "drop": {"12": [[31.2, 31.6]]}}
# trim = keep only that window (e.g. a noise after the last word); drop = remove a slip ("Uno… Uno")
EDITS = json.loads(Path("edits.json").read_text()) if Path("edits.json").exists() else {}


def subtract(segs, cuts):
    for c0, c1 in cuts:
        segs = [p for a, b in segs for p in ([a, min(b, c0)], [max(a, c1), b]) if p[1] - p[0] > 0.05]
    return segs


out = {}
for i in sorted(int(p.stem) for p in TAKES.glob("*.mp4") if p.stem.isdigit()):
    sil, dur = silences(TAKES / f"{i}.mp4")
    sp = speech(sil, dur)
    segs = [[max(0, a - PRE), min(dur, b + POST)] for a, b in sp]
    merged = []
    for a, b in segs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    lo, hi = EDITS.get("trim", {}).get(str(i), [0, dur])
    merged = [[max(a, lo), min(b, hi)] for a, b in merged if b > lo and a < hi]
    merged = subtract(merged, EDITS.get("drop", {}).get(str(i), []))
    # snap to the 30 fps frame grid (never past the last whole frame): aroll.py, timeline.py and to_capcut.py
    # all cut on these exact frames, so the composed video and the CapCut project line up frame for frame
    vdur = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                                 "-of", "csv=p=0", str(TAKES / f"{i}.mp4")], capture_output=True, text=True).stdout.strip() or dur)
    nf = int(min(dur, vdur) * FPS + 1e-6)
    merged = [[round(a * FPS), min(round(b * FPS), nf)] for a, b in merged]
    merged = [[a / FPS, b / FPS] for a, b in merged if b > a]
    out[str(i)] = [[round(a, 4), round(b, 4)] for a, b in merged]
    kept = sum(b - a for a, b in merged)
    print(f"toma {i:2d}: {dur:5.1f}s → {kept:5.1f}s en {len(merged)} tramos")
Path("segments.json").write_text(json.dumps(out, indent=1))
print("total:", round(sum(b - a for v in out.values() for a, b in v), 1), "s")
