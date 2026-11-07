"""Render the full-screen video graphics listed in work/plan.json that are not HTML pages:

  pantalla -> work/gfx/<id>.mp4  screen recording in a rounded card (~1720 px wide, soft shadow) on the brand
              background, sped up to fit its slot, with eased zooms into source regions. The zooms are sub-pixel
              crops done in Pillow (no zoompan: it rounds to whole pixels and jitters on video).
  antes    -> work/gfx/<id>.mp4  before/after base: raw take span in the left window, the same span after cutting
              (work/take_N.mp4) in the right window. antes-despues.html goes on top as a normal overlay.

Usage (from edit/): python pantalla.py [id-prefix]      env TAKES_DIR = raw takes N.mp4 (default ./takes or ~/Downloads)
"""
import json, math, os, subprocess, sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import marca   # brand colours from motion/src/marca.css

FPS, W, H = 30, 1920, 1080
NAVY = marca.rgb("bg")                  # background (marca.css --bg)
CARD_W, CARD_MAX_H, RADIUS = 1720, 980, 18
ZOOM_T = 0.9                            # seconds per zoom move
LEFT, RIGHT = (60, 250, 880, 495), (980, 250, 880, 495)   # holes in antes-despues.html (x, y, w, h)
TAKES = Path(os.environ.get("TAKES_DIR") or ("takes" if Path("takes").is_dir() else Path.home() / "Downloads"))
WORK, GFX = Path("work"), Path("work/gfx")


def background():
    """Brand background with a faint accent glow top-left and a fainter light one bottom-right (dithered: no banding)."""
    bg = Image.new("RGB", (W, H), NAVY)
    for colour, box, strength in ((marca.rgb("deep"), (-500, -650, 1500, 900), 0.16),
                                  (marca.rgb("sky"), (900, 500, 2500, 1700), 0.06)):
        glow = Image.radial_gradient("L").resize((box[2] - box[0], box[3] - box[1]), Image.BICUBIC)
        glow = glow.point(lambda v, k=strength: int(max(0, 255 - v * 2) * k))
        bg.paste(Image.new("RGB", glow.size, colour), box[:2], glow)
    return ImageChops.add(bg, Image.effect_noise((W, H), 1.2).convert("RGB"), offset=-128)   # ±1 level of dither


def rounded(size, r, ss=4):
    m = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] * ss - 1, size[1] * ss - 1], r * ss, fill=255)
    return m.resize(size, Image.LANCZOS)


def card_frame(sw, sh):
    """Background with shadow and hairline border for a card that fits a sw x sh recording; returns bg, mask, box."""
    cw = CARD_W
    ch = round(cw * sh / sw)
    if ch > CARD_MAX_H:
        ch, cw = CARD_MAX_H, round(CARD_MAX_H * sw / sh)
    x0, y0 = (W - cw) // 2, (H - ch) // 2
    bg = background()
    shadow = Image.new("L", (W, H), 0)
    shadow.paste(rounded((cw, ch), RADIUS), (x0, y0 + 22))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.7))
    bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, shadow)
    bg.paste(Image.new("RGB", (cw + 2, ch + 2), marca.rgb("line")), (x0 - 1, y0 - 1), rounded((cw + 2, ch + 2), RADIUS + 1))
    return bg, rounded((cw, ch), RADIUS), (x0, y0, cw, ch)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return tuple(int(x) for x in r.stdout.strip().split(",")[:2])


def fit_view(r, sw, sh):
    """Source region (x, y, w, h) -> view with the source aspect, centred on the region, inside the frame."""
    x, y, w, h = r
    cx, cy = x + w / 2, y + h / 2
    a = sw / sh
    w, h = (h * a, h) if w / h < a else (w, w / a)
    if w > sw:
        w, h = sw, sh
    return (min(max(cx - w / 2, 0), sw - w), min(max(cy - h / 2, 0), sh - h), w, h)


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def lerp_view(a, b, u):
    """Zoom about the fixed point of the two views: every point travels straight and one way (no swing), the width
    changes geometrically (even feel), and the view stays inside the frame when both ends do (convexity)."""
    (ax, ay, aw, ah), (bx, by, bw, bh) = a, b
    r = bw / aw
    if abs(r - 1) < 0.02:                       # (almost) same size: plain pan (the fixed point is far away)
        return tuple(p + (q - p) * u for p, q in zip(a, b))
    px, py = (bx - ax * r) / (1 - r), (by - ay * r) / (1 - r)
    k = r ** u
    return (px - (px - ax) * k, py - (py - ay) * k, aw * k, ah * k)


def views(n, zooms, sw, sh):
    full = (0, 0, sw, sh)
    kfs = sorted((z[0], fit_view(z[1:5], sw, sh) if len(z) >= 5 and z[1] is not None else full) for z in zooms)
    frm, to, t0, k, out = full, full, -1e9, 0, []
    for i in range(n):
        t = i / FPS
        while k < len(kfs) and kfs[k][0] <= t:
            frm = lerp_view(frm, to, ease((kfs[k][0] - t0) / ZOOM_T))   # start from wherever the camera is
            to, t0 = kfs[k][1], kfs[k][0]
            k += 1
        x, y, w, h = lerp_view(frm, to, ease((t - t0) / ZOOM_T))
        out.append((min(max(x, 0), sw - w), min(max(y, 0), sh - h), w, h))
    return out


def encoder(out):
    return subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "fast",
                             "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)


def pantalla(gph):
    src, a, b = gph["src"], gph["src_in"], gph["src_out"]
    sw, sh = probe(src)
    n = int(round(gph["dur"] * FPS))
    speed = max(1.0, (b - a) / gph["dur"])
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{a}", "-t", f"{b - a}", "-i", src,
                            "-vf", f"setpts=(PTS-STARTPTS)/{speed:.6f},fps={FPS},format=rgb24", "-f", "rawvideo", "-"],
                           stdout=subprocess.PIPE)
    bg, mask, (x0, y0, cw, ch) = card_frame(sw, sh)
    enc, size, last = encoder(GFX / f"{gph['id']}.mp4"), sw * sh * 3, None
    for i, (vx, vy, vw, vh) in enumerate(views(n, gph.get("zooms", []), sw, sh)):
        buf = dec.stdout.read(size)
        if len(buf) == size:
            last = Image.frombytes("RGB", (sw, sh), buf)
        if last is None:
            sys.exit(f"{gph['id']}: no frames decoded from {src}")
        frame = bg.copy()
        frame.paste(last.resize((cw, ch), Image.LANCZOS, box=(vx, vy, vx + vw, vy + vh)), (x0, y0), mask)
        enc.stdin.write(frame.tobytes())
    dec.stdout.close(); dec.wait(); enc.stdin.close(); enc.wait()
    if enc.returncode:
        sys.exit(f"{gph['id']}: encoder failed")
    print(f"ok  {gph['id']}  pantalla x{speed:.2f}  ({n} frames, {len(gph.get('zooms', []))} zooms)", flush=True)


def antes(gph):
    k, d = gph["speed"], gph["dur"]
    raw, cut = TAKES / f"{gph['take']}.mp4", WORK / f"take_{gph['take']}.mp4"
    bgpng = WORK / "pantalla_bg.png"
    background().save(bgpng)

    def win(i, w, h):
        return (f"[{i}:v]setpts=(PTS-STARTPTS)/{k:.6f},fps={FPS},scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"format=yuv444p,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"   # 4:4:4: 495 px is odd
                f"tpad=start_mode=clone:start_duration={gph.get('lead', 0)}")   # hold frame 1 until the timers start
    fc = (f"{win(1, LEFT[2], LEFT[3])}[l];{win(2, RIGHT[2], RIGHT[3])}[r];"
          f"[0:v][l]overlay={LEFT[0]}:{LEFT[1]}:format=yuv444[a];[a][r]overlay={RIGHT[0]}:{RIGHT[1]}:format=yuv444,"
          "format=yuv420p[v]")
    run = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(bgpng),
                          "-ss", f"{gph['raw_in']}", "-t", f"{gph['raw_out'] - gph['raw_in']}", "-i", str(raw),
                          "-ss", f"{gph['cut_in']}", "-t", f"{gph['cut_out'] - gph['cut_in']}", "-i", str(cut),
                          "-filter_complex", fc, "-map", "[v]", "-an", "-frames:v", str(int(round(d * FPS))), "-r", str(FPS),
                          "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(GFX / f"{gph['id']}.mp4")])
    bgpng.unlink()
    if run.returncode:
        sys.exit(f"{gph['id']}: ffmpeg failed")
    print(f"ok  {gph['id']}  antes/después x{k:.2f}  (bruto {gph['raw_out'] - gph['raw_in']:.1f}s · "
          f"cortado {gph['cut_out'] - gph['cut_in']:.1f}s)", flush=True)


def _solve(A, b):
    n = len(b); M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c])); M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def _coeffs(dst, src):
    """Pillow PERSPECTIVE coefficients mapping output points dst[i] to input points src[i]."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return _solve(A, b)


def persp(gph):
    """Screen recording as a 3D shot (like the reference video): the crop `persp.crop` of the recording, tilted in
    perspective on the brand background with a slow push-in, sharp in a diagonal band and blurred outside it."""
    src, a, b = gph["src"], gph["src_in"], gph["src_out"]
    cx, cy, cw, ch = gph["persp"]["crop"]
    n = int(round(gph["dur"] * FPS))
    speed = max(1.0, (b - a) / gph["dur"])
    pw = 1600; ph = round(pw * ch / cw) // 2 * 2
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{a}", "-t", f"{b - a}", "-i", src, "-vf",
                            f"crop={cw}:{ch}:{cx}:{cy},scale={pw}:{ph},setpts=(PTS-STARTPTS)/{speed:.6f},fps={FPS},format=rgb24",
                            "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    bg = background()
    # band of focus: sharp across the middle diagonal, soft towards the corners
    band = Image.linear_gradient("L").rotate(-24, expand=True).resize((W * 2, H * 2)).crop((W // 2, H // 2 - 150, W // 2 + W, H // 2 - 150 + H))
    band = band.point(lambda v: int(max(0, 255 - abs(v - 128) * 4.2)))
    band = band.filter(ImageFilter.GaussianBlur(40))
    enc, size, last = encoder(GFX / f"{gph['id']}.mp4"), pw * ph * 3, None
    srcq = [(0, 0), (pw, 0), (pw, ph), (0, ph)]
    for i in range(n):
        buf = dec.stdout.read(size)
        if len(buf) == size:
            last = Image.frombytes("RGB", (pw, ph), buf)
        if last is None:
            sys.exit(f"{gph['id']}: no frames decoded from {src}")
        u = i / max(1, n - 1); z = 1.0 + 0.10 * u; dx = -70 * u     # slow push-in and drift
        quad = [(150, 40), (2050, -170), (2260, 1290), (-170, 1090)]
        cxq, cyq = W / 2, H / 2
        quad = [((x - cxq) * z + cxq + dx, (y - cyq) * z + cyq) for x, y in quad]
        rgba = last.convert("RGBA")
        warped = rgba.transform((W, H), Image.PERSPECTIVE, _coeffs(quad, srcq), Image.BICUBIC)
        frame = bg.copy().convert("RGBA")
        sharp = Image.alpha_composite(frame, warped)
        soft = sharp.filter(ImageFilter.GaussianBlur(7))
        out = Image.composite(sharp, soft, band).convert("RGB")
        enc.stdin.write(out.tobytes())
    dec.stdout.close(); dec.wait(); enc.stdin.close(); enc.wait()
    if enc.returncode:
        sys.exit(f"{gph['id']}: encoder failed")
    print(f"ok  {gph['id']}  pantalla 3D x{speed:.2f}  ({n} frames)", flush=True)


BIG = (320, 128, 1280, 720)   # the one window of antes-despues2.html (x, y, w, h)


def antes2(gph):
    """Sequential before/after base: raw take (desaturated) from raw_in until the switch, cross-fade, cut take."""
    d, lead, sw, xf = gph["dur"], gph["lead"], gph["switch"], gph["xf"]
    p1 = max(0.5, sw - lead)                 # raw seconds shown (real speed)
    p2 = max(0.5, d - sw + 0.1)              # cut seconds shown
    raw, cut = TAKES / f"{gph['take']}.mp4", WORK / f"take_{gph['take']}.mp4"
    bgpng = WORK / "pantalla_bg.png"
    background().save(bgpng)
    x, y, w, h = BIG
    sc = f"fps={FPS},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    fc = (f"[1:v]setpts=PTS-STARTPTS,{sc},hue=s=0.3,eq=brightness=-0.03,format=yuv444p,"
          f"tpad=start_mode=clone:start_duration={lead}[r];"
          f"[2:v]setpts=PTS-STARTPTS,{sc},format=yuv444p,tpad=stop_mode=clone:stop_duration=2[c];"
          f"[r][c]xfade=transition=fade:duration={xf}:offset={lead + p1 - xf / 2:.3f}[w];"
          f"[0:v][w]overlay={x}:{y}:format=yuv444,format=yuv420p[v]")
    run = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(bgpng),
                          "-ss", f"{gph['raw_in']}", "-t", f"{p1 + xf}", "-i", str(raw),
                          "-ss", f"{gph['cut_in']}", "-t", f"{p2}", "-i", str(cut),
                          "-filter_complex", fc, "-map", "[v]", "-an", "-frames:v", str(int(round(d * FPS))), "-r", str(FPS),
                          "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(GFX / f"{gph['id']}.mp4")])
    bgpng.unlink()
    if run.returncode:
        sys.exit(f"{gph['id']}: ffmpeg failed")
    print(f"ok  {gph['id']}  antes/después secuencial (bruto {p1:.1f}s → cortado {p2:.1f}s)", flush=True)


if __name__ == "__main__":
    GFX.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    todo = [x for x in json.loads((WORK / "plan.json").read_text())["graphics"]
            if x.get("kind") in ("pantalla", "antes", "antes2") and x["id"].startswith(only)]
    for x in todo:
        ({"pantalla": pantalla, "antes": antes, "antes2": antes2}[x["kind"]] if not x.get("persp") else persp)(x)
    if not todo:
        print("sin clips de pantalla ni antes/después")
