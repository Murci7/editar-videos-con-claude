"""Build teleprompter.html from guion-teleprompter.txt (blocks: a line of ─, 'TOMA N · TITLE', a line of ─, then text).

Usage: python make_teleprompter.py guion-teleprompter.txt teleprompter.html
Keys in the page: double-click start/stop · F fullscreen · ↑↓ speed · →← take · R restart · [ ] move text · +/− size.
"""
import json, re, sys
from pathlib import Path
txt = Path(sys.argv[1]).read_text(encoding="utf-8")
parts = re.split(r"─+\n(TOMA [^\n]+)\n─+\n", txt)
tomas = [{"t": parts[i].strip(), "x": parts[i + 1].strip()} for i in range(1, len(parts), 2)]
tpl = (Path(__file__).parent / "teleprompter.template.html").read_text(encoding="utf-8")
Path(sys.argv[2]).write_text(tpl.replace("__TOMAS__", json.dumps(tomas, ensure_ascii=False)), encoding="utf-8")
print(f"{len(tomas)} tomas → {sys.argv[2]}")
