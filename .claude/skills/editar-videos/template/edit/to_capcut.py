"""Turn this edit into a CapCut desktop project where every element sits on its own track, and count the edits.

  main track   every speech segment of every take = its own clip from the RAW take (in/out = segments.json, on the
               same frames as aroll.py), odd ones punched in 112 % on the face (CENTER_TAKES: centred close-up), all muted; title/end = brand colour
  overlays     full-screen graphics (pantalla, antes/después, HTML full) below, overlay graphics above, captions.mov
               on the top track; tracks allocated greedily so nothing overlaps
  audio        narration (work/narr.wav, from 0) · SFX · music bed (work/music_bed.wav, if compose.py made one)

Run after compose.py (it makes narr.wav and music_bed.wav) and captions_mov.py. Writes work/capcut_spec.json and
work/capcut_stats.json, then calls capcut_draft.py build. With CapCut open: a NEW draft is written without touching
the registry (CapCut imports it by itself, seen on 5-nov); replacing an existing one is refused (it may be open).
Usage (from edit/): python to_capcut.py [--name "Draft name"] [--no-build]
env: TAKES_DIR (raw takes N.mp4; default ./takes or ~/Downloads), CAPCUT_DRAFT (path to capcut_draft.py; default
     <project>/capcut/capcut_draft.py)
"""
import json, math, os, re, subprocess, sys
from pathlib import Path

import marca
from aroll import crop, frames   # the punch-in / close-up crops and the frame-exact cuts aroll.py made

FPS = 30
WORK, GFX = Path("work"), Path("work/gfx")
TAKES = Path(os.environ.get("TAKES_DIR") or ("takes" if Path("takes").is_dir() else Path.home() / "Downloads"))
PLAN = json.loads((WORK / "plan.json").read_text())
SLUG = Path.cwd().resolve().parent.name
NAME = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else os.environ.get("CAPCUT_NAME", SLUG)


def capcut_tool():
    """CAPCUT_DRAFT, else <project>/capcut/capcut_draft.py (copied from the template), else the nearest capcut/ above."""
    if os.environ.get("CAPCUT_DRAFT"):
        return Path(os.environ["CAPCUT_DRAFT"]).resolve()
    for d in Path(__file__).resolve().parents[1:]:
        if (d / "capcut" / "capcut_draft.py").is_file():
            return d / "capcut" / "capcut_draft.py"
    sys.exit("No encuentro capcut_draft.py (copia template/capcut/ al proyecto o define CAPCUT_DRAFT=/ruta/capcut_draft.py)")


def media_len(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=duration", "-of", "json",
                        str(path)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    ds = [float(s["duration"]) for s in j.get("streams", []) if s.get("duration")]
    return min(ds) if ds else float(j["format"]["duration"])


def fit(path, want):
    """Out point on the frame grid that never passes the end of the media (the generator refuses that)."""
    return min(round(want * FPS), math.floor(media_len(path) * FPS + 1e-6)) / FPS


def frame(t):
    return round(t * FPS)


def allocate(items):
    """Greedy: each item goes on the first track whose last clip has ended (frame-exact)."""
    tracks = []
    for it in sorted(items, key=lambda x: x["start"]):
        s = frame(it["start"])
        for t in tracks:
            if t["end"] <= s:
                break
        else:
            t = {"end": 0, "clips": []}; tracks.append(t)
        t["clips"].append(it["clip"]); t["end"] = s + frame(it["len"])
    return [t["clips"] for t in tracks]


# ---- main track: raw takes cut on the same frames as aroll.py ----
# punch-in / close-up: aroll crops w x h at (x, y) and scales it to full frame; in CapCut that is scale z around the
# centre plus a shift that puts the crop centre back in the middle of the canvas (units: half canvas, y up)
def place(take, k):
    c = crop(take, k)
    if not c:
        return {}
    z, x, y, w, h = c
    cx, cy = x + w / 2, y + h / 2
    return {"scale": round(z, 5), "x": round(-z * (cx - 960) / 960, 5), "y": round(z * (cy - 540) / 540, 5)}


brand = WORK / "capcut_brand.png"
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={marca.ff('bg')}:s=1920x1080",
                "-frames:v", "1", str(brand)], check=True)
main, n_seg, main_frames = [], 0, 0
for pc in PLAN["pieces"]:
    if isinstance(pc["item"], int):
        raw = (TAKES / f"{pc['item']}.mp4").absolute()
        for k, (fa, fb) in enumerate(frames(pc["item"])):
            c = {"source": str(raw), "in": fa / FPS, "out": fb / FPS, "volume": 0.0}
            c.update(place(pc["item"], k))
            main.append(c); n_seg += 1; main_frames += fb - fa
    else:
        main.append({"source": str(brand.absolute()), "duration": pc["dur"]})
        main_frames += frame(pc["dur"])

# ---- graphics: full-screen tracks below, overlay tracks above, captions on top ----
total = PLAN["total"]
full, ovr, sfx = [], [], []
for gph in PLAN["graphics"]:
    path = (GFX / (gph["id"] + (".mov" if gph["overlay"] else ".mp4"))).absolute()
    if not path.exists():
        sys.exit(f"falta {path} (¿render.py / pantalla.py?)")
    ln = fit(path, gph["dur"])
    (ovr if gph["overlay"] else full).append({"start": gph["start"], "len": ln, "clip": {
        "source": str(path), "start": gph["start"], "in": 0, "out": ln}})
    if gph.get("sfx"):
        w = Path("sfx", f"{gph['sfx']}.wav").absolute()
        ln = fit(w, min(media_len(w), total - gph["start"]))
        sfx.append({"start": gph["start"], "len": ln, "clip": {"source": str(w), "start": gph["start"], "in": 0, "out": ln}})
overlay_tracks = [{"name": f"Pantalla y fondos {i + 1}", "clips": c} for i, c in enumerate(allocate(full))]
overlay_tracks += [{"name": f"Gráficos {i + 1}", "clips": c} for i, c in enumerate(allocate(ovr))]
caps = WORK / "captions.mov"
if not caps.exists():
    sys.exit("falta work/captions.mov (python captions_mov.py)")
overlay_tracks.append({"name": "Subtítulos", "clips": [{"source": str(caps.absolute()), "start": 0, "in": 0,
                                                         "out": fit(caps, total)}]})

audio_tracks = [{"name": "Voz", "clips": [{"source": str((WORK / "narr.wav").absolute()), "start": 0, "in": 0,
                                           "out": fit(WORK / "narr.wav", total)}]}]
audio_tracks += [{"name": "SFX" + (f" {i + 1}" if i else ""), "clips": c} for i, c in enumerate(allocate(sfx))]
bed = WORK / "music_bed.wav"
if bed.exists():   # level, fades and ducking are already in the file (same mix as compose.py)
    audio_tracks.append({"name": "Música", "clips": [{"source": str(bed.absolute()), "start": 0, "in": 0,
                                                      "out": fit(bed, total), "volume": 1.0}]})

# ---- cover: a frame of the first take ----
cover = WORK / "capcut_cover.jpg"
first = next(p["item"] for p in PLAN["pieces"] if isinstance(p["item"], int))
fa, fb = frames(first)[0]
subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{(fa + fb) / 2 / FPS:.3f}", "-i",
                str(TAKES / f"{first}.mp4"), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(cover)], check=True)

spec = {"name": NAME, "canvas": {"width": 1920, "height": 1080, "fps": FPS}, "cover": str(cover.absolute()),
        "main_track": {"name": "Tomas (cortes)", "clips": main}, "overlay_tracks": overlay_tracks,
        "audio_tracks": audio_tracks}
(WORK / "capcut_spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))

# ---- edit count: segments + graphics + caption lines + SFX ----
n_caps = len(re.findall(r"^Dialogue:", (WORK / "captions.ass").read_text(), flags=re.M))
stats = {"draft": NAME, "segmentos": n_seg, "graficos": len(PLAN["graphics"]), "subtitulos": n_caps,
         "sfx": len(sfx), "musica": bed.exists()}
stats["ediciones"] = n_seg + stats["graficos"] + n_caps + stats["sfx"]
stats["plan_total_s"] = total
stats["pista_principal_s"] = round(main_frames / FPS, 4)
stats["pistas"] = {"video": 1 + len(overlay_tracks), "audio": len(audio_tracks)}
print(f"{stats['ediciones']} ediciones hechas por Claude = {n_seg} cortes + {stats['graficos']} gráficos + "
      f"{n_caps} subtítulos + {stats['sfx']} efectos de sonido")
print(f"pistas: {stats['pistas']['video']} de vídeo, {stats['pistas']['audio']} de audio · "
      f"pista principal {main_frames / FPS:.2f}s · plan {total:.2f}s")
if abs(main_frames / FPS - total) > 0.5 / FPS:
    sys.exit(f"la pista principal ({main_frames / FPS:.3f}s) no cuadra con el plan ({total:.3f}s)")
(WORK / "capcut_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False))   # the count, even if CapCut fails

drafts = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
if "--no-build" not in sys.argv and not (drafts / "root_meta_info.json").exists():
    print("CapCut no está instalado o no se ha abierto nunca (no existe su carpeta de proyectos): recuento hecho, "
          "proyecto de CapCut no creado. Abre CapCut una vez, crea un proyecto vacío, ciérralo y repite.")
elif "--no-build" not in sys.argv:
    tool = capcut_tool()
    running = subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0
    if running and (drafts / NAME).exists():
        sys.exit(f"CapCut está abierto y el proyecto «{NAME}» ya existe (puede estar abierto en CapCut). "
                 "Cierra CapCut (Cmd+Q) y repite: python to_capcut.py" + (f' --name "{NAME}"' if NAME != SLUG else ""))
    extra = ["--allow-running", "--no-register"] if running else []   # never touch the registry while CapCut runs
    r = subprocess.run([sys.executable, str(tool), "build", str((WORK / "capcut_spec.json").absolute()), "--force",
                        *extra], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        sys.exit(f"CapCut: {r.stderr.strip() or r.stdout.strip()}")
    folder = re.search(r"draft written: (.+?)  \(", r.stdout).group(1)
    info = json.loads((Path(folder) / "draft_info.json").read_text())
    stats["draft_s"] = info["duration"] / 1e6
    stats["draft_folder"] = folder
    stats["validado"] = r.stdout.rstrip().endswith("OK")   # capcut_draft.py validates after writing
    root = json.loads((drafts / "root_meta_info.json").read_text())
    meta = json.loads((Path(folder) / "draft_meta_info.json").read_text())
    stats["registrado"] = any(e.get("draft_fold_path") == folder and e.get("draft_id") == meta["draft_id"]
                              for e in root["all_draft_store"])
    print(f"proyecto de CapCut «{NAME}»: {stats['draft_s']:.2f}s (plan {total:.2f}s)")
    if not stats["registrado"]:
        print("  CapCut está abierto: el proyecto está escrito sin tocar su registro; suele aparecer solo en segundos. "
              "Si no, cierra CapCut (Cmd+Q) y ábrelo.")
    (WORK / "capcut_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False))
