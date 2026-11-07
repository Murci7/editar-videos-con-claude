"""Compose the final video from plan.json.

1. A-roll: cut takes + brand-colour holders for the title card and end screen (concat demuxer; colour from marca.css).
2. Narration: cut take audio + silences → cleaned (high-pass, compression) → loudness -14 LUFS.
3. Graphics on top at their scheduled times (full-screen mp4 or transparent overlay mov; full-screen ones below the
   overlays, as in the CapCut project), SFX (sfx/*.wav) under them.
4. Optional music bed: music.wav (or --music PATH) levelled to MUSIC_LUFS, looped to length, fade in, 3 s fade out,
   gently ducked under the voice → work/music_bed.wav (to_capcut.py puts this same file on the CapCut music track).
5. Burned-in captions (captions.ass) → render/<project-folder>-final.mp4

Usage: python compose.py [--preview] [--music PATH]   (--preview = 720p, fast, for a quick look)
"""
import json, subprocess, sys
from pathlib import Path

import marca

WORK, GFX, OUT = Path("work"), Path("work/gfx"), Path("render")
OUT.mkdir(exist_ok=True)
PLAN = json.loads((WORK / "plan.json").read_text())
PREVIEW = "--preview" in sys.argv
MUSIC = Path(sys.argv[sys.argv.index("--music") + 1]) if "--music" in sys.argv else Path("music.wav")
MUSIC_LUFS = -27          # music bed level (narration is -14 LUFS); the ducking takes ~5 dB more off under the voice


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a], check=True)


# ---- 1. A-roll video ----
lst = []
for p in PLAN["pieces"]:
    if isinstance(p["item"], int):
        lst.append(f"file 'take_{p['item']}.mp4'")
    else:
        holder = WORK / f"hold_{p['item']}.mp4"
        ff("-f", "lavfi", "-i", f"color=c={marca.ff('bg')}:s=1920x1080:r=30:d={p['dur']}", "-c:v", "libx264", "-crf", "16",
           "-preset", "fast", "-pix_fmt", "yuv420p", str(holder))
        lst.append(f"file '{holder.name}'")
(WORK / "aroll.txt").write_text("\n".join(lst) + "\n")
ff("-f", "concat", "-safe", "0", "-i", str(WORK / "aroll.txt"), "-c", "copy", str(WORK / "aroll.mp4"))

# ---- 2. Narration ----
alist = []
for p in PLAN["pieces"]:
    if isinstance(p["item"], int):
        # fit each take's audio to its video length so A/V offsets never add up across takes
        vdur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                               str(WORK / f"take_{p['item']}.mp4")], capture_output=True, text=True).stdout.strip()
        fit = WORK / f"fit_{p['item']}.wav"
        ff("-i", str(WORK / f"take_{p['item']}.wav"), "-af", "apad", "-t", vdur, "-c:a", "pcm_s24le", str(fit))
        alist.append(f"file '{fit.name}'")
    else:
        sil = WORK / f"sil_{p['item']}.wav"
        ff("-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={p['dur']}", "-c:a", "pcm_s24le", str(sil))
        alist.append(f"file '{sil.name}'")
(WORK / "audio.txt").write_text("\n".join(alist) + "\n")
ff("-f", "concat", "-safe", "0", "-i", str(WORK / "audio.txt"), "-c:a", "pcm_s24le", str(WORK / "narr_raw.wav"))
CHAIN = "highpass=f=80,lowpass=f=15000,acompressor=threshold=-21dB:ratio=3:attack=5:release=90:makeup=2"
# two-pass loudness normalisation
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(WORK / "narr_raw.wav"), "-af",
                    CHAIN + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
LN = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
ff("-i", str(WORK / "narr_raw.wav"), "-af", CHAIN + "," + LN, "-ar", "48000", "-c:a", "pcm_s24le", str(WORK / "narr.wav"))

# ---- 4. Music bed (optional) ----
bed = WORK / "music_bed.wav"
bed.unlink(missing_ok=True)
if MUSIC.exists():
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(MUSIC), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    gain = MUSIC_LUFS - float(json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"])
    T = PLAN["total"]
    W = PLAN.get("music") or []
    if W:   # music only where it should play (schedule.py MUSICA): [start, end, offset in the track], soft in/out
        n = len(W)
        parts = [f"[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain:.2f}dB,asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
        for i, (a, b, o) in enumerate(W):
            d = b - a
            fi = 0.4 if a < 0.5 else 0.8
            parts.append(f"[s{i}]atrim={o:.3f}:{o + d:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={fi},"
                         f"afade=t=out:st={max(0, d - 1.2):.3f}:d=1.2,adelay={int(a * 1000)}|{int(a * 1000)}[w{i}]")
        parts.append("".join(f"[w{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad[m]")
        src = ["-i", str(MUSIC)]
    else:
        parts = [f"[0:a]atrim=0:{T},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={gain:.2f}dB,"
                 f"afade=t=in:d=2,afade=t=out:st={max(0, T - 3):.3f}:d=3[m]"]
        src = ["-stream_loop", "-1", "-i", str(MUSIC)]
    ff(*src, "-i", str(WORK / "narr.wav"), "-filter_complex",
       ";".join(parts) + ";[1:a]aresample=48000,aformat=channel_layouts=stereo[key];"
       "[m][key]sidechaincompress=threshold=0.05:ratio=2.5:attack=80:release=600,apad[out]",   # apad: exact length
       "-map", "[out]", "-t", str(T), "-c:a", "pcm_s24le", str(bed))
    if W:
        print(f"música en {len(W)} tramos: " + " · ".join(f"{a:.0f}-{b:.0f}s" for a, b, _ in W))
    print(f"música: {MUSIC} ({gain:+.1f} dB → {MUSIC_LUFS} LUFS, ducking bajo la voz)")

# ---- 3 + 5. Graphics, SFX, music, captions ----
inputs = ["-i", str(WORK / "aroll.mp4"), "-i", str(WORK / "narr.wav")]
fc, last, idx = [], "[0:v]", 2
sfx_in = []
for gph in sorted(PLAN["graphics"], key=lambda x: x["overlay"]):   # full screen first (below), overlays on top
    path = GFX / (gph["id"] + (".mov" if gph["overlay"] else ".mp4"))
    inputs += ["-i", str(path)]
    s, e = gph["start"], gph["start"] + gph["dur"]
    fc.append(f"[{idx}:v]setpts=PTS-STARTPTS+{s}/TB[g{idx}]")
    fc.append(f"{last}[g{idx}]overlay=0:0:eof_action=pass:enable='between(t,{s:.3f},{e:.3f})'[v{idx}]")
    last = f"[v{idx}]"; idx += 1
    if gph.get("sfx"):
        sfx_in.append((gph["sfx"], s))
for kind, s in sfx_in:
    inputs += ["-i", str(Path("sfx") / f"{kind}.wav")]
    ms = int(s * 1000)
    fc.append(f"[{idx}:a]adelay={ms}|{ms}[s{idx}]"); idx += 1
fonts = Path("fonts").resolve()
scale = ",scale=1280:720" if PREVIEW else ""
fc.append(f"{last}subtitles={WORK / 'captions.ass'}:fontsdir={fonts}{scale},format=yuv420p[vout]")
mix = "[1:a]" + "".join(f"[s{i}]" for i in range(idx - len(sfx_in), idx))
if bed.exists():
    inputs += ["-i", str(bed)]
    mix += f"[{idx}:a]"; idx += 1
fc.append(f"{mix}amix=inputs={mix.count('[')}:normalize=0:duration=first[aout]")
(WORK / "filter.txt").write_text(";\n".join(fc))
SLUG = Path.cwd().resolve().parent.name
name = f"{SLUG}-preview.mp4" if PREVIEW else f"{SLUG}-final.mp4"
enc = ["-c:v", "libx264", "-preset", "veryfast" if PREVIEW else "medium", "-crf", "23" if PREVIEW else "18"]
ff(*inputs, "-filter_complex_script", str(WORK / "filter.txt"), "-map", "[vout]", "-map", "[aout]", *enc,
   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(PLAN["total"]), str(OUT / name))
print("listo:", OUT / name)
