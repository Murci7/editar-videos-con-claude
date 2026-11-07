"""Read whisper.cpp word-level JSON and print a timed transcript, flagging long pauses.

Usage: python words.py TX_DIR [take ...]
"""
import json, sys
from pathlib import Path


def words(path):
    data = json.loads(Path(path).read_text())
    out = []
    for seg in data["transcription"]:
        t = seg["text"].strip()
        if t:
            out.append((seg["offsets"]["from"] / 1000, seg["offsets"]["to"] / 1000, t))
    return out


if __name__ == "__main__":
    tx = Path(sys.argv[1])
    takes = sys.argv[2:] or [str(i) for i in sorted(int(p.stem) for p in tx.glob("*.json") if p.stem.isdigit())]
    for k in takes:
        w = words(tx / f"{k}.json")
        print(f"\n=== TOMA {k}  ({w[0][0]:.2f} → {w[-1][1]:.2f})")
        line, start, prev = [], w[0][0], w[0][0]
        for t0, t1, t in w:
            if t0 - prev > 0.6 and line:
                print(f"  {start:6.2f}  {' '.join(line)}")
                print(f"         ·· pausa {t0 - prev:.1f}s")
                line, start = [], t0
            if len(line) >= 14:
                print(f"  {start:6.2f}  {' '.join(line)}")
                line, start = [], t0
            line.append(t); prev = t1
        if line:
            print(f"  {start:6.2f}  {' '.join(line)}")
