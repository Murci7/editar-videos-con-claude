"""Prepare a face for the thumbnail: cut the person out, clean the edge, store the face box.

macOS only (Apple Vision). Runs with the PyObjC venv (see cutout.py):
  ~/.cache/editar-videos-vision/bin/python prep_face.py <image> <key> [thumbnail_dir]
Writes <thumbnail_dir>/caras/cara-<key>.png and the face box into caras/faces.json.
Paste faces.json into FACES in thumb.html, then render with ?f=<key>.
Source can be a video frame (ffmpeg -ss T -i take.mp4 -frames:v 1 raw.png) or an AI portrait.
"""
import json
import subprocess
import sys
from pathlib import Path

import Quartz
import Vision
from Foundation import NSURL

src, key = Path(sys.argv[1]).resolve(), sys.argv[2]
thumb = Path(sys.argv[3] if len(sys.argv) > 3 else ".").resolve()
caras = thumb / "caras"
caras.mkdir(exist_ok=True)
tmp, out = caras / f"tmp-{key}.png", caras / f"cara-{key}.png"

# 1. person segmentation, then erode + blur the alpha so no background rim survives
subprocess.run([sys.executable, str(Path(__file__).with_name("cutout.py")), str(src), str(tmp)], check=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp), "-filter_complex",
                "[0]format=rgba,split[c][a];[a]alphaextract,erosion,erosion,gblur=sigma=1.0[m];[c][m]alphamerge",
                str(out)], check=True)
tmp.unlink()

# 2. face box (Apple Vision), in source pixels, top-left origin
ci = Quartz.CIImage.imageWithContentsOfURL_(NSURL.fileURLWithPath_(str(src)))
W, H = ci.extent().size.width, ci.extent().size.height
req = Vision.VNDetectFaceRectanglesRequest.alloc().initWithCompletionHandler_(None)
Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci, {}).performRequests_error_([req], None)
if not req.results():
    sys.exit("no face found")
bb = req.results()[0].boundingBox()
x, w = bb.origin.x * W, bb.size.width * W
y, h = (1 - bb.origin.y - bb.size.height) * H, bb.size.height * H

faces_path = caras / "faces.json"
faces = json.loads(faces_path.read_text()) if faces_path.exists() else {}
faces[key] = {"cx": round(x + w / 2), "cy": round(y + h / 2), "w": round(w), "h": round(h), "W": int(W)}
faces_path.write_text(json.dumps(faces))
print(out, faces[key])
