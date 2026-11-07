"""Cut each take into its speech segments with jump-cut punch-ins and write work/take_N.mp4 + work/take_N.wav.

Even segments = wide (100 %), odd = punch-in (112 %) anchored on the face, so the face stays put.
CENTER_TAKES (e.g. CENTER_TAKES=16,19: talk-only takes with no graphics) are reframed as a close-up with the face in
the middle of the frame (ZC, odd segments 6 % tighter), so the takes are all recorded in the same spot on the right.
Cuts land on whole frames (frames()), the same ones to_capcut.py uses for the CapCut main track.
"""
import json, subprocess, sys
from pathlib import Path

import os
TAKES = Path(os.environ.get("TAKES_DIR") or ("takes" if Path("takes").is_dir() else Path.home() / "Downloads"))
WORK = Path("work"); WORK.mkdir(exist_ok=True)
FX, FY, Z = 1290, 380, 1.12          # face anchor (px) and punch-in factor
CW, CH = int(1920 / Z) // 2 * 2, int(1080 / Z) // 2 * 2
CX, CY = int(FX - FX / Z), int(FY - FY / Z)
CENTER = {int(t) for t in os.environ.get("CENTER_TAKES", "").split(",") if t.strip()}
ZC = min(1.5, max(1.3, 960 / max(1, 1920 - FX)))   # close-up that brings a right-third face to the middle


def crop(take, k):
    """(zoom, x, y, w, h) crop of segment k of a take, scaled back to 1920x1080 — or None for the full frame.
    Shared with to_capcut.py, which turns it into CapCut scale + position."""
    if take in CENTER:
        z = ZC * (1.06 if k % 2 else 1.0)
        w, h = int(1920 / z) // 2 * 2, int(1080 / z) // 2 * 2
        x = min(max(0, int(FX - w / 2)), 1920 - w)
        y = min(max(0, int(FY - 0.42 * h)), 1080 - h)
        return 1920 / w, x, y, w, h
    return (Z, CX, CY, CW, CH) if k % 2 else None
SEG = json.loads(Path("segments.json").read_text())
FPS = 30


def frames(take):
    """Speech segments of a take as [first_frame, end_frame) at 30 fps (shared with timeline.py / to_capcut.py)."""
    segs = [[round(a * FPS), round(b * FPS)] for a, b in SEG[str(take)]]
    return [s for s in segs if s[1] > s[0]]


def build(take):
    f, vouts, aouts = [], [], []
    for k, (fa, fb) in enumerate(frames(take)):
        a, b = fa / FPS, fb / FPS
        # video: frames fa..fb-1 (half-frame margins so float timestamps can't add or drop one); audio: exact span
        # frame-exact: frames fa..fb-1 and samples fa*1600..fb*1600 (48 kHz). No fps filter: it could add a frame at
        # the end of a segment, the concat would pad the audio to match, and the narration would drift against CapCut,
        # whose clips are frame-exact (seen on a 5-min video: +21 frames, the voice ~0.7 s late by the end).
        v = f"[0:v]trim=start_frame={fa}:end_frame={fb},setpts=PTS-STARTPTS"
        c = crop(take, k)
        if c:
            _, x, y, w, h = c
            v += f",crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos"
        f.append(v + f",setsar=1,format=yuv420p[v{k}]")
        d = b - a
        f.append(f"[0:a]aresample=48000,atrim=start_sample={fa * 1600}:end_sample={fb * 1600},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d=0.012,afade=t=out:st={max(0, d - 0.015):.3f}:d=0.015[a{k}]")
        vouts.append(f"[v{k}]"); aouts.append(f"[a{k}]")
    f.append("".join(v + a for v, a in zip(vouts, aouts)) + f"concat=n={len(vouts)}:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(TAKES / f"{take}.mp4"),
                    "-filter_complex", ";".join(f), "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "fast",
                    str(WORK / f"take_{take}.mp4"), "-map", "[a]", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
                    str(WORK / f"take_{take}.wav")], check=True)
    print(f"toma {take} ok", flush=True)


if __name__ == "__main__":
    for t in (sys.argv[1:] or sorted(int(k) for k in SEG)):
        build(int(t))
