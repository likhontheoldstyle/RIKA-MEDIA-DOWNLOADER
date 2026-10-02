# RIKA MEDIA DOWNLOADER

Fast and secure YouTube media downloader website. Paste a YouTube URL, see every
available video quality and audio option, download directly, or convert audio to
a real MP3 on the server.

## Project overview

Python web application built for Vercel serverless deployment, also runnable
locally. Media metadata comes from the configured upstream YouTube media API.
The frontend never sees secrets, raw upstream URLs, or internal paths. Downloads
use short-lived encrypted tokens. Audio can be transcoded to genuine MP3 with
FFmpeg (libmp3lame, 192 kbps) — never a renamed M4A file.

## Architecture

```
public/index.html        -> glassmorphism frontend (vanilla JS, no secrets)
api/*.py                 -> Vercel serverless entrypoints, one ASGI app each
main/app.py              -> FastAPI factory, routes, error handlers
main/startup.py          -> directory setup, startup logging
main/shutdown.py         -> cleanup hooks
main.py                  -> tiny entrypoint, exposes `app`
handler/youtube_handler.py -> analysis orchestration
handler/media_handler.py   -> normalization helpers
handler/download_handler.py -> token verification, download targets
handler/mp3_handler.py     -> MP3 conversion orchestration
social/youtube.py          -> ONLY place with upstream API knowledge
core/*                   -> config, constants, exceptions, logger, utils
security/*               -> middleware, rate limit, validation, headers
```

Browser flow for video/audio:

```
Browser -> POST /api/youtube -> upstream API -> normalized media + tokens
Browser -> GET /api/download?token=... -> 302 redirect to media source URL
```

Browser flow for MP3:

```
Browser -> POST /api/mp3 {token} -> download source audio
        -> FFmpeg transcode -> audio/mpeg stream -> Browser
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill values (see below).

## Environment variables

| Variable            | Purpose                                            | Default                          |
|---------------------|----------------------------------------------------|----------------------------------|
| APP_ENV             | `production` or `development`                      | `production`                     |
| SECRET_KEY          | Signs/encrypts download tokens. Hardcoded in      | hardcoded                        |
|                     | `core/config.py`.                                  |                                  |
| YTDL_API_URL        | Upstream YouTube media API endpoint                | ytultra endpoint                 |
| FFMPEG_PATH         | Full path to ffmpeg binary (optional override)     | auto-detect                      |
| CONVERTER_URL       | Remote MP3 converter API (fallback if no FFmpeg)   | empty (MP3 disabled)             |
| CONVERTER_API_KEY   | API key for remote converter                       | empty                            |
| RATE_LIMIT          | Requests per minute per IP                         | `10`                             |
| MP3_RATE_LIMIT      | MP3 conversions per minute per IP                  | `3`                              |
| CACHE_TTL           | Upstream response cache seconds                    | `600`                            |
| TOKEN_TTL           | Download token lifetime seconds                    | `2700`                           |
| MAX_REQUEST_SIZE    | Max JSON body bytes                                | `1048576`                        |
| MP3_BITRATE         | MP3 bitrate                                        | `192k`                           |
| MP3_MAX_SOURCE_BYTES| Max source audio download bytes for conversion     | `262144000`                      |
| TEMP_DIR            | Temp working directory                             | `var/temp`                       |

## Local development

```bash
python main.py
```

Open http://localhost:8000/ — the rewrite serves `public/index.html` only on
Vercel; locally open `public/index.html` in a browser while the API runs, or
serve the folder statically.

Run tests:

```bash
python -m pytest tests/ -q
```

## Vercel deployment

1. Push this project to GitHub.
2. In Vercel, import the repository.
3. Set environment variables (at minimum `SECRET_KEY` with a long random
   string). Everything else has working defaults.
4. Deploy. Vercel detects Python from `requirements.txt`.

`vercel.json` maps `/` to `public/index.html`. Each file in `api/` becomes a
serverless function exporting an ASGI `app`.

## FFmpeg requirement

MP3 conversion needs a real FFmpeg binary with `libmp3lame`:

- Local: install FFmpeg on the system (`ffmpeg` on PATH) or set `FFMPEG_PATH`.
- Vercel: `imageio-ffmpeg` (in `requirements.txt`) ships a static FFmpeg binary
  and is detected automatically. No system install needed.

If neither is available, set `CONVERTER_URL` (+ `CONVERTER_API_KEY`) to use a
remote conversion backend:

```
POST {CONVERTER_URL}
Headers: Content-Type: application/json, X-API-Key: {CONVERTER_API_KEY}
Body: {"audio_url": "...", "format": "mp3", "bitrate": "192k", "title": "..."}
Expected: 200 {"download_url": "https://.../file.mp3"}
```

If no converter is available at all, the API reports `mp3_available: false`,
the frontend hides the MP3 option, and `POST /api/mp3` returns 503. MP3 is
never faked.

## MP3 conversion architecture

`handler/mp3_handler.py` orchestrates: verify encrypted audio token, stream the
source audio to a temp file (size-capped), run FFmpeg via subprocess with a
timeout (`-vn -codec:a libmp3lame -b:a 192k`), stream the result back as
`audio/mpeg` with a safe `Content-Disposition` filename, then delete temp files
in a background task. Failures clean up in `finally`-style paths. FFmpeg
command lines and temp paths are never exposed to the client.

## Security architecture

- Strict YouTube-only URL validation; SSRF protection (scheme allowlist,
  host allowlist, IP-literal and private-range rejection, DNS re-resolution
  check for download targets).
- Download targets restricted to `*.googlevideo.com` over HTTPS.
- Media URLs never sent to the browser; Fernet-encrypted short-lived tokens
  instead (integrity + expiry).
- IP-based rate limiting (general + stricter MP3 bucket) plus burst/abuse
  blocking in middleware.
- Security headers: CSP, X-Content-Type-Options, DENY framing,
  Referrer-Policy, Permissions-Policy, HSTS.
- Request body size limits; safe error messages only (no tracebacks, paths,
  or exception names).
- Secret masking in logs; no secrets in frontend; same-origin API only.
- Sanitized filenames; safe subprocess invocation (argument list, no shell).

Frontend source is public by nature — all secrets stay server-side. No fake
"encryption" of HTML/JS is used as a security mechanism.

## API endpoints

### POST /api/youtube

Request:

```json
{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
```

Response:

```json
{
  "success": true,
  "title": "YouTube Video",
  "duration": 213,
  "thumbnail": "https://i.ytimg.com/...",
  "mp3_available": true,
  "media": [
    {"token": "...", "type": "video", "quality": "1080p", "format": "MP4",
     "size": "77.16 MB", "size_bytes": 80911999},
    {"token": "...", "type": "audio", "quality": "M4A", "format": "M4A",
     "size": "3.29 MB", "size_bytes": 3449447}
  ]
}
```

### GET /api/download?token=...

Validates the token, then 302-redirects to the media source URL.

### GET /api/media?token=...

Returns safe metadata for a token: filename, kind, quality, format, mime.

### POST /api/mp3

Request: `{"token": "..."}` (audio token from `/api/youtube`).

Response: `audio/mpeg` stream with `Content-Disposition: attachment`.
503 when conversion is unavailable.

### GET /api/health

```json
{"status": "ok"}
```

Error format (all endpoints):

```json
{"success": false, "error": "Safe error message"}
```

## Troubleshooting

- `Invalid YouTube URL` — only youtube.com / youtu.be links are accepted.
- `No media found` — upstream returned nothing usable for this video.
- `Rate limit exceeded` — slow down; limits are per IP.
- `MP3 conversion is temporarily unavailable` — no FFmpeg and no
  `CONVERTER_URL` configured.
- `This download link has expired` — tokens live 45 minutes; analyze again.
- On Vercel Hobby, functions time out after 60 seconds: very long MP3
  conversions may not finish. Use a remote converter or Vercel Pro for
  longer workloads.

## Vercel-specific limitations

- Serverless functions are stateless: tokens are self-contained (encrypted),
  not server memory.
- `/tmp` is the only writable directory; temp files are cleaned after each
  conversion.
- Function execution time and memory are limited by the Vercel plan.
- Large video/audio files are 302-redirected for direct browser download and
  are never proxied through the function.
- In-memory rate limiting and caching are per function instance.

## Legal notice

Download content only when you have the right or permission to do so.
