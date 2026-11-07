"""Build the video timeline: maps words to final time, schedules graphics, writes captions.

Outputs (in work/):
  jobs.json      -> graphics to render with motion/render.py (cues synced to the voice)
  plan.json      -> layout used by compose.py, pantalla.py and to_capcut.py (A-roll pieces, graphics with start/duration;
                    p() screen clips and ad() before/after bases are full-screen graphics rendered by pantalla.py)
  captions.ass   -> burned-in subtitles (2-3 words per line)
"""
import json, re, unicodedata
from pathlib import Path

import marca

TX = Path("work/tx")
WORK = Path("work"); WORK.mkdir(exist_ok=True)
FPS = 30


def fr(t):
    """Snap a time to the 30 fps frame grid (cuts, graphics and the CapCut project all share it)."""
    return round(round(t * FPS) / FPS, 4)


SEG = {int(k): [[fr(a), fr(b)] for a, b in v if fr(b) > fr(a)]
       for k, v in json.loads(Path("segments.json").read_text()).items()}
N = max(SEG)   # number of takes
TITLE_DUR, END_DUR = 2.8, 12.0

# Transcription fixes for the captions: (regex, replacement), case-insensitive. Add what whisper mis-hears in your
# video (your name, your brand, product names): read work/txc with words.py and add a line per mistake.
FIXES = [(r"\bchat ?gpt\b", "ChatGPT"), (r"\bmeter[ií]a\b", "meter IA"), (r"\bva a matizar\b", "automatizar"),
         (r"\bcloud\b|\bclaud\b|\bclod\b", "Claude"), (r"\bcap ?cut\b|\bcapcat\b|\bcap kat\b", "CapCut")]


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def words(take):
    data = json.loads((TX / f"{take}.json").read_text())
    w = [[w["offsets"]["from"] / 1000, w["offsets"]["to"] / 1000, w["text"].strip()]
         for w in data["transcription"] if w["text"].strip()]
    # whisper pins the first words to 0 s when the take starts with silence: spread them from the real
    # speech onset (silencedetect) up to the first word that is timed after it
    a0 = SEG[take][0][0] + 0.12
    j = next((i for i, x in enumerate(w) if x[0] >= a0 + 0.05), len(w))
    if j:
        tj = w[j][0] if j < len(w) else a0 + 0.3 * j
        for i in range(j):
            w[i][0] = a0 + (tj - a0) * i / j
            w[i][1] = a0 + (tj - a0) * (i + 1) / j
    return [tuple(x) for x in w]


def tmap(take, t):
    """Take time -> time inside the cut take (pauses removed)."""
    acc = 0.0
    for a, b in SEG[take]:
        if t < a:
            return acc
        if t <= b:
            return acc + (t - a)
        acc += b - a
    return acc


def cut_len(take):
    return sum(b - a for a, b in SEG[take])


# ---- global layout: take 1, title card, takes 2..N, end screen ----
pieces, t = [], 0.0
for item in [1, "titulo"] + list(range(2, N + 1)) + ["cierre"]:
    d = TITLE_DUR if item == "titulo" else END_DUR if item == "cierre" else cut_len(item)
    pieces.append({"item": item, "start": round(t, 4), "dur": round(d, 4)})
    t += d
TOTAL = t
START = {p["item"]: p["start"] for p in pieces}
CUTTX = Path("work/txc")


def cut_words(take):
    f = CUTTX / f"{take}.json"
    if f.exists():
        data = json.loads(f.read_text())
        return [(w["offsets"]["from"] / 1000, w["offsets"]["to"] / 1000, w["text"].strip())
                for w in data["transcription"] if w["text"].strip()]
    return [(tmap(take, a), tmap(take, b), t) for a, b, t in words(take)]


W = {k: cut_words(k) for k in range(1, N + 1)}


def at(take, word, nth=1, after=0.0, end=False, prefix=False):
    """Global time of the nth occurrence of `word` (normalized) in a take, searching after take-time `after`."""
    n = 0
    target = norm(word)
    for t0, t1, w in W[take]:
        if t0 >= after and (norm(w).startswith(target) if prefix else norm(w) == target):
            n += 1
            if n == nth:
                return round(START[take] + (t1 if end else t0), 3)
    raise KeyError(f"'{word}' #{nth} not found in take {take}")


def take_start(k): return START[k]
def take_end(k): return round(START[k] + cut_len(k), 3)


def aw(take, *words, nth=1, frac=0.5, end=False, after=0.0):
    """Tolerant at(): tries several words in order (improvised lines; whisper writes «3» for «tres» and may hear
    «Cloud» for «Claude»). If none is found, falls back to `frac` of the take and prints a ⚠ to review."""
    for w in words:
        try:
            return at(take, w, nth, after=after, end=end)
        except KeyError:
            continue
    t = round(take_start(take) + (take_end(take) - take_start(take)) * frac, 3)
    print(f"  ⚠ toma {take}: no encuentro {words} → {t:.2f}s (aprox., revisar)")
    return t


GR = []   # graphics: id, page, query, start, dur, overlay, cues (global) -> made relative


def g(gid, page, start, end, overlay, query="", cues=(), sfx=None, **extra):
    start, end = fr(start), fr(end)
    dur = round(end - start, 4)
    rel = ",".join(f"{c - start:.2f}" for c in cues)
    q = query + (("&" if query else "") + f"c={rel}" if cues else "")
    GR.append({"id": gid, "page": page, "query": q, "start": start, "dur": dur, "overlay": overlay, "sfx": sfx, **extra})


def p(gid, file, src_in, src_out, start, end, zooms=(), sfx=None, persp=None):
    """Screen recording («pantalla»), full screen: src_in..src_out of `file` (seconds) sped up to fit start..end.
    zooms = [(t, x, y, w, h), ...]: t = seconds after `start`; x, y, w, h = source pixels to zoom into
    (eased, ~0.9 s); (t, None) zooms back out. Rendered by pantalla.py."""
    g(gid, None, start, end, False, sfx=sfx, kind="pantalla", src=str(Path(file).absolute()), src_in=src_in,
      src_out=src_out, zooms=[[z[0], *(z[1:] if len(z) > 2 else [])] for z in zooms],
      **({"persp": persp} if persp else {}))


def ad(gid, take, raw_in, raw_out, start, end, page="antes-despues.html", sfx=None, lead=0.5):
    """Before/after («antes/después»): full-screen base with take time raw_in..raw_out in the left window (raw) and the
    same span after cutting in the right window (pantalla.py), plus `page` on top as an overlay (<gid>-ov) whose
    transparent holes match the windows. Both windows hold their first frame for `lead` s, then play together at the
    same speed (sped up only if the raw span doesn't fit); the cut side ends first and holds. The page gets
    a/b = raw/cut seconds and x = speed; its two timers start at `lead` (cue 0)."""
    cut_in, cut_out = tmap(take, raw_in), tmap(take, raw_out)
    raw_d, cut_d = raw_out - raw_in, cut_out - cut_in
    speed = max(1.0, raw_d / max(0.1, fr(end) - fr(start) - lead - 0.3))
    g(gid, None, start, end, False, kind="antes", take=take, raw_in=raw_in, raw_out=raw_out, cut_in=round(cut_in, 4),
      cut_out=round(cut_out, 4), speed=round(speed, 4), lead=lead)
    g(gid + "-ov", page, start, end, True, f"a={raw_d:.2f}&b={cut_d:.2f}&x={speed:.4f}", [fr(start) + lead], sfx)


def ad_seq(gid, take, start, switch, end, raw_in=0.0, raw_out=None, page="antes-despues2.html", sfx=None, lead=0.4, xf=0.35):
    """Before/after, sequential and unmistakable: ONE big window plays the raw take (desaturated, «● REC») from
    raw_in until `switch` (absolute time), cross-fades and plays the same take after cutting (work/take_N.mp4) until
    `end`. `page` draws a bar of the whole raw take under it (speech blue, silences red with their length) that
    collapses at the switch: silences out, bar shrinks to the cut length (rendered by pantalla.py, kind antes2)."""
    segs = [[a, b] for a, b in SEG[take]]
    raw_out = raw_out if raw_out is not None else segs[-1][1] + 1.0
    sw, st, en = fr(switch), fr(start), fr(end)
    cut_total = sum(b - a for a, b in segs if a >= raw_in and b <= raw_out)
    g(gid, None, st, en, False, kind="antes2", take=take, raw_in=raw_in, cut_in=round(tmap(take, raw_in), 4),
      lead=lead, switch=round(sw - st, 4), xf=xf)
    sp = ",".join(f"{max(a, raw_in) - raw_in:.2f}-{min(b, raw_out) - raw_in:.2f}" for a, b in segs if b > raw_in and a < raw_out)
    g(gid + "-ov", page, st, en, True, f"a={raw_out - raw_in:.2f}&b={cut_total:.2f}&sp={sp}", [st + lead, sw], sfx)


exec(Path("schedule.py").read_text())   # the per-take graphics schedule (kept separate so it is easy to tweak)

# ---- captions ----
def ass_time(s):
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def fix(text):
    for pat, rep in FIXES:
        text = re.sub(pat, rep, text, flags=re.I)
    return text


lines = []
for k in range(1, N + 1):
    group = []
    for t0, t1, w in W[k]:
        group.append((START[k] + t0, START[k] + t1, w))
        txt = " ".join(x[2] for x in group)
        if len(group) >= 3 or len(txt) > 16 or w[-1] in ".,?!:;…":
            lines.append((group[0][0], group[-1][1], txt)); group = []
    if group:
        lines.append((group[0][0], group[-1][1], " ".join(x[2] for x in group)))
# continuous display: each line stays until the next starts (max +0.6 s)
events = []
for i in range(1, len(lines)):   # keep captions strictly in order, each on screen ≥ 0.3 s (no stacked lines)
    a, b, txt = lines[i]
    if a < lines[i - 1][0] + 0.3:
        lines[i] = (lines[i - 1][0] + 0.3, max(b, lines[i - 1][0] + 0.6), txt)
for i, (a, b, txt) in enumerate(lines):
    nxt = lines[i + 1][0] if i + 1 < len(lines) else b + 0.6
    end = min(nxt, b + 0.6)
    txt = fix(txt).strip(" ,;:")
    events.append(f"Dialogue: 0,{ass_time(a)},{ass_time(max(end, a + 0.3))},Cap,,0,0,0,,{txt}")
header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter,62,&H00FFFFFF,&H00FFFFFF,&H00140B07,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,62,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
header = header.replace("&H00140B07", marca.ass("bg"))   # caption outline in the brand background colour
(WORK / "captions.ass").write_text(header + "\n".join(events) + "\n")

jobs = [{"id": x["id"], "page": x["page"], "query": x["query"], "dur": x["dur"], "overlay": x["overlay"]} for x in GR if x["page"]]
(WORK / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False))
MUS = [[round(max(0.0, a), 3), round(min(TOTAL, b), 3), round(o, 3)] for a, b, o in globals().get("MUSICA", []) if b > a]
(WORK / "plan.json").write_text(json.dumps({"total": round(TOTAL, 4), "pieces": pieces, "graphics": GR, "music": MUS},
                                         indent=1, ensure_ascii=False))
print(f"duración total {TOTAL // 60:.0f}:{TOTAL % 60:04.1f} · {len(GR)} gráficos · {len(events)} subtítulos")
for x in GR:
    print(f"  {x['start']:7.2f}  +{x['dur']:5.2f}  {'OVR' if x['overlay'] else 'FULL'}  {x['id']}  {x['query'] or x.get('kind', '')}")
