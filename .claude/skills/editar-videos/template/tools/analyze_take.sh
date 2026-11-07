#!/bin/bash
# Quick technical check of a test clip or take: format, loudness, peak, echo (RT60) and 3 frames.
# Usage: analyze_take.sh clip.mp4 [out_dir]
F="$1"; O="${2:-/tmp/take-check}"; mkdir -p "$O"; HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-python3}"
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate -of compact "$F"
ffmpeg -hide_banner -i "$F" -map 0:a -af "ebur128=framelog=quiet,astats=metadata=0:measure_perchannel=0:measure_overall=Peak_level" -f null - 2>&1 | grep -E " I:|Peak level" | head -2
ffmpeg -hide_banner -loglevel error -y -i "$F" -vn -ac 1 -ar 48000 -c:a pcm_s16le "$O/a.wav" && $PY "$HERE/rt60.py" "$O/a.wav"
for t in 2 8 15; do ffmpeg -hide_banner -loglevel error -y -ss $t -i "$F" -frames:v 1 -vf scale=960:-1 "$O/frame_$t.jpg"; done
echo "fotogramas en $O (objetivo: −16…−19 LUFS en bruto, picos < −3 dB, RT60 < 0,35 s, 1920×1080 sin franjas)"
