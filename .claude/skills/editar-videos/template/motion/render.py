"""Render the motion graphics (HTML pages in src/) to video files.

Each graphic is an HTML page in src/ driven by CSS animations. We open it in headless Chromium,
freeze the animations at each frame time, screenshot, and encode with ffmpeg:
  - overlay clips  -> <id>.mov (PNG codec with alpha, light on disk)
  - full-screen    -> <id>.mp4 (H.264 on the brand background)

Usage:  .venv/bin/python render.py jobs.json OUT_DIR [id-prefix]
jobs.json = [{"id": "...", "page": "pila.html", "query": "active=0&c=1.2,3.4", "dur": 7.5, "overlay": true}, ...]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent / "src"
FPS = 30


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def render(page, out, job):
    overlay = job["overlay"]
    url = (SRC / job["page"]).as_uri() + "?" + job.get("query", "") + ("" if overlay else "&bg=1")
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(250)
    frames = Path(tempfile.mkdtemp(prefix=job["id"] + "-"))
    try:
        total = int(round(job["dur"] * FPS))
        for i in range(total):
            page.evaluate(f"window.__seek({i * 1000 / FPS})")
            page.screenshot(path=str(frames / f"f{i:05d}.png"), omit_background=overlay)
        pattern = str(frames / "f%05d.png")
        if overlay:
            ffmpeg("-framerate", str(FPS), "-i", pattern, "-c:v", "png", "-pix_fmt", "rgba", str(out / f"{job['id']}.mov"))
        else:
            ffmpeg("-framerate", str(FPS), "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                   "-preset", "fast", str(out / f"{job['id']}.mp4"))
        print(f"ok  {job['id']}  ({total} frames)", flush=True)
    finally:
        shutil.rmtree(frames, ignore_errors=True)


def main():
    jobs = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3] if len(sys.argv) > 3 else ""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        for job in jobs:
            if job["id"].startswith(only):
                render(page, out, job)
        browser.close()


if __name__ == "__main__":
    main()
