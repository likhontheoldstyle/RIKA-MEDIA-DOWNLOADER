import re

INTERNAL = ("core", "security", "social", "handler", "main", "api")

SECTIONS = [
    ("core/constants.py", {}),
    ("core/exceptions.py", {}),
    ("core/logger.py", {}),
    ("core/config.py", {}),
    ("core/utils.py", {"config.": ""}),
    ("security/security_config.py", {}),
    ("security/headers.py", {}),
    ("security/validation.py", {"config.": ""}),
    ("security/rate_limit.py", {"config.": ""}),
    ("security/middleware.py", {"scfg.": "", "config.": ""}),
    ("social/youtube.py", {"config.": "", "utils.": ""}),
    ("handler/youtube_handler.py", {"yt.": "", "config.": "", "utils.": ""}),
    ("handler/download_handler.py", {"utils.": ""}),
    ("handler/media_handler.py", {"utils.": ""}),
    ("handler/mp3_handler.py", {"config.": "", "utils.": ""}),
]

API_FILES = [
    ("build/api_src/youtube.py", {"utils.": "", "youtube_handler.": ""}),
    ("build/api_src/download.py", {"download_handler.": ""}),
    ("build/api_src/media.py", {"download_handler.": ""}),
    ("build/api_src/mp3.py", {"mp3_handler.": "", "utils.": "", "config.": ""}),
    ("build/api_src/health.py", {}),
]


def is_internal_import(first_line):
    m = re.match(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)", first_line)
    if not m:
        return False
    mod = m.group(1)
    return mod.split(".")[0] in INTERNAL


def strip_sections(path):
    with open(path) as fh:
        lines = fh.readlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("sys.path.insert("):
            depth = stripped.count("(") - stripped.count(")")
            i += 1
            while depth > 0 and i < len(lines):
                depth += lines[i].count("(") - lines[i].count(")")
                i += 1
            continue
        if re.match(r"^\s*(from|import)\s+", line) and is_internal_import(line):
            depth = line.count("(") - line.count(")")
            i += 1
            while depth > 0 and i < len(lines):
                depth += lines[i].count("(") - lines[i].count(")")
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def apply_replacements(lines, reps):
    if not reps:
        return lines
    out = []
    for line in lines:
        for old, new in reps.items():
            if old in line:
                line = line.replace(old, new)
        out.append(line)
    return out


parts = []
parts.append("from fastapi import FastAPI, Request\nfrom fastapi.responses import JSONResponse\n")
for path, reps in SECTIONS:
    lines = apply_replacements(strip_sections(path), reps)
    parts.append("".join(lines).rstrip() + "\n")

for path, reps in API_FILES:
    lines = strip_sections(path)
    lines = [l for l in lines
             if l.strip() != "from main.app import create_app"
             and l.strip() != "app = create_app()"]
    lines = apply_replacements(lines, reps)
    parts.append("".join(lines).rstrip() + "\n")

with open("main/app.py") as fh:
    app_src = fh.read()
m = re.search(r"(def create_app\(\):\n(?:.*\n)*)", app_src)
func_lines = []
for line in m.group(1).splitlines(keepends=True):
    s = line.strip()
    if re.match(r"from api\.\w+ import \w+", s):
        continue
    func_lines.append(line)
parts.append("".join(func_lines).rstrip() + "\n")
parts.append("app = create_app()\n")

bundle = "\n".join(parts)
with open("api/index.py", "w") as fh:
    fh.write(bundle)

names = {}
for mm in re.finditer(r"^(?:def|class)\s+(\w+)", bundle, re.M):
    names.setdefault(mm.group(1), 0)
    names[mm.group(1)] += 1
dups = {k: v for k, v in names.items() if v > 1}
print("dups:", dups if dups else "none")
print("bytes:", len(bundle))
