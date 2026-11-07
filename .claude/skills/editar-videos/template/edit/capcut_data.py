"""Export the REAL CapCut project as data for motion/src/capcut.html (the stylized CapCut timeline graphic).

Reads the draft that to_capcut.py wrote (draft_info.json), the caption lines (work/captions.ass) and the narration
(work/narr.wav), and writes motion/src/capcut-data.js + thumbnails of the first takes in motion/src/capcut-thumbs/.
Usage (from edit/, after to_capcut.py): python capcut_data.py ["Draft name"] [seconds_with_thumbs=90]
Draft name: argument, else CAPCUT_NAME, else the project folder name (what to_capcut.py uses by default).
"""
import array, json, re, subprocess, sys
from pathlib import Path

import os
NAME = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("CAPCUT_NAME") or Path.cwd().resolve().parent.name)
THUMB_S = float(sys.argv[2]) if len(sys.argv) > 2 else 90
DRAFT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft" / NAME / "draft_info.json"
SRC = Path(__file__).resolve().parent.parent / "motion/src"
THUMBS = SRC / "capcut-thumbs"

LABELS = {"pildora": "ediciones", "ni-un-clip": "ni un clip", "titulo": "Título", "rotulo": "Rótulo",
          "flujo": "Flujo", "skill": "Skill", "herramientas": "Herramientas", "paso": "Paso", "teleprompter": "Teleprompter",
          "carpeta": "Carpeta", "frase": "La frase", "onda": "Onda", "palabra": "Palabra", "claude": "Claude",
          "antes-despues": "Antes / después", "pistas": "Pistas", "revision": "Revisión", "publicacion": "Publicación",
          "coste": "Coste", "trucos": "3 trucos", "cierre": "Cierre", "barrido": "CapCut real", "capcut": "CapCut", "capcut3d": "CapCut 3D"}


def label(path):
    stem = Path(path).stem
    m = re.match(r"t\d+-(.+?)(-ov)?$", stem)
    key = m.group(1) if m else stem
    return LABELS.get(key, key.replace("-", " ").capitalize())


j = json.loads(DRAFT.read_text())
mats = {}
for kind, arr in j.get("materials", {}).items():
    if isinstance(arr, list):
        for m in arr:
            if isinstance(m, dict) and "id" in m:
                mats[m["id"]] = m
out = {"name": NAME, "dur": j["duration"] / 1e6, "tracks": []}
THUMBS.mkdir(exist_ok=True)
for f in THUMBS.glob("*.jpg"):
    f.unlink()
for t in j["tracks"]:
    name, kind = t.get("name", ""), t.get("type")
    clips = []
    for k, s in enumerate(t.get("segments", [])):
        m = mats.get(s.get("material_id"), {})
        st, du = s["target_timerange"]["start"] / 1e6, s["target_timerange"]["duration"] / 1e6
        c = {"s": round(st, 3), "d": round(du, 3), "l": label(m.get("path", ""))}
        if name.startswith("Tomas") and st < THUMB_S:          # thumbnail of the take at its in-point
            src_in = s.get("source_timerange", {}).get("start", 0) / 1e6 + min(0.4, du / 2)
            th = THUMBS / f"{k:03d}.jpg"
            seek = [] if m["path"].lower().endswith((".png", ".jpg")) else ["-ss", f"{src_in:.3f}"]
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *seek, "-i", m["path"],
                            "-frames:v", "1", "-vf", "scale=-2:120,format=yuvj420p", "-q:v", "4", str(th)], check=True)
            c["th"] = f"capcut-thumbs/{th.name}"
        if name.startswith("SFX"):
            c["l"] = Path(m.get("path", "")).stem.replace("-", " ")
        clips.append(c)
    out["tracks"].append({"name": name, "kind": kind, "clips": clips})

# captions: the real lines (the draft has them as one transparent MOV)
caps = []
for line in Path("work/captions.ass").read_text().splitlines():
    if line.startswith("Dialogue:"):
        f = line.split(",", 9)
        tt = lambda x: sum(float(v) * m for v, m in zip(x.split(":"), (3600, 60, 1)))
        caps.append({"s": round(tt(f[1]), 2), "d": round(tt(f[2]) - tt(f[1]), 2), "l": re.sub(r"\{[^}]*\}", "", f[9]).strip()})
out["captions"] = caps

# narration envelope (10 values per second, 0-1) for the voice waveform
raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "work/narr.wav", "-ac", "1", "-ar", "1000",
                      "-f", "s16le", "-"], capture_output=True, check=True).stdout
a = array.array("h", raw)
env = [max(abs(x) for x in a[i:i + 100]) if a[i:i + 100] else 0 for i in range(0, len(a), 100)]
peak = max(env) or 1
out["voice"] = [round(v / peak, 2) for v in env]
music = Path("work/music_bed.wav")
if music.exists():
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(music), "-ac", "1", "-ar", "1000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = array.array("h", raw)
    env = [max(abs(x) for x in a[i:i + 100]) if a[i:i + 100] else 0 for i in range(0, len(a), 100)]
    peak = max(env) or 1
    out["music"] = [round(v / peak, 2) for v in env]
(SRC / "capcut-data.js").write_text("window.CAPCUT = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
print(f"capcut-data.js · {len(out['tracks'])} pistas · {len(caps)} subtítulos · "
      f"{len(list(THUMBS.glob('*.jpg')))} miniaturas · música: {'sí' if 'music' in out else 'no'}")
