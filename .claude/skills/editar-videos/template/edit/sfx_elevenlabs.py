"""Generate the edit's sound effects with ElevenLabs Sound Effects into sfx-elevenlabs/, with the same names and peak
level as the synthesized ones in sfx/ (so swapping the folder changes the sound, not the mix).
Usage: python sfx_elevenlabs.py [name ...]      (~11 credits per second of sound; existing files are skipped)
Then: python sfx_elevenlabs.py --comparar  → sfx-elevenlabs/comparacion.m4a (spoken label, ours, ElevenLabs).
The key comes from ELEVENLABS_API_KEY or a .env (see isolate.py) and is never printed.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path
from isolate import api_key

OUT = Path("sfx-elevenlabs"); OURS = Path("sfx")
URL = "https://api.elevenlabs.io/v1/sound-generation"
# name: (prompt, seconds generated, max length kept, peak dBFS if there is no synthesized one to match)
SFX = {
    "golpe-grave": ("Deep cinematic sub-bass boom hit for a title card reveal, punchy, clean, short low rumble decay, no music", 1.5, 1.2, -16),
    "whoosh-suave": ("Soft airy whoosh transition, smooth quick swipe, modern minimal tech video edit, clean", 0.9, 0.9, -20),
    "whoosh": ("Fast crisp whoosh swipe transition, modern tech video edit, clean, short", 0.8, 0.8, -18),
    "pop-suave": ("Soft subtle bubble pop for a user interface card appearing, gentle, clean, minimal, very short", 0.5, 0.3, -26),
    "pop": ("Short crisp pop for a card appearing on screen, clean modern user interface sound, very short", 0.5, 0.25, -22),
    "clic": ("Single soft mouse click, clean, close, very short", 0.5, 0.15, -24),
    "subida": ("Short clean riser swell building tension, cinematic, smooth, ends abruptly at the peak", 1.6, 1.6, -22),
    "teclado": ("Quick typing of a short sentence on a quiet laptop keyboard, close, clean, then pressing enter", 2.5, 2.5, -24),
    "check": ("Soft positive success chime, two quick notes, modern app notification, clean, short", 1.0, 1.0, -22),
}


def peak(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "astats=metadata=0:measure_overall=Peak_level",
                        "-f", "null", "-"], capture_output=True, text=True)
    return float(re.findall(r"Peak level dB: (-?[\d.]+)", r.stderr)[-1])


def generate(name, key):
    prompt, secs, keep, default_peak = SFX[name]
    dst = OUT / f"{name}.wav"
    if dst.exists():
        return f"{name}: ya existe"
    with tempfile.TemporaryDirectory() as td:
        mp3 = Path(td) / "a.mp3"
        r = subprocess.run(["curl", "-sS", "-K", "-", "-o", str(mp3), "-w", "%{http_code}", "-X", "POST", URL,
                            "-H", "Content-Type: application/json",
                            "-d", json.dumps({"text": prompt, "duration_seconds": secs, "prompt_influence": 0.6})],
                           input=f'header = "xi-api-key: {key}"\n', capture_output=True, text=True)
        if r.stdout.strip() != "200":
            raise RuntimeError(f"{name}: ElevenLabs respondió {r.stdout.strip()}: {mp3.read_text(errors='ignore')[:200]}")
        target = peak(OURS / f"{name}.wav") if (OURS / f"{name}.wav").exists() else default_peak
        raw = Path(td) / "b.wav"
        # trim the silence before the sound, keep `keep` seconds with a short fade-out, mono 48 kHz like sfx/
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3), "-af",
                        f"silenceremove=start_periods=1:start_threshold=-50dB,atrim=0:{keep},"
                        f"afade=t=out:st={max(0, keep - min(0.12, keep / 3)):.3f}:d={min(0.12, keep / 3):.3f}",
                        "-ac", "1", "-ar", "48000", str(raw)], check=True)
        gain = target - peak(raw)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-af", f"volume={gain:.2f}dB",
                        "-c:a", "pcm_s16le", str(dst)], check=True)
    return f"{name}: ok ({target:.0f} dB de pico)"


def compare():
    """comparacion.m4a: for every effect, a spoken label, ours (if any), a short gap, ElevenLabs."""
    parts = []
    with tempfile.TemporaryDirectory() as td:
        for i, name in enumerate(SFX):
            if not (OUT / f"{name}.wav").exists():
                continue
            label = Path(td) / f"l{i}.aiff"
            ours = "nuestro, y el nuevo" if (OURS / f"{name}.wav").exists() else "nuevo"
            subprocess.run(["say", "-v", "Mónica", "-o", str(label), f"{name.replace('-', ' ')}: {ours}"], check=True)
            parts += [label] + ([OURS / f"{name}.wav"] if (OURS / f"{name}.wav").exists() else []) + [OUT / f"{name}.wav"]
        ins, fc = [], []
        for k, p in enumerate(parts):
            ins += ["-i", str(p)]
            fc.append(f"[{k}]aresample=48000,aformat=channel_layouts=mono,apad=pad_dur=0.7[s{k}]")
        fc.append("".join(f"[s{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc),
                        "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(OUT / "comparacion.m4a")], check=True)
    print(OUT / "comparacion.m4a")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    if sys.argv[1:] == ["--comparar"]:
        compare(); sys.exit(0)
    key = api_key()
    if not key:
        sys.exit("Falta ELEVENLABS_API_KEY")
    for n in (sys.argv[1:] or SFX):
        print(generate(n, key), flush=True)
