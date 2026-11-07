"""Clean room echo from every cut take with ElevenLabs Voice Isolator: work/take_N.wav is replaced in place by the
cleaned voice (same length to the sample, so lip sync holds) and the original is kept in work/audio-original/.

Runs right after aroll.py, so Whisper, the preview and the CapCut project all use the clean voice. Already-cleaned
takes are skipped, and results are cached by the hash of the original audio (re-running aroll with the same cuts
costs nothing).
Usage: python isolate.py [N ...]          env: ISOLATE=0 (skip) · ELEVENLABS_API_KEY · ELEVEN_ENV_FILE (.env with the key)
Without ElevenLabs credits (free route, e.g. Adobe Podcast Enhance):
  python isolate.py --exportar           → work/para-limpiar.wav (all takes in a row, 1 s apart) for you to upload
  python isolate.py --importar <file>    → splits the cleaned file back into the takes (checks sync per take), caches it
The key is read from the environment or from a .env file and is never printed.
"""
import hashlib, json, math, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORK = Path("work"); ORIG = WORK / "audio-original"; CACHE = WORK / "isolated"; INDEX = CACHE / "index.json"
URL = "https://api.elevenlabs.io/v1/audio-isolation"


def api_key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"].strip()
    cands = [os.environ.get("ELEVEN_ENV_FILE", "")]
    cands += [str(d / ".env") for d in [Path.cwd(), *Path.cwd().parents]]
    for c in cands:
        if c and Path(c).is_file():
            for line in Path(c).read_text().splitlines():
                if line.startswith("ELEVENLABS_API_KEY=") and line.split("=", 1)[1].strip():
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def sha(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def samples(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration_ts",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


def clean(take, key, index):
    wav = WORK / f"take_{take}.wav"
    cur = sha(wav)
    if index.get(str(take), {}).get("clean") == cur:
        return f"toma {take}: ya limpia"
    ORIG.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wav, ORIG / wav.name)
    cached = CACHE / f"{cur}.wav"
    if not cached.exists():
        mp3 = CACHE / f"{cur}.mp3"
        # the key goes to curl on stdin (-K -), so it never shows in the process list or the terminal
        r = subprocess.run(["curl", "-sS", "-K", "-", "-o", str(mp3), "-w", "%{http_code}", "-X", "POST", URL,
                            "-F", f"audio=@{wav}"], input=f'header = "xi-api-key: {key}"\n',
                           capture_output=True, text=True)
        code = r.stdout.strip()
        if code != "200":
            detail = mp3.read_text(errors="ignore")[:300] if mp3.exists() else r.stderr[:300]
            mp3.unlink(missing_ok=True)
            raise RuntimeError(f"toma {take}: ElevenLabs respondió {code or 'sin conexión'}: {detail}")
        n = samples(wav)   # same length as the original, to the sample
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3), "-af",
                        f"aresample=48000,apad,atrim=end_sample={n}", "-ac", "1", "-c:a", "pcm_s24le", str(cached)],
                       check=True)
        mp3.unlink()
    shutil.copy2(cached, wav)
    index[str(take)] = {"orig": cur, "clean": sha(wav)}
    return f"toma {take}: eco limpio"


GAP = 48000   # 1 s of silence between takes in the export


def pcm(path, rate=8000):
    """Mono 16-bit samples of any audio file (ffmpeg), for envelopes."""
    import array
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
                        "-f", "s16le", "-"], capture_output=True, check=True)
    return array.array("h", r.stdout)


def envelope(a, hop=80):
    return [math.log1p(math.sqrt(sum(x * x for x in a[i:i + hop]) / hop)) for i in range(0, len(a) - hop, hop)]


def lag_ms(ref, test, span=30):
    """Offset of test against ref in 10 ms steps (positive: test is late)."""
    n = min(len(ref), len(test)); mr = sum(ref[:n]) / n; mt = sum(test[:n]) / n
    r = [x - mr for x in ref[:n]]; t = [x - mt for x in test[:n]]
    best = max(range(-span, span + 1), key=lambda l: sum(r[i] * t[i + l] for i in range(max(0, -l), min(n, n - l))))
    return best * 10


def export():
    takes = sorted(int(p.stem.split("_")[1]) for p in WORK.glob("take_*.wav"))
    index = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    srcs = []
    for t in takes:   # always the original voice, even if a take was already cleaned
        wav = WORK / f"take_{t}.wav"
        if index.get(str(t), {}).get("clean") == sha(wav) and (ORIG / wav.name).exists():
            wav = ORIG / wav.name
        srcs.append((t, wav))
    layout, pos, ins, fc = [], 0, [], []
    for k, (t, wav) in enumerate(srcs):
        n = samples(wav); layout.append({"toma": t, "inicio": pos, "muestras": n, "sha": sha(wav)}); pos += n + GAP
        ins += ["-i", str(wav)]; fc.append(f"[{k}]aresample=48000,apad=pad_len={GAP}[s{k}]")
    fc.append("".join(f"[s{k}]" for k in range(len(srcs))) + f"concat=n={len(srcs)}:v=0:a=1[out]")
    out = WORK / "para-limpiar.wav"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc),
                    "-map", "[out]", "-ac", "1", "-c:a", "pcm_s16le", str(out)], check=True)
    (WORK / "para-limpiar.json").write_text(json.dumps(layout, indent=1))
    print(f"{out} · {len(srcs)} tomas · {pos / 48000 / 60:.1f} min")


def import_clean(path):
    layout = json.loads((WORK / "para-limpiar.json").read_text())
    CACHE.mkdir(parents=True, exist_ok=True); ORIG.mkdir(parents=True, exist_ok=True)
    full = WORK / "limpio-48k.wav"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "48000",
                    "-c:a", "pcm_s24le", str(full)], check=True)
    index = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    for e in layout:
        t = e["toma"]; wav = WORK / f"take_{t}.wav"
        raw = ORIG / wav.name if (ORIG / wav.name).exists() and sha(ORIG / wav.name) == e["sha"] else wav
        if sha(raw) != e["sha"]:
            sys.exit(f"La toma {t} ha cambiado desde la exportación: vuelve a exportar (python isolate.py --exportar)")
        start = e["inicio"]
        for attempt in range(2):   # cut, measure the sync against the original, and re-cut once if it is off
            dst = CACHE / f"{e['sha']}.wav"
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(full), "-af",
                            f"atrim=start_sample={max(0, start)}:end_sample={start + e['muestras']},asetpts=N/SR/TB,"
                            f"apad,atrim=end_sample={e['muestras']}", "-c:a", "pcm_s24le", str(dst)], check=True)
            off = lag_ms(envelope(pcm(raw)), envelope(pcm(dst)))
            if off == 0:
                break
            start += int(off * 48)
        if off != 0:
            print(f"⚠ toma {t}: desfase de {off} ms tras recolocarla, revísala")
        if sha(wav) == e["sha"]:
            shutil.copy2(wav, ORIG / wav.name)
        shutil.copy2(dst, wav)
        index[str(t)] = {"orig": e["sha"], "clean": sha(wav)}
        print(f"toma {t}: limpia (desfase {off} ms)")
    INDEX.write_text(json.dumps(index, indent=1)); full.unlink()
    print(f"{len(layout)} tomas con la voz limpia importada; sigue con ./run_all.sh 3")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--exportar"]:
        export(); sys.exit(0)
    if sys.argv[1:2] == ["--importar"]:
        import_clean(sys.argv[2]); sys.exit(0)
    if os.environ.get("ISOLATE", "1") == "0":
        print("ISOLATE=0: audio sin limpiar"); sys.exit(0)
    key = api_key()
    if not key:
        print("sin clave de ElevenLabs (ELEVENLABS_API_KEY): audio sin limpiar"); sys.exit(0)
    takes = [int(t) for t in sys.argv[1:]] or sorted(int(p.stem.split("_")[1]) for p in WORK.glob("take_*.wav"))
    CACHE.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    errors = []
    with ThreadPoolExecutor(4) as ex:
        futs = {t: ex.submit(clean, t, key, index) for t in takes}
        for t, f in futs.items():
            try:
                print(f.result(), flush=True)
            except Exception as e:   # keep going with the other takes, fail at the end
                errors.append(str(e)); print("✗", e, flush=True)
    INDEX.write_text(json.dumps(index, indent=1))
    if errors:
        sys.exit("Fallaron %d tomas. Repite ./run_all.sh 2, o sigue sin limpiar con ISOLATE=0 ./run_all.sh 2" % len(errors))
    print(f"eco limpio en {len(takes)} tomas (ElevenLabs); originales en work/audio-original/")
