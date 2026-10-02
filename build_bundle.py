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
    ("social/platforms.py", {}),
    ("social/cobalt.py", {"config.": ""}),
    ("handler/youtube_handler.py", {"yt.": "", "config.": "", "utils.": ""}),
    ("handler/fetch_handler.py", {"config.": "", "utils.": ""}),
    ("handler/download_handler.py", {"utils.": ""}),
    ("handler/media_handler.py", {"utils.": ""}),
    ("handler/mp3_handler.py", {"config.": "", "utils.": ""}),
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


ROUTES = {
    "youtube": ('post', "/api/youtube", "youtube_endpoint"),
    "download": ('get', "/api/download", "download_endpoint"),
    "media": ('get', "/api/media", "media_endpoint"),
    "mp3": ('post', "/api/mp3", "mp3_endpoint"),
    "health": ('get', "/api/health", "health_endpoint"),
    "fetch": ('post', "/api/fetch", "fetch_endpoint"),
}

shared_parts = []
shared_parts.append("from fastapi import FastAPI, Request\nfrom fastapi.responses import JSONResponse\n")
for path, reps in SECTIONS:
    lines = apply_replacements(strip_sections(path), reps)
    shared_parts.append("".join(lines).rstrip() + "\n")
shared_bundle = "\n".join(shared_parts)

API_REPS = {
    "build/api_src/youtube.py": {"utils.": "", "youtube_handler.": ""},
    "build/api_src/download.py": {"download_handler.": ""},
    "build/api_src/media.py": {"download_handler.": ""},
    "build/api_src/mp3.py": {"mp3_handler.": "", "utils.": "", "config.": ""},
    "build/api_src/health.py": {},
    "build/api_src/fetch.py": {"fetch_handler.": ""},
}

with open("main/app.py") as fh:
    app_src = fh.read()

parts = [shared_bundle]
for path in ("build/api_src/youtube.py", "build/api_src/download.py",
             "build/api_src/media.py", "build/api_src/mp3.py",
             "build/api_src/health.py", "build/api_src/fetch.py"):
    reps = dict(API_REPS.get(path, {}))
    lines = strip_sections(path)
    lines = [l for l in lines
             if l.strip() != "from main.app import create_app"
             and l.strip() != "app = create_app()"]
    lines = apply_replacements(lines, reps)
    parts.append("".join(lines).rstrip() + "\n")

wiring = []
wiring.append("app = FastAPI(title=\"RIKA MEDIA DOWNLOADER\", docs_url=None, redoc_url=None, openapi_url=None)")
wiring.append("app.add_middleware(SecurityMiddleware)")
for _name, (method, route, func) in ROUTES.items():
    wiring.append("app.%s(\"%s\")(%s)" % (method, route, func))
wiring.append("")
wiring.append("@app.exception_handler(AppError)")
wiring.append("async def app_error_handler(request: Request, exc: AppError):")
wiring.append("    return JSONResponse(")
wiring.append("        {\"success\": False, \"error\": exc.safe_message},")
wiring.append("        status_code=exc.status_code,")
wiring.append("    )")
wiring.append("")
wiring.append("@app.exception_handler(Exception)")
wiring.append("async def unhandled_handler(request: Request, exc: Exception):")
wiring.append("    return JSONResponse(")
wiring.append("        {\"success\": False, \"error\": GENERIC_ERROR},")
wiring.append("        status_code=500,")
wiring.append("    )")
parts.append("\n".join(wiring) + "\n")

with open("api/index.py", "w") as fh:
    fh.write("\n".join(parts))

names = {}
bundle_check = shared_bundle
for mm in re.finditer(r"^(?:def|class)\s+(\w+)", bundle_check, re.M):
    names.setdefault(mm.group(1), 0)
    names[mm.group(1)] += 1
dups = {k: v for k, v in names.items() if v > 1}
print("dups:", dups if dups else "none")
