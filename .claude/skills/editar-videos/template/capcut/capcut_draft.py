#!/usr/bin/env python3
"""capcut_draft.py - build a CapCut desktop (9.x, macOS) project ("draft") from a JSON timeline spec.

Stdlib + ffprobe only. Never touches existing drafts: it reads one of them once to snapshot
the format (template_snapshot.json), then writes a *new* draft folder and registers it.

  python3 capcut_draft.py snapshot [--template "<draft folder>"]   # (re)capture the format
  python3 capcut_draft.py build  spec.json [--force] [--no-register]
  python3 capcut_draft.py validate "<draft folder>"
  python3 capcut_draft.py remove  "<draft name>"                   # only drafts we generated

Spec (times in seconds; x/y in CapCut units = half-canvas, x right +, y UP +; scale 1.0 =
media fitted to the canvas):
{
  "name": "Prueba Claude",
  "canvas": {"width": 1920, "height": 1080, "fps": 30},
  "main_track":     {"clips": [{"source": "a.mp4", "in": 0, "out": 1.3, "scale": 1.0,
                                "keyframes": {"scale": [[0, 1.0], [6, 1.3]]}}]},
  "overlay_tracks": [{"name": "...", "clips": [{"source": "o.mov", "start": 5, "in": 0, "out": 4,
                                                "x": -0.45, "y": 0.5, "scale": 0.5}]}],
  "audio_tracks":   [{"name": "SFX", "clips": [{"source": "w.wav", "start": 3.4, "volume": 1.0}]}],
  "text_tracks":    [{"clips": [{"text": "Hola", "start": 0.3, "duration": 3, "y": -0.72,
                                 "size": 9, "color": "#FFFFFF", "bold": true}]}]
}
Main-track clips are laid end to end from 0. Images (.png/.jpg) take "duration" instead of in/out.
Any clip takes "volume" (1.0 = as recorded, 0.0 = muted), e.g. muted camera clips under a separate narration track.
Keyframe properties: scale, x, y, rotation, alpha, volume  ->  [[t_rel_to_clip_start, value], ...].
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS_ROOT = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
SNAPSHOT = os.path.join(HERE, "template_snapshot.json")
MANIFEST = os.path.join(HERE, "generated_drafts.json")   # drafts this copy generated (the only ones it replaces)
BACKUPS = os.path.join(HERE, "backups")      # root_meta_info.json copies, before every registry change
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".aif", ".aiff", ".ogg"}
PHOTO_DURATION = 10_800_000_000  # CapCut convention for stills: 3 h of "source"

COMMON_ATTACHMENTS = ["attachment_action_scene.json", "attachment_gen_ai_info.json",
                      "attachment_pc_timeline.json", "attachment_plugin_draft.json",
                      "attachment_script_video.json"]
EMPTY_DIRS = ["Resources/audioAlg", "Resources/videoAlg", "adjust_mask", "matting",
              "qr_upload", "smart_crop", "subdraft"]
KF_PROPS = {"x": ["KFTypePositionX"], "y": ["KFTypePositionY"], "rotation": ["KFTypeRotation"],
            "alpha": ["KFTypeAlpha"], "volume": ["KFTypeVolume"],
            # uniform zoom: written as both axes (identical values) so it holds whether CapCut
            # reads X only (uniform mode) or X and Y independently.
            "scale": ["KFTypeScaleX", "KFTypeScaleY"]}


# ----------------------------------------------------------------------------- helpers
def UID():
    return str(uuid.uuid4()).upper()


def lid():
    return str(uuid.uuid4())


def now_us():
    return int(time.time() * 1_000_000)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def capcut_running():
    r = subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True)
    return r.returncode == 0


def backup(path):
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUPS, f"{os.path.basename(path)}.{stamp}.bak")
    shutil.copy2(path, dst)
    return dst


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", path], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    ext = os.path.splitext(path)[1].lower()
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    kind = "photo" if ext in IMAGE_EXT else ("audio" if (ext in AUDIO_EXT or v is None) else "video")
    if kind == "photo":
        dur = PHOTO_DURATION
    else:
        s = v if (kind == "video" and v and v.get("duration")) else (a or {})
        dur = int(round(float(s.get("duration") or info["format"]["duration"]) * 1_000_000))
    st = os.stat(path)
    return {"path": path, "kind": kind, "duration": dur,
            "width": int(v["width"]) if v else 0, "height": int(v["height"]) if v else 0,
            "has_audio": a is not None, "size": st.st_size, "mtime": int(st.st_mtime),
            "unique_id": hashlib.md5(f"{path}|{st.st_size}|{st.st_mtime}".encode()).hexdigest(),
            "local_id": lid()}


# ----------------------------------------------------------------------------- snapshot
def find_template():
    cands = sorted(os.path.join(DRAFTS_ROOT, d) for d in os.listdir(DRAFTS_ROOT))
    for d in cands:
        p = os.path.join(d, "draft_info.json")
        if os.path.isfile(p):
            j = load(p)
            if any(t["type"] == "video" and t["segments"] for t in j.get("tracks", [])):
                return d
    sys.exit("No existing draft with a video segment to use as template.")


def snapshot(template_dir=None):
    """Read-only capture of an existing draft's structure. Media paths are blanked."""
    d = template_dir or find_template()
    info = load(os.path.join(d, "draft_info.json"))
    meta = load(os.path.join(d, "draft_meta_info.json"))
    root = load(os.path.join(DRAFTS_ROOT, "root_meta_info.json"))
    vtrack = next(t for t in info["tracks"] if t["type"] == "video" and t["segments"])
    seg = vtrack["segments"][0]
    mats = info["materials"]
    by_id = {m["id"]: (k, m) for k, lst in mats.items() for m in lst if isinstance(m, dict) and "id" in m}
    companions = {}
    for ref in seg["extra_material_refs"]:
        k, m = by_id[ref]
        companions[k] = m
    video = copy.deepcopy(next(m for m in mats["videos"] if m["id"] == seg["material_id"]))
    for k in ("path", "material_name", "local_material_id", "unique_id"):
        video[k] = ""
    skel = copy.deepcopy(info)
    skel["tracks"] = []
    skel["materials"] = {k: [] for k in mats}
    skel["duration"] = 0
    skel["id"] = ""
    msk = copy.deepcopy(meta)
    meta_mat = None
    for grp in msk["draft_materials"]:
        if grp["value"] and meta_mat is None:
            meta_mat = copy.deepcopy(grp["value"][0])
        grp["value"] = []
    msk["draft_segment_extra_info"] = []
    msk["draft_materials_copied_info"] = []
    root_entry = copy.deepcopy(next(e for e in root["all_draft_store"]
                                    if e["draft_fold_path"] == meta["draft_fold_path"]))
    vstore = load(os.path.join(d, "draft_virtual_store.json"))
    for grp in vstore["draft_virtual_store"]:
        if grp["type"] == 1:
            grp["value"] = []
    proj = load(os.path.join(d, "Timelines", "project.json"))
    aux = {}
    for name in ["attachment_pc_common.json", "attachment_editing.json", "performance_opt_info.json"]:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            aux[name] = open(p, encoding="utf-8").read()
    for name in COMMON_ATTACHMENTS:
        p = os.path.join(d, "common_attachment", name)
        if os.path.isfile(p):
            aux["common_attachment/" + name] = open(p, encoding="utf-8").read()
    snap = {"captured_from": d, "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
            "draft_info_skeleton": skel, "video_track": {k: v for k, v in vtrack.items() if k != "segments"},
            "video_segment": seg, "video_material": video, "companions": companions,
            "meta_skeleton": msk, "meta_material": meta_mat, "root_entry": root_entry,
            "virtual_store": vstore, "project_json": proj, "aux_files": aux}
    write_text(SNAPSHOT, json.dumps(snap, ensure_ascii=False, indent=1))
    print(f"snapshot written: {SNAPSHOT}\n  from: {d}\n  companions: {list(companions)}")
    return snap


# ----------------------------------------------------------------------------- inferred prototypes
# These shapes do NOT appear in any local draft (no audio/text/animation there). They follow the
# public CapCut/JianYing draft format; every key name was checked against strings in CapCut 9.5's
# libvideoeditor/libVECreator. Treat them as the uncertain part.
def material_animation(mid):  # shape observed in a CapCut draft
    return {"id": mid, "type": "sticker_animation", "animations": [], "multi_language_current": "none"}


def audio_material(mid, m):
    return {"app_id": 0, "category_id": "", "category_name": "local", "check_flag": 1,
            "copyright_limit_type": "none", "duration": m["duration"], "effect_id": "",
            "formula_id": "", "id": mid, "intensifies_path": "", "is_ai_clone_tone": False,
            "is_text_edit_overdub": False, "is_ugc": False, "local_material_id": m["local_id"],
            "music_id": lid(), "name": os.path.basename(m["path"]), "path": m["path"], "query": "",
            "request_id": "", "resource_id": "", "search_id": "", "source_from": "",
            "source_platform": 0, "team_id": "", "text_id": "", "tone_category_id": "",
            "tone_category_name": "", "tone_effect_id": "", "tone_effect_name": "",
            "tone_platform": "", "tone_second_category_id": "", "tone_second_category_name": "",
            "tone_speaker": "", "tone_type": "", "type": "extract_music", "unique_id": m["unique_id"],
            "video_id": "", "wave_points": []}


def hex_rgb(h):
    h = h.lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def text_material(mid, c):
    text = c["text"]
    rgb = hex_rgb(c.get("color", "#FFFFFF"))
    size = float(c.get("size", 8.0))
    style = {"fill": {"alpha": 1.0, "content": {"render_type": "solid",
                                                  "solid": {"alpha": 1.0, "color": rgb}}},
             "range": [0, len(text)], "size": size, "bold": bool(c.get("bold", False)),
             "italic": bool(c.get("italic", False)), "underline": False, "strokes": []}
    content = {"styles": [style], "text": text}
    return {"add_type": 0, "alignment": int(c.get("align", 1)), "background_alpha": 1.0,
            "background_color": "", "background_height": 0.14, "background_horizontal_offset": 0.0,
            "background_round_radius": 0.0, "background_style": 0, "background_vertical_offset": 0.0,
            "background_width": 0.14, "base_content": "", "bold_width": 0.0, "border_alpha": 1.0,
            "border_color": "", "border_width": 0.08, "check_flag": 7,
            "combo_info": {"text_templates": []}, "content": dump(content),
            "fixed_height": -1.0, "fixed_width": -1.0, "font_category_id": "",
            "font_category_name": "", "font_id": "", "font_name": "", "font_path": "",
            "font_resource_id": "", "font_size": size, "font_source_platform": 0, "font_team_id": "",
            "font_title": "none", "font_url": "", "fonts": [], "force_apply_line_max_width": False,
            "global_alpha": 1.0, "group_id": "", "has_shadow": False, "id": mid,
            "initial_scale": 1.0, "inner_padding": -1.0, "is_rich_text": False, "italic_degree": 0,
            "ktv_color": "", "language": "", "layer_weight": 1, "letter_spacing": 0.0,
            "line_feed": 1, "line_max_width": 0.82, "line_spacing": 0.02,
            "multi_language_current": "none", "name": "", "original_size": [],
            "preset_category": "", "preset_category_id": "", "preset_has_set_alignment": False,
            "preset_id": "", "preset_index": 0, "preset_name": "", "recognize_task_id": "",
            "recognize_type": 0, "relevance_segment": [], "shadow_alpha": 0.9, "shadow_angle": -45.0,
            "shadow_color": "", "shadow_distance": 5.0, "shadow_point": {"x": 0.6363961, "y": -0.6363961},
            "shadow_smoothing": 0.45, "shape_clip_x": False, "shape_clip_y": False, "source_from": "",
            "style_name": "", "sub_type": 0, "subtitle_keywords": None,
            "subtitle_template_original_fontsize": 0.0, "text_alpha": 1.0,
            "text_color": "#" + c.get("color", "#FFFFFF").lstrip("#").upper(), "text_curve": None,
            "text_preset_resource_id": "", "text_size": 30, "text_to_audio_ids": [],
            "tts_auto_update": False, "type": "text", "typesetting": 0, "underline": False,
            "underline_offset": 0.22, "underline_width": 0.05, "use_effect_default_color": True,
            "words": {"end_time": [], "start_time": [], "text": []}}


# ----------------------------------------------------------------------------- builder
class Builder:
    def __init__(self, spec, spec_dir, snap):
        self.spec, self.dir, self.snap = spec, spec_dir, snap
        cv = spec.get("canvas", {})
        self.w, self.h = int(cv.get("width", 1920)), int(cv.get("height", 1080))
        self.fps = float(cv.get("fps", 30))
        self.media = {}            # abs path -> probe dict
        self.info = copy.deepcopy(snap["draft_info_skeleton"])
        self.mats = self.info["materials"]
        self.segment_ids = []

    # time: seconds -> microseconds snapped to the frame grid
    def us(self, sec):
        return int(round(round(float(sec) * self.fps) * 1_000_000 / self.fps))

    def stage(self, p):
        """CapCut (Mac) is sandboxed: it can only read ~/Movies on its own (entitlement
        assets.movies.read-write) plus files the user picks by hand. Put every source under
        ~/Movies/CapCut/claude-media/<draft>/ as a hard link (same file, no extra disk);
        fall back to a copy if linking is not possible."""
        movies = os.path.realpath(os.path.expanduser("~/Movies"))
        real = os.path.realpath(p)          # symlinked takes: link the real file (keeps the symlink's name)
        if real.startswith(movies + os.sep):
            return p
        d = os.path.join(movies, "CapCut", "claude-media", self.spec.get("name", "draft"))
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, os.path.basename(p))
        if os.path.exists(dst) and not os.path.samefile(real, dst):
            os.remove(dst)                  # stale link to an older render of the same file name
        if not os.path.exists(dst):
            try:
                os.link(real, dst)
            except OSError:
                shutil.copy2(real, dst)
        return dst

    def src(self, rel):
        p = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(self.dir, rel))
        if not os.path.isfile(p):
            sys.exit(f"missing media: {p}")
        p = self.stage(p)
        if p not in self.media:
            self.media[p] = probe(p)
        return self.media[p]

    def companion(self, kind):
        m = copy.deepcopy(self.snap["companions"][kind])
        m["id"] = UID()
        self.mats[kind].append(m)
        return m["id"]

    def keyframes(self, kfs):
        out = []
        for prop, pts in (kfs or {}).items():
            for ptype in KF_PROPS[prop]:
                out.append({"id": UID(), "material_id": "", "property_type": ptype,
                            "keyframe_list": [{"curveType": "Line", "graphID": "", "id": UID(),
                                               "left_control": {"x": 0.0, "y": 0.0},
                                               "right_control": {"x": 0.0, "y": 0.0},
                                               "string_value": "", "time_offset": self.us(t),
                                               "values": [float(v)]} for t, v in pts]})
        return out

    def segment(self, mat_id, refs, src_start, src_dur, tl_start, tl_dur, c, render_index):
        s = copy.deepcopy(self.snap["video_segment"])
        sid = UID()
        self.segment_ids.append(sid)
        kfs = c.get("keyframes") or {}
        scale = float(kfs["scale"][0][1]) if "scale" in kfs else float(c.get("scale", 1.0))
        x = float(kfs["x"][0][1]) if "x" in kfs else float(c.get("x", 0.0))
        y = float(kfs["y"][0][1]) if "y" in kfs else float(c.get("y", 0.0))
        s.update({"id": sid, "material_id": mat_id, "extra_material_refs": refs,
                  "source_timerange": {"start": src_start, "duration": src_dur},
                  "target_timerange": {"start": tl_start, "duration": tl_dur},
                  "render_timerange": {"start": 0, "duration": 0},
                  "speed": 1.0, "volume": float(c.get("volume", 1.0)), "last_nonzero_volume": 1.0,
                  "visible": True, "group_id": "", "raw_segment_id": "", "template_id": "",
                  "render_index": render_index, "track_render_index": render_index,
                  "keyframe_refs": [], "common_keyframes": self.keyframes(kfs), "caption_info": None})
        s["clip"] = {"scale": {"x": scale, "y": scale}, "rotation": float(c.get("rotation", 0.0)),
                     "transform": {"x": x, "y": y},
                     "flip": {"vertical": False, "horizontal": False}, "alpha": float(c.get("alpha", 1.0))}
        s["uniform_scale"] = {"on": True, "value": 1.0}
        return s

    def visual_clip(self, c, tl_start, render_index):
        m = self.src(c["source"])
        if m["kind"] == "audio":
            sys.exit(f"{m['path']} has no video stream; put it on an audio track")
        if m["kind"] == "photo":
            src_start, dur = 0, self.us(c["duration"])
        else:
            src_start = self.us(c.get("in", 0))
            dur = self.us(c["out"]) - src_start if "out" in c else m["duration"] - src_start
            if src_start + dur > m["duration"]:
                sys.exit(f"out point beyond media end: {m['path']}")
        mat = copy.deepcopy(self.snap["video_material"])
        mid = UID()
        name = os.path.basename(m["path"])
        mat.update({"id": mid, "type": m["kind"], "path": m["path"], "material_name": name,
                    "duration": m["duration"], "width": m["width"], "height": m["height"],
                    "has_audio": m["has_audio"], "local_material_id": m["local_id"],
                    "unique_id": m["unique_id"], "category_name": "local", "media_path": ""})
        self.mats["videos"].append(mat)
        refs = [self.companion(k) for k in ("speeds", "placeholder_infos", "canvases",
                                            "sound_channel_mappings", "material_colors",
                                            "vocal_separations") if k in self.snap["companions"]]
        return self.segment(mid, refs, src_start, dur, tl_start, dur, c, render_index)

    def track(self, ttype, name, segments):
        t = copy.deepcopy(self.snap["video_track"])
        t.update({"id": UID(), "type": ttype, "name": name or "", "is_default_name": not name,
                  "flag": 0, "attribute": 0, "segments": segments})
        return t

    def build(self):
        tracks = []
        # main track: contiguous from 0
        cursor, segs = 0, []
        for c in self.spec["main_track"]["clips"]:
            s = self.visual_clip(c, cursor, 0)
            cursor += s["target_timerange"]["duration"]
            segs.append(s)
        tracks.append(self.track("video", self.spec["main_track"].get("name"), segs))
        # overlay video tracks
        ri = 0
        for ot in self.spec.get("overlay_tracks", []):
            ri += 1
            segs = [self.visual_clip(c, self.us(c["start"]), ri) for c in ot["clips"]]
            tracks.append(self.track("video", ot.get("name"), segs))
        # text tracks (inferred format)
        for tt in self.spec.get("text_tracks", []):
            ri += 1
            segs = []
            for c in tt["clips"]:
                mid = UID()
                self.mats["texts"].append(text_material(mid, c))
                anim = UID()
                self.mats["material_animations"].append(material_animation(anim))
                dur = self.us(c["duration"])
                s = self.segment(mid, [anim], 0, dur, self.us(c["start"]), dur, c, 15000 + ri)
                s["track_render_index"] = ri
                segs.append(s)
            tracks.append(self.track("text", tt.get("name"), segs))
        # audio tracks (inferred material format)
        for at in self.spec.get("audio_tracks", []):
            segs = []
            for c in at["clips"]:
                m = self.src(c["source"])
                mid = UID()
                self.mats["audios"].append(audio_material(mid, m))
                src_start = self.us(c.get("in", 0))
                dur = (self.us(c["out"]) if "out" in c else m["duration"]) - src_start
                refs = [self.companion(k) for k in ("speeds", "placeholder_infos",
                                                    "sound_channel_mappings", "vocal_separations")
                        if k in self.snap["companions"]]
                segs.append(self.segment(mid, refs, src_start, dur, self.us(c["start"]), dur, c, 0))
            tracks.append(self.track("audio", at.get("name"), segs))

        for t in tracks:  # no overlaps inside a track
            t["segments"].sort(key=lambda s: s["target_timerange"]["start"])
            for a, b in zip(t["segments"], t["segments"][1:]):
                if a["target_timerange"]["start"] + a["target_timerange"]["duration"] > b["target_timerange"]["start"]:
                    sys.exit(f"overlapping clips on track '{t['name'] or t['type']}'")
        duration = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                       for t in tracks for s in t["segments"])
        self.info.update({"id": UID(), "duration": duration, "fps": self.fps, "tracks": tracks,
                          "canvas_config": {"ratio": "original", "width": self.w, "height": self.h,
                                            "background": None}})
        return self.info


# ----------------------------------------------------------------------------- writing
def manifest():
    return load(MANIFEST) if os.path.isfile(MANIFEST) else []


def write_draft(spec_path, force=False, register=True, allow_running=False):
    if capcut_running() and not allow_running:
        sys.exit("CapCut is running. Quit it first (it rewrites root_meta_info.json on exit).")
    spec = load(spec_path)
    snap = load(SNAPSHOT) if os.path.isfile(SNAPSHOT) else snapshot()
    name = spec["name"]
    folder = os.path.join(DRAFTS_ROOT, name)
    keep_id = registered_id(folder)     # CapCut may have imported the draft by itself: keep the id it knows
    if os.path.exists(folder):
        ours = {e["draft_id"] for e in manifest()}
        mp = os.path.join(folder, "draft_meta_info.json")
        did = load(mp).get("draft_id") if os.path.isfile(mp) else None
        if not force or did not in ours:
            sys.exit(f"'{folder}' exists" + ("" if did in ours else " and was NOT generated by this tool")
                     + (". Use --force to replace it." if did in ours else ". Refusing to touch it."))
        keep_id = keep_id or did
        shutil.rmtree(folder)

    b = Builder(spec, os.path.dirname(os.path.abspath(spec_path)), snap)
    info = b.build()
    tid, draft_id, project_id = info["id"], keep_id or UID(), UID()
    t_us, t_s = now_us(), int(time.time())
    info_txt = dump(info)
    media = list(b.media.values())
    mat_size = sum(m["size"] for m in media)

    # draft_meta_info.json -- media bin (type 0) lists every imported file
    meta = copy.deepcopy(snap["meta_skeleton"])
    meta_vals = []
    for m in media:
        e = copy.deepcopy(snap["meta_material"])
        d = PHOTO_DURATION if m["kind"] == "photo" else m["duration"] // 1000 * 1000
        e.update({"create_time": m["mtime"], "duration": d, "extra_info": os.path.basename(m["path"]),
                  "file_Path": m["path"], "width": m["width"], "height": m["height"], "id": m["local_id"],
                  "import_time": t_s, "import_time_ms": t_us,
                  "metetype": {"video": "video", "photo": "photo", "audio": "music"}[m["kind"]],
                  "roughcut_time_range": {"duration": d, "start": 0},
                  "sub_time_range": {"duration": -1, "start": -1}, "type": 0, "md5": ""})
        meta_vals.append(e)
    for grp in meta["draft_materials"]:
        if grp["type"] == 0:
            grp["value"] = meta_vals
    meta.update({"draft_cover": "draft_cover.jpg", "draft_fold_path": folder, "draft_id": draft_id,
                 "draft_name": name, "draft_root_path": DRAFTS_ROOT, "draft_need_rename_folder": False,
                 "draft_timeline_materials_size_": mat_size, "tm_draft_create": t_us,
                 "tm_draft_modified": t_us, "tm_draft_removed": 0, "tm_duration": info["duration"]})

    vstore = copy.deepcopy(snap["virtual_store"])
    for grp in vstore["draft_virtual_store"]:
        if grp["type"] == 1:
            grp["value"] = [{"child_id": m["local_id"], "parent_id": ""} for m in media]

    proj = copy.deepcopy(snap["project_json"])
    proj.update({"create_time": t_us, "update_time": t_us, "id": project_id, "main_timeline_id": tid,
                 "timelines": [{"create_time": t_us, "id": tid, "is_marked_delete": False,
                                "name": "Timeline 01", "update_time": t_us}]})
    layout = {"dockItems": [{"dockIndex": 0, "ratio": 1, "timelineIds": [tid],
                             "timelineNames": ["Timeline 01"]}], "layoutOrientation": 1}
    idmap = {"id_mapping": {"mapping": [{"short_id": str(1000 + i), "uuid": s}
                                        for i, s in enumerate(b.segment_ids)],
                            "next_index": 1000 + len(b.segment_ids), "version": "1.0.0"}}
    settings = ("[General]\ncloud_last_modify_platform=mac\n"
                f"draft_create_time={t_s}\ndraft_last_edit_time={t_s}\nreal_edit_keys=1\nreal_edit_seconds=0\n")
    agency = {"is_auto_agency_enabled": False, "is_auto_agency_popup": False,
              "is_single_agency_mode": False, "marterials": None, "use_converter": False,
              "video_resolution": 720}

    # stage in the work folder, then copy into CapCut's drafts root
    stage = os.path.join(HERE, "build", name)
    if os.path.exists(stage):
        shutil.rmtree(stage)
    tdir = os.path.join(stage, "Timelines", tid)
    files = {
        "draft_info.json": info_txt, "draft_info.json.bak": info_txt, "template-2.tmp": info_txt,
        "draft_meta_info.json": dump(meta), "draft_virtual_store.json": dump(vstore),
        "key_value.json": "{}", "draft_settings": settings, "draft_agency_config.json": dump(agency),
        "draft_biz_config.json": "", "timeline_layout.json": dump(layout),
        "Timelines/project.json": dump(proj), "Timelines/project.json.bak": dump(proj),
        "common_attachment/attachment_id_mapping.json": dump(idmap),
    }
    for k, v in snap["aux_files"].items():
        files.setdefault(k, v)
    for k, v in list(files.items()):
        if k.startswith("Timelines/"):
            continue
        if k in ("draft_info.json", "draft_info.json.bak", "template-2.tmp",
                 "attachment_pc_common.json", "attachment_editing.json") or k.startswith("common_attachment/"):
            files[f"Timelines/{tid}/{k}"] = v
    for rel, txt in files.items():
        write_text(os.path.join(stage, rel), txt)
    for dname in EMPTY_DIRS:
        os.makedirs(os.path.join(stage, dname), exist_ok=True)
    cover = spec.get("cover") or os.path.join(HERE, "media", "cover.jpg")
    if os.path.isfile(cover):
        shutil.copy2(cover, os.path.join(stage, "draft_cover.jpg"))
        shutil.copy2(cover, os.path.join(tdir, "draft_cover.jpg"))

    shutil.copytree(stage, folder)
    print(f"draft written: {folder}  ({info['duration']/1e6:.2f} s, {len(info['tracks'])} tracks)")

    entries = [e for e in manifest() if e["folder"] != folder]
    entries.append({"name": name, "draft_id": draft_id, "folder": folder,
                    "created": dt.datetime.now().isoformat(timespec="seconds")})
    write_text(MANIFEST, json.dumps(entries, ensure_ascii=False, indent=1))

    if register:
        register_draft(snap, meta, folder, info, mat_size, t_us)
    validate(folder)
    return folder


def registered_id(folder):
    """draft_id that root_meta_info.json already holds for this folder (read only), or None."""
    try:
        root = load(os.path.join(DRAFTS_ROOT, "root_meta_info.json"))
    except (OSError, ValueError):
        return None
    return next((e.get("draft_id") for e in root.get("all_draft_store", [])
                 if os.path.normpath(e.get("draft_fold_path", "")) == os.path.normpath(folder)), None)


def register_draft(snap, meta, folder, info, mat_size, t_us):
    rp = os.path.join(DRAFTS_ROOT, "root_meta_info.json")
    print("root_meta_info.json backup:", backup(rp))
    root = load(rp)
    e = copy.deepcopy(snap["root_entry"])
    e.update({"draft_cover": os.path.join(folder, "draft_cover.jpg"), "draft_fold_path": folder,
              "draft_id": meta["draft_id"], "draft_json_file": os.path.join(folder, "draft_info.json"),
              "draft_name": meta["draft_name"], "draft_root_path": DRAFTS_ROOT,
              "draft_timeline_materials_size": mat_size, "tm_draft_create": t_us,
              "tm_draft_modified": t_us, "tm_draft_removed": 0, "tm_duration": info["duration"],
              "streaming_edit_draft_ready": True})
    store = [x for x in root["all_draft_store"] if x["draft_fold_path"] != folder]
    root["all_draft_store"] = [e] + store
    root["draft_ids"] = len(root["all_draft_store"])
    tmp = rp + ".tmp"
    write_text(tmp, dump(root))
    load(tmp)  # parse back before swapping in
    os.replace(tmp, rp)
    print("registered in root_meta_info.json")


def remove(name):
    if capcut_running():
        sys.exit("Quit CapCut first.")
    folder = os.path.join(DRAFTS_ROOT, name)
    ours = {e["folder"]: e for e in manifest()}
    if folder not in ours:
        sys.exit(f"'{name}' was not generated by this tool; refusing.")
    rp = os.path.join(DRAFTS_ROOT, "root_meta_info.json")
    print("backup:", backup(rp))
    root = load(rp)
    root["all_draft_store"] = [x for x in root["all_draft_store"] if x["draft_fold_path"] != folder]
    root["draft_ids"] = len(root["all_draft_store"])
    write_text(rp, dump(root))
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    media = os.path.join(os.path.expanduser("~/Movies"), "CapCut", "claude-media", name)
    if os.path.isdir(media):            # only hard links / copies this tool staged for the draft
        shutil.rmtree(media)
    write_text(MANIFEST, json.dumps([e for e in manifest() if e["folder"] != folder], indent=1))
    print("removed", folder)


# ----------------------------------------------------------------------------- validation
def validate(folder):
    errs, n = [], 0
    for dp, _, fs in os.walk(folder):
        for f in fs:
            p = os.path.join(dp, f)
            if f.endswith((".json", ".bak", ".tmp")) and os.path.getsize(p) > 0:
                try:
                    load(p)
                    n += 1
                except Exception as ex:
                    errs.append(f"JSON parse failed: {p}: {ex}")
    info = load(os.path.join(folder, "draft_info.json"))
    meta = load(os.path.join(folder, "draft_meta_info.json"))
    proj = load(os.path.join(folder, "Timelines", "project.json"))
    tid = info["id"]
    if proj["main_timeline_id"] != tid or tid not in [t["id"] for t in proj["timelines"]]:
        errs.append("project.json main_timeline_id != draft_info id")
    root_txt = open(os.path.join(folder, "draft_info.json"), "rb").read()
    for rel in ["draft_info.json.bak", "template-2.tmp", f"Timelines/{tid}/draft_info.json",
                f"Timelines/{tid}/draft_info.json.bak", f"Timelines/{tid}/template-2.tmp"]:
        p = os.path.join(folder, rel)
        if not os.path.isfile(p) or open(p, "rb").read() != root_txt:
            errs.append(f"copy mismatch: {rel}")
    ids = {}
    for k, lst in info["materials"].items():
        for m in lst:
            if isinstance(m, dict) and "id" in m:
                if m["id"] in ids:
                    errs.append(f"duplicate material id {m['id']}")
                ids[m["id"]] = (k, m)
    want = {"video": {"videos"}, "audio": {"audios"}, "text": {"texts"}}
    end = 0
    for t in info["tracks"]:
        for s in t["segments"]:
            k, m = ids.get(s["material_id"], (None, None))
            if k not in want.get(t["type"], set()):
                errs.append(f"segment {s['id']} -> material {s['material_id']} not in {want.get(t['type'])}")
            for r in s["extra_material_refs"]:
                if r not in ids:
                    errs.append(f"segment {s['id']} dangling ref {r}")
            st, tt = s["source_timerange"], s["target_timerange"]
            if m and k in ("videos", "audios") and st["start"] + st["duration"] > m["duration"]:
                errs.append(f"segment {s['id']} source range beyond media")
            if m and "path" in m and m.get("path") and not os.path.isfile(m["path"]):
                errs.append(f"missing media file {m['path']}")
            end = max(end, tt["start"] + tt["duration"])
    main = info["tracks"][0]["segments"]
    pos = 0
    for s in main:
        if s["target_timerange"]["start"] != pos:
            errs.append(f"main track gap/overlap at {pos}")
        pos = s["target_timerange"]["start"] + s["target_timerange"]["duration"]
    if end != info["duration"] or meta["tm_duration"] != info["duration"]:
        errs.append("duration mismatch (tracks/draft_info/meta)")
    if os.path.normpath(meta["draft_fold_path"]) != os.path.normpath(folder):
        errs.append("meta draft_fold_path != folder")
    if meta["draft_name"] != os.path.basename(folder):
        errs.append("meta draft_name != folder name")
    root = load(os.path.join(DRAFTS_ROOT, "root_meta_info.json"))
    reg = [e for e in root["all_draft_store"] if e["draft_fold_path"] == folder]
    if not reg:
        print("  note: not registered in root_meta_info.json (CapCut should still discover the folder)")
    elif reg[0]["draft_id"] != meta["draft_id"]:
        errs.append("root_meta_info draft_id != meta draft_id")
    print(f"validate: parsed {n} JSON files, {len(info['tracks'])} tracks, "
          f"{sum(len(t['segments']) for t in info['tracks'])} segments, {info['duration']/1e6:.2f} s")
    for e in errs:
        print("  ERROR:", e)
    print("  OK" if not errs else f"  {len(errs)} problem(s)")
    return not errs


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot"); p.add_argument("--template")
    p = sub.add_parser("build"); p.add_argument("spec"); p.add_argument("--force", action="store_true")
    p.add_argument("--no-register", action="store_true"); p.add_argument("--allow-running", action="store_true")
    p = sub.add_parser("validate"); p.add_argument("folder")
    p = sub.add_parser("remove"); p.add_argument("name")
    a = ap.parse_args()
    if a.cmd == "snapshot":
        snapshot(a.template)
    elif a.cmd == "build":
        write_draft(a.spec, a.force, not a.no_register, a.allow_running)
    elif a.cmd == "validate":
        sys.exit(0 if validate(os.path.abspath(a.folder)) else 1)
    elif a.cmd == "remove":
        remove(a.name)
