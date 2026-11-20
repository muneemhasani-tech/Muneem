# MCP servers and Claude Desktop extensions for analysing local video files (state as of 12 Nov 2026)

Method note for the report writer: package existence, versions and release dates were checked directly against the PyPI and npm registry JSON on 2026-11-12. READMEs were read from raw.githubusercontent.com. The `ffmpeg-mcp-lite` behaviour was confirmed by reading the source in its PyPI sdist. GitHub's API was not reachable in this session, so star counts and last-commit dates are mostly missing (see Gaps). Nothing was installed or run on Windows; all Windows notes come from the projects' own docs.

## 1. Which MCP servers extract video frames and return them to Claude as images? Does `ffmpeg-mcp-lite` do it?

### Takeaway
`ffmpeg-mcp-lite` does have a frame-extraction tool, but it only writes files to disk and returns a text path, so Claude does not see the frames. The servers that return frames as real MCP image content, all free and local, are `mcp-video-analyzer` (npm), `media-context-mcp` (npm), `claude-real-video` / `crv-mcp` (PyPI), `lawriec/mcp-video-reader` (GitHub only), `pauloFroes/mcp-ffmpeg` (GitHub only) and `video-frame-analyzer` (npm); the first three also do local Whisper transcription.

### Cited Findings

**ffmpeg-mcp-lite (kevinwatt): frames to disk only**
- PyPI package `ffmpeg-mcp-lite`, latest 0.2.2, uploaded 2026-05-08, Python >=3.10 — [PyPI JSON](https://pypi.org/pypi/ffmpeg-mcp-lite/json)
- Eight tools: `ffmpeg_get_info`, `ffmpeg_convert`, `ffmpeg_compress`, `ffmpeg_trim`, `ffmpeg_merge`, `ffmpeg_extract_audio`, `ffmpeg_extract_frames` (params `file_path`, `interval` or `count`, `format` jpg/png/bmp/webp), `ffmpeg_add_subtitles`. Config is `"command": "uvx", "args": ["ffmpeg-mcp-lite"]`. 28 stars, 9 commits, no GitHub releases. README says it works on Windows, macOS and Linux; FFmpeg must be on PATH or set via `FFMPEG_PATH`/`FFPROBE_PATH` — [GitHub README](https://github.com/kevinwatt/ffmpeg-mcp-lite)
- Source of `tools/frames.py` in the 0.2.2 sdist: the function is typed `-> str`, writes `frame_%04d.<format>` into `<FFMPEG_OUTPUT_DIR>/<video stem>_frames`, and returns only the string `"Extracted {frame_count} frames to: {output_dir}"`. No image content is returned. A grep of the whole package for `ImageContent` / `Image(` found nothing — [PyPI sdist for ffmpeg-mcp-lite 0.2.2](https://pypi.org/project/ffmpeg-mcp-lite/#files)
- Default output directory is `~/Downloads` unless `FFMPEG_OUTPUT_DIR` is set — [GitHub README](https://github.com/kevinwatt/ffmpeg-mcp-lite)
- No transcription tool; `ffmpeg_extract_audio` only produces an audio file — [GitHub README](https://github.com/kevinwatt/ffmpeg-mcp-lite)

**mcp-video-analyzer (guimatheus92): frames as images + transcript + OCR, local files supported**
- npm `mcp-video-analyzer`, latest 0.11.0, published 2026-10-13 — [npm registry](https://registry.npmjs.org/mcp-video-analyzer)
- Install: `npx mcp-video-analyzer@latest` (Claude Desktop config uses `"command": "npx"`). Requires Node.js 22.12+. Bundles `ffmpeg-static`, so no system ffmpeg is needed for local files — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Tools: `analyze_video` (transcript + key frames + OCR + timeline + metadata), `analyze_videos` (batch), `get_transcript`, `get_metadata`, `get_frames`, `analyze_moment`, `get_frame_at`, `get_frame_burst` — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Local files: pass an absolute path or `file://` URI as the `url` argument; relative paths are rejected. Recognised extensions include `.mp4`, `.mov`, `.mkv`, `.webm` — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Frame policy: scene-change detection with perceptual-hash dedup; for static talking-head Reels with no cuts it falls back to uniform temporal sampling. `maxFrames` is 1–60, defaulting to about 12 for videos of 30 s or less. `get_frames` returns up to 20 frames. Emitted frames are capped at 800 px wide, JPEG quality 70 (`MCP_FRAME_MAX_WIDTH`, `MCP_FRAME_JPEG_QUALITY`) — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Transcription fallback chain: (1) `@huggingface/transformers` in-process, only if `WHISPER_HF_MODEL` is set (e.g. `Xenova/whisper-small`); (2) a `whisper` CLI on PATH or at `WHISPER_BIN` (`pip install -U openai-whisper`, or `whisper-ctranslate2` for faster-whisper); (3) OpenAI Whisper API if `OPENAI_API_KEY` is set. With none configured it returns an empty transcript plus a warning — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Defaults matter for Bangla: `WHISPER_MODEL` defaults to `tiny`, which the README calls "fast but weak for non-English audio"; it recommends `small` or `medium` plus `WHISPER_LANGUAGE` — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- Windows note from the README: pip installs `whisper.exe` into Python's `Scripts/` directory, which is often not on the PATH that GUI-launched MCP clients inherit; if transcripts come back empty, set `WHISPER_BIN` to the full path. Browser-cookie extraction for yt-dlp requires the browser to be closed on Windows — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- OCR runs via bundled `tesseract.js` on full-resolution frames — [README](https://github.com/guimatheus92/mcp-video-analyzer)

**media-context-mcp (vishalguptax): contact sheets, local, no API keys**
- npm `media-context-mcp`, latest 0.1.4, published 2026-06-23, Apache-2.0 — [npm registry](https://registry.npmjs.org/media-context-mcp)
- Install: config `"command": "npx", "args": ["-y", "media-context-mcp"]`, then a one-time `npx media-context-mcp setup` (core) and `npx media-context-mcp setup --audio` (transcription), which install helpers through the OS package manager. Node.js 18+, Windows/macOS/Linux — [README](https://github.com/vishalguptax/media-context-mcp)
- Tools: `analyze_media` (video, audio or image; file or URL) and `check_media_deps` — [README](https://github.com/vishalguptax/media-context-mcp)
- Default `sheet` mode tiles frames into one or two contact-sheet images; other modes are `frames` (full-size stills), `scenes`, `filmstrip`. Defaults: `maxFrames` 30, `grid` 5, per-frame `scale` 320 px, `format` webp. `transcript` is off by default; `whisperModel` defaults to `small`; OCR is optional with `ocrLang` default `eng` — [README](https://github.com/vishalguptax/media-context-mcp)
- README states everything runs locally with no API keys and no uploads — [README](https://github.com/vishalguptax/media-context-mcp)

**claude-real-video / crv-mcp (HUANGCHIHHUNGLeo): scene-aware frames + Whisper**
- PyPI `claude-real-video`, latest 0.10.7, uploaded 2026-09-26, Python >=3.10, extras `whisper`, `fast`, `mlx`, `speakers`, `mcp` — [PyPI JSON](https://pypi.org/pypi/claude-real-video/json)
- MCP setup: `pip install 'claude-real-video[mcp]'`, then Claude Desktop config `{ "mcpServers": { "crv": { "command": "crv-mcp" } } }`. The docs do not give a uvx command — [PyPI page](https://pypi.org/project/claude-real-video/)
- Tools: `watch_video(source, max_frames, language, transcribe)` returns a timestamped transcript plus the first batch of keyframes as images; `get_frames(source, start_index, count)` pages the rest; `get_transcript` (text only); `search_memory`; `list_watched`. Analyses are cached in `~/.cache/crv-mcp` — [PyPI page](https://pypi.org/project/claude-real-video/)
- The `fast` extra uses faster-whisper with a Silero VAD gate, falling back to the `whisper` CLI. Model sizes `tiny`, `base`, `small`, `medium`, `large`, `turbo`; CLI default `base`. `turbo` needs a 1.6 GB download and about 6 GB of memory — [PyPI page](https://pypi.org/project/claude-real-video/)
- The author states it was verified end to end on Claude Code only; Claude Desktop and Cursor are expected to work but were not separately tested. About 1.9k GitHub stars, MIT — [DEV Community post](https://dev.to/huangchihhungleo/let-claude-desktop-and-cursor-actually-watch-videos-mcp-fully-local-2gnf)
- Frame selection is scene-change detection plus a floor of one frame per second, then pixel-difference dedup against a sliding window. The README's example: a 58-second clip yields 26 kept frames versus 58 at fixed 1 fps. Accepts URLs via yt-dlp (README examples include an Instagram reel URL) or local files. A paid "crv Pro" ($19) adds camera-move and pacing analysis — [GitHub README](https://github.com/HUANGCHIHHUNGLeo/claude-real-video)

**mcp-video-reader (lawriec): simple frame tools, GitHub install only**
- Tools include `get_video_info`, `extract_frames` (`num_frames` 1–20, default 10, optional `start_time`/`end_time`; output is a text summary plus base64 JPEG images), `extract_frame_at_timestamp` (one base64 JPEG), plus convert/trim/audio/subtitle tools. No API key. No transcription — [README](https://github.com/lawriec/mcp-video-reader)
- The README recommends `npx -y mcp-video-reader`, but the npm registry returned no such package on 2026-11-12, so the working install is `npx -y github:lawriec/mcp-video-reader` — [npm registry lookup](https://registry.npmjs.org/mcp-video-reader); [README](https://github.com/lawriec/mcp-video-reader)

**mcp-ffmpeg (pauloFroes): minimal, GitHub install only**
- Install `npx -y github:pauloFroes/mcp-ffmpeg`; Node 18+, ffmpeg and ffprobe on PATH. Tools: `check_dependencies`, `get_media_info`, `extract_frames` ("returns base64 images"), `extract_audio` (to MP3), `split_audio`. MIT. No transcription — [README](https://github.com/pauloFroes/mcp-ffmpeg)

**Other npm packages confirmed to exist (not inspected in depth)**
- `video-frame-analyzer` 1.0.0, published 2026-03-01: "extracting key frames from videos and returning them as base64 images for Claude analysis"; no repository URL in the registry metadata — [npm registry](https://registry.npmjs.org/video-frame-analyzer)
- `@eequaled/frames-mcp` 1.1.0, published 2026-02-25: extracts frames and clips with ffmpeg; no repository URL in the registry metadata — [npm registry](https://registry.npmjs.org/@eequaled/frames-mcp)
- `clipwright-frames` 0.3.3 on PyPI, uploaded 2026-07-08, Python >=3.11: still-frame extraction into images, OTIO markers and a JSON manifest (editing-oriented) — [PyPI JSON](https://pypi.org/pypi/clipwright-frames/json)

**Desktop extensions (.mcpb)**
- A search of Anthropic's extension material found no Anthropic-reviewed video/FFmpeg/transcription extension; `.mcpb` files are zip archives with a `manifest.json` installable from Settings → Extensions — [Anthropic engineering post](https://www.anthropic.com/engineering/desktop-extensions); [Claude docs: MCPB](https://claude.com/docs/connectors/building/mcpb)

### Inferences
- For 20–60 s vertical reels with Bangla speech on a CPU-only Windows 10 machine, `mcp-video-analyzer` looks like the closest single-server fit: one `npx` line, bundled ffmpeg, frames returned at a sane size (800 px, about 12 frames for a 30 s clip), explicit handling of talking-head Reels, and a per-call `language`/`model` override. It still needs a separately installed Whisper CLI (or `WHISPER_HF_MODEL`) to transcribe.
- `media-context-mcp` is the cheapest in context (one or two contact sheets), but 320 px tiles may be too small to read on-screen Bangla captions; its `frames` mode or a higher `scale` would be needed for text overlays. Its OCR default is English; whether Bengali tesseract data installs through its setup command was not checked.
- `claude-real-video` can probably be launched without a global pip install via `uvx --from "claude-real-video[mcp,fast]" crv-mcp`, because the package exposes a `crv-mcp` console script and those extras exist. This command is inferred, not documented and not tested.
- `ffmpeg-mcp-lite` is still useful as the "extract" half of a two-server setup: it writes frames to a folder and the filesystem server (section 2) shows them to Claude.
- `misbahsy/video-audio-mcp` and "mcp-video" were named in the brief but were not confirmed in this session, so they are deliberately not catalogued.

### Gaps
- Star counts and last-commit dates for every repo except `ffmpeg-mcp-lite` (28 stars) and `claude-real-video` (about 1.9k, from the author's post) could not be fetched; the GitHub API was blocked in this session.
- No server was actually run in Claude Desktop on Windows 10. Whether each one's image results render and stay under Claude Desktop's result-size cap is untested. The `claude-real-video` author explicitly did not test Claude Desktop.
- The number of frames `crv-mcp`'s `watch_video` returns per call is not documented.
- Whether Anthropic's in-app extension directory now lists any video extension could not be checked (the directory is only browsable inside the app).

## 2. Can the official filesystem server's `read_media_file` return image files from disk to Claude in Claude Desktop? Size limits?

### Takeaway
Yes: `read_media_file` takes a path and returns image files as MCP `image` content (base64 + MIME type), so frames written by ffmpeg can be viewed without drag-and-drop. The server sets no size cap itself; the practical ceiling is Claude Desktop's community-reported ~1 MB tool-result limit, so frames should be downscaled JPEGs read one or a few at a time.

### Cited Findings
- `read_media_file` input is `path` only. It returns the file's bytes as base64 with MIME type; image and audio files come back as `image` or `audio` content, other types as an embedded `resource`. The README states no maximum file size for this tool — [filesystem server README](https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/filesystem/README.md)
- npm `@modelcontextprotocol/server-filesystem` latest is 2.3.0, published 2026-11-11 — [npm registry](https://registry.npmjs.org/@modelcontextprotocol/server-filesystem)
- Config: `"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "<allowed dir>", ...]`. The current README requires Node.js 24 or later. On Windows it says to launch through `cmd` with `"/c", "npx"` at the start of `args` — [filesystem server README](https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/filesystem/README.md)
- Windows path rules in the same README: alternate data streams, reserved device names (`CON`, `NUL`, `COM1`…) and path components ending in a dot or space are refused — [filesystem server README](https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/filesystem/README.md)
- A user bug report dated 9 June 2026 quotes the Claude Desktop error "Tool result is too large. Maximum size is 1MB"; it was closed the same day without an explanation — [issue mirror](https://claudeissues.com/issue/66519-bug-keep-omn-getting-the-message-tool-result-is-too-large-maximum-size-is-1mb)
- A third-party MCP server's client-compatibility guide says Claude Desktop and claude.ai impose a ~1 MB limit on tool result content, and works around it by returning a small WebP thumbnail. This came from a search snippet; the page itself returned 404 when fetched — [image-generation-mcp guide](https://pvliesdonk.github.io/image-generation-mcp/guides/client-compatibility)

### Inferences
- Base64 inflates bytes by about a third, so a 1 MB result cap means roughly 700 KB of raw image data per tool call in total. A 720 px-wide JPEG frame at moderate quality is typically well under that, so several small frames per call may fit, but a batch of full-resolution 1080×1920 PNGs will not.
- `read_media_file` reads one path per call, so viewing 10 frames means 10 tool calls. A server that returns several frames in one result (section 1) or a contact sheet is more convenient.
- The Node 24 requirement is new relative to older guides; a Windows 10 machine with an older Node would need an upgrade or a pinned older package version.

### Gaps
- No official Anthropic documentation of the 1 MB Claude Desktop tool-result limit was found; the figure rests on a user bug report and a third-party guide.
- Not verified on Windows: whether the current Claude Desktop build renders `read_media_file` image results reliably.
- `read_multiple_files` returning images was not checked; assume text only.

## 3. Which MCP servers bridge to a video-native model (Gemini, Twelve Labs)? Is there a free tier?

### Takeaway
Confirmed bridges are `ai-vision-mcp` (npm, Gemini, accepts local file paths), `gemini-video-understanding-mcp` (npm, URL-oriented), `video-research-mcp` (PyPI, Gemini) and the optional Twelve Labs Pegasus path inside `mcp-video-analyzer`. Gemini still has a free API tier covering several video-capable models in November 2026, but these bridges return text only, upload the video to Google, and free-tier content is used to improve Google's products.

### Cited Findings
- `ai-vision-mcp` (tan-yong-sheng): npm latest 0.0.7, published 2026-04-04. Run with `npx ai-vision-mcp` and env `GEMINI_API_KEY`. Has an `analyze_video` tool whose `videoSource` accepts a YouTube URL, GCS URI or local file path (README example `C:\Users\username\Downloads\video.mp4`). Models are set per function via env, e.g. `ANALYZE_VIDEO_MODEL` — [npm registry](https://registry.npmjs.org/ai-vision-mcp); [README](https://github.com/tan-yong-sheng/ai-vision-mcp)
- `gemini-video-understanding-mcp` (tan-yong-sheng): npm latest 0.0.10, published 2025-09-11, described as "video understanding using Google's Gemini models with URL support" — [npm registry](https://registry.npmjs.org/gemini-video-understanding-mcp)
- `video-research-mcp` (Galbaz1): PyPI latest 0.7.1, uploaded 2026-09-29, Python >=3.11, "MCP server for video analysis, document extraction, cited research and optional knowledge storage" — [PyPI JSON](https://pypi.org/pypi/video-research-mcp/json)
- `mcp-video-analyzer` can use Twelve Labs Pegasus when `TWELVELABS_API_KEY` is set; per its README this applies to direct video URLs and returns an AI-generated timestamped transcript and summary — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- An npm package `twelvelabs-mcp` 1.0.0 (published 2026-05-12, "TwelveLabs MCP Server") exists but has no repository URL in its registry metadata, so its publisher was not confirmed — [npm registry](https://registry.npmjs.org/twelvelabs-mcp)
- Gemini pricing page, free tier listed for: Gemini 4 Hydrogen, 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite, 3 Flash Preview, 2.5 Flash-Lite (among others). Not on the free tier: Gemini 4 Carbon, Gemini 4 Argon, 3.1 Pro Preview. Free-tier data is used to improve Google's products. Gemini 2.5 Pro and 2.5 Flash are deprecated, with requests routed to newer models from 1 December 2026 — [Gemini API pricing](https://aistudio.google.com/docs/pricing)
- Gemini video docs: default sampling is 1 frame per second (configurable); about 100 tokens per second of video at low media resolution and about 300 at high; audio adds 32 tokens per second and is processed alongside frames. Inline upload suits requests under 20 MB; the Files API allows 2 GB on the free tier. Supported types include `video/mp4`, `video/mov`, `video/webm`. The docs warn fast motion can lose detail at 1 FPS — [Gemini video understanding docs](https://aistudio.google.com/docs/video-understanding)
- Free-tier rate limits per model are no longer listed in the docs; the rate-limits page points to the AI Studio rate-limit dashboard for the account's active limits — [Gemini rate limits](https://aistudio.google.com/docs/rate-limits)
- Search-result listings also name `moe5445/gemini-video-mcp-server` (tool `analyze_video_file` for local files) and others on Glama/LobeHub; these were seen only as aggregator listings, not verified at source — [LobeHub listing](https://lobehub.com/mcp/moe5445-gemini-video-mcp-server)

### Inferences
- A 60-second reel costs roughly 6,000–20,000 Gemini input tokens (100–300 tokens/s plus 32/s audio), so a free-tier key should comfortably handle a handful of reels a day, subject to whatever daily request limit the account shows in AI Studio.
- `ai-vision-mcp`'s README examples reference 2.5-era model names (e.g. `gemini-2.5-flash-lite`). Given the 2.5 Flash/Pro deprecation on 1 Dec 2026, the model env vars should be set explicitly to a current free-tier model such as `gemini-3.5-flash-lite` or `gemini-4-hydrogen`. The exact model ID strings should be confirmed in AI Studio.
- A Gemini bridge is the only option here where a model hears the audio natively (tone, music) and gets true 1 fps coverage. It conflicts with the "free and local" preference on the local part: the reel is uploaded to Google and, on the free tier, may be used for product improvement.
- Because bridges return text, Claude is reading Gemini's description rather than seeing the video; pairing a bridge with a frame-returning server gives Claude both.

### Gaps
- Exact free-tier RPM/RPD numbers for video-capable models in November 2026 could not be obtained (shown only in the logged-in AI Studio dashboard).
- Gemini's Bangla/Banglish speech accuracy was not researched here.
- Whether `ai-vision-mcp` 0.0.7 works with Gemini 3.x/4 model IDs is untested. Its last npm release predates those names in the pricing page.
- No official first-party Twelve Labs MCP server was confirmed. Twelve Labs free-tier terms were not researched.

## 4. Are there MCP servers for local transcription (Whisper / faster-whisper / whisper.cpp) that run on CPU on Windows?

### Takeaway
Yes. `whisper-transcribe-mcp` (PyPI, faster-whisper, uvx one-liner, documents Windows quirks) is the best-documented; `simple-asr-mcp` (PyPI, faster-whisper, CPU int8 by default) and `video-transcriber-mcp` (npm, whisper.cpp) also exist. The all-in-one video servers in section 1 embed Whisper too.

### Cited Findings
- `whisper-transcribe-mcp` (ZahiriNatZuke): PyPI latest 1.1.3, uploaded 2026-09-22, Python >=3.10 — [PyPI JSON](https://pypi.org/pypi/whisper-transcribe-mcp/json)
- Its config: `"command": "uvx", "args": ["whisper-transcribe-mcp[local]"], "env": {"WHISPER_MODEL": "base"}`. Tools: `transcribe_file` (absolute path; `language` ISO 639 code, `model_size`, optional post-processing), `transcribe_base64`, `list_models`. `WHISPER_MODEL` options: `tiny`, `base`, `small`, `medium`, `large-v3`; default `base`. Local backend is used when no OpenAI key is set; the model downloads from HuggingFace on first use — [PyPI page](https://pypi.org/project/whisper-transcribe-mcp/)
- Windows notes on that page: use the full path to `uvx.exe` (find with `where.exe uvx`), add `"--python", "3.12"` to args to avoid `ctranslate2` wheel problems on newer Python, and give Claude the file's Windows path instead of attaching the audio — [PyPI page](https://pypi.org/project/whisper-transcribe-mcp/)
- Listed input formats are "mp3, wav, m4a, ogg, flac, webm, etc."; mp4 is not explicitly listed — [PyPI page](https://pypi.org/project/whisper-transcribe-mcp/)
- `simple-asr-mcp` (Selentar): PyPI latest 0.1.2, uploaded 2026-04-06. faster-whisper, "Runs on CPU, no cloud required". Tools `transcribe_file`, `list_models`. Defaults `WHISPER_MODEL=small`, `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`. Install documented as `pipx install simple-asr-mcp`; needs ffmpeg (Windows: `winget install Gyan.FFmpeg`). Estimated RAM: small ~2 GB, medium ~5 GB, large-v3 ~10 GB — [PyPI JSON](https://pypi.org/pypi/simple-asr-mcp/json); [README](https://github.com/Selentar/simple-asr-mcp)
- `video-transcriber-mcp` (nhatvu148): npm latest 2.0.0, published 2026-07-05; transcribes videos from 1000+ platforms or local video files using whisper.cpp — [npm registry](https://registry.npmjs.org/video-transcriber-mcp)
- `mcp-server-whisper` on PyPI (1.1.0, 2025-10-16) uses the OpenAI Whisper/GPT-4o API, so it is paid, not local — [PyPI JSON](https://pypi.org/pypi/mcp-server-whisper/json)
- Other faster-whisper servers surfaced only via listings: `BigUncle/Fast-Whisper-MCP-Server` (batching, CUDA auto-detect) and `uzusio/faster-whisper-mcp` (subtitles from video; git clone + uv) — [Glama listing](https://glama.ai/mcp/servers/BigUncle/Fast-Whisper-MCP-Server)

### Inferences
- For `whisper-transcribe-mcp`, feeding it the reel's `.mp4` may or may not work; the safe path is to extract audio first (`ffmpeg_extract_audio` from `ffmpeg-mcp-lite`, or plain ffmpeg) and pass the `.mp3`/`.m4a`. faster-whisper decodes through PyAV/ffmpeg and usually accepts mp4, but the server may filter by extension. Untested.
- Whisper's language list includes Bengali (code `bn`), so `language: "bn"` can be forced. This is background knowledge, not verified against a source in this session. Whisper's Bangla accuracy is noticeably weaker than English, and code-mixed Banglish is harder still; `small` is a sensible floor on an i7 CPU and `medium` or `large-v3` (int8) will be more accurate but slow. For 20–60 s clips even `medium` on CPU should finish in minutes rather than hours. These are estimates, not measurements.
- `simple-asr-mcp` can likely be run as `uvx simple-asr-mcp` since the console script matches the package name, but its docs only show pipx/pip.

### Gaps
- No benchmark of Whisper model sizes on Bangla/Banglish reels was gathered here; no source was found comparing faster-whisper with Gemini on Bangla.
- Whether `video-transcriber-mcp` ships a prebuilt whisper.cpp binary for Windows or needs a compiler was not checked.
- No MCP server wrapping a Bangla-fine-tuned Whisper model was found.

## 5. YouTube / Instagram / TikTok transcript or downloader MCP servers for published reels

### Takeaway
`@kevinwatt/yt-dlp-mcp` (npm, actively released) is the main downloader/subtitle server; `mcp-video-analyzer` and `claude-real-video` accept Instagram/TikTok/YouTube URLs directly through yt-dlp; `reel-relay` is a self-hosted Instagram-reel pipeline that needs a Groq key and a tunnel. Instagram frequently needs login cookies, and downloading others' content sits against platform terms.

### Cited Findings
- `@kevinwatt/yt-dlp-mcp`: npm latest 0.10.2, published 2026-10-29; "video and audio content download capabilities (e.g. YouTube, Facebook, Tiktok, etc.)" — [npm registry](https://registry.npmjs.org/@kevinwatt/yt-dlp-mcp)
- Its tools are prefixed `ytdlp_`: `ytdlp_search_videos`, `ytdlp_list_subtitle_languages`, `ytdlp_download_video_subtitles` (VTT), `ytdlp_download_transcript` (plain text), `ytdlp_download_video`, `ytdlp_download_audio`, `ytdlp_get_video_metadata`, `ytdlp_get_video_metadata_summary`, `ytdlp_get_video_comments`, `ytdlp_get_video_comments_summary`. Config: `npx -y @kevinwatt/yt-dlp-mcp@latest`; env `YTDLP_DOWNLOADS_DIR`, `YTDLP_DEFAULT_SUBTITLE_LANG` (default `en`). Windows is listed as supported — [README](https://github.com/kevinwatt/yt-dlp-mcp)
- `mcp-video-analyzer` supports YouTube, Vimeo, TikTok, Instagram, X, Twitch, Dailymotion and Facebook URLs when yt-dlp is installed (`pip install yt-dlp`): native captions first, Whisper fallback, downloads capped at 1080p. Cookies can be supplied via `YTDLP_COOKIES` — [README](https://github.com/guimatheus92/mcp-video-analyzer)
- `claude-real-video` accepts YouTube/Instagram/TikTok links via yt-dlp and a `--cookies` Netscape cookie file for login-gated sources; its README says "Only download content you have the right to" — [GitHub README](https://github.com/HUANGCHIHHUNGLeo/claude-real-video)
- `mcp-youtube-transcript` (jkawamoto): PyPI latest 0.3.5, uploaded 2025-06-26; retrieves YouTube transcripts only — [PyPI JSON](https://pypi.org/pypi/mcp-youtube-transcript/json)
- `clipscribe`: PyPI 0.1.1, uploaded 2026-08-22; "Extract transcripts from YouTube, TikTok, and Instagram URLs" with per-platform extras — [PyPI JSON](https://pypi.org/pypi/clipscribe/json)
- `reel-relay` (siemd2): self-hosted Python 3.11+ service. yt-dlp downloads the reel (≤720p), ffmpeg makes ~30 deduplicated 512 px JPEG keyframes, captions or Groq `whisper-large-v3` provide a timestamped transcript, and a FastMCP streamable-HTTP server exposes `list_recent_reels`, `get_reel(reel_id?, include_frames=true, max_frames=10)` and `get_reel_frames`, with frames delivered as MCP image content. Requires a free Groq API key and a cloudflared/Tailscale tunnel plus a Claude custom connector; git clone install, with macOS/Linux instructions — [README](https://github.com/siemd2/reel-relay)

### Inferences
- For analysing competitors' published reels, the lowest-friction route is to give `mcp-video-analyzer` or `crv-mcp` the reel URL and let it download, frame and transcribe in one call. Instagram often blocks anonymous yt-dlp downloads, so a cookies file from the user's own logged-in session is commonly needed, and extractors break periodically until yt-dlp is updated.
- Terms-of-service caveat: Instagram's and TikTok's terms restrict automated collection and downloading of content without permission, and YouTube's terms restrict downloading outside its own features. Downloading for private analysis is common practice but is not sanctioned by the platforms; re-uploading or redistributing the clips adds copyright risk; and using account cookies with automated tools carries some account-restriction risk. This is a general summary, not sourced legal analysis.
- Auto-captions for Bangla reels are often absent on Instagram, so the Whisper fallback will usually be what runs.
- `reel-relay` is over-engineered for a desktop workflow on Windows (tunnel, Groq key, no Windows instructions); it is relevant mainly if the user wants to forward reels from a phone.

### Gaps
- Current reliability of yt-dlp against Instagram and TikTok in November 2026 was not tested.
- The platforms' terms were not fetched and quoted in this session.
- No dedicated, verified "Instagram transcript" MCP package on npm/PyPI beyond those above was confirmed; `transcriptor-mcp` appears in directories but was not found on npm under the names tried.

## 6. Practical limits: number/size of images an MCP tool can return in Claude Desktop, and context usage

### Takeaway
Plan for small frames in small batches: Claude Desktop's tool-result cap is reported at about 1 MB per result, claude.ai allows 20 images per message, and each image costs ⌈w/28⌉×⌈h/28⌉ tokens, so a dozen 512–800 px vertical frames costs roughly 8k–18k tokens while full-resolution frames cost about 4.8k tokens each on current models.

### Cited Findings
- Image token cost: Claude processes images in 28×28-pixel patches; an image costs `⌈width / 28⌉ × ⌈height / 28⌉` visual tokens — [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Resolution tiers: Claude 4.7 and later models accept up to 2,576 px on the long edge and 4,784 visual tokens per image; other models 1,568 px and 1,568 tokens. Larger images are downscaled first — [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Count limits: 20 images per message on claude.ai; 100 per API request for 200k-context models and 600 for others. Max dimensions 8000×8000 px. Above 20 images in one API request a stricter per-image dimension limit applies, and images in earlier turns and inside `tool_result` content count toward that threshold. Max size per image is 10 MB on claude.ai and the Claude API — [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Supported formats: JPEG, PNG, GIF, WebP — [Claude vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Claude Desktop tool-result cap: a June 2026 user report quotes "Tool result is too large. Maximum size is 1MB" — [issue mirror](https://claudeissues.com/issue/66519-bug-keep-omn-getting-the-message-tool-result-is-too-large-maximum-size-is-1mb)
- A separate report describes a Claude Code MCP image response failing for exceeding 25,000 tokens; this is Claude Code, not Claude Desktop — [issue mirror](https://claudeissues.com/issue/9152-bug-claude-code-mcp-image-responses-token-exceeds-25000-tokens)
- A report describes a session becoming unusable with "Request too large (max 20MB)" after an MCP screenshot — [issue mirror](https://claudeissues.com/issue/37418-request-too-large-max-20mb-after-mcp-screenshot-session-becomes-unusable)
- One issue report says a tool result could carry as many as 15 images where an MCP resource filled context with one — [issue mirror](https://claudeissues.com/issue/14962-bug-mcp-resource-returning-image-fills-up-context-with-1-image-whereas-tool-resu)
- Server authors' own guardrails: `mcp-video-analyzer` caps emitted frames at 800 px wide/JPEG q70 and warns native-resolution frames cost several times more context; `mcp-video-reader` caps `extract_frames` at 20; `reel-relay` uses 512 px frames and `max_frames=10`; `media-context-mcp` defaults to 320 px tiles in one or two contact sheets — [mcp-video-analyzer README](https://github.com/guimatheus92/mcp-video-analyzer); [mcp-video-reader README](https://github.com/lawriec/mcp-video-reader); [reel-relay README](https://github.com/siemd2/reel-relay); [media-context-mcp README](https://github.com/vishalguptax/media-context-mcp)

### Inferences
- Token arithmetic for 9:16 frames using the documented formula: 320×569 px ≈ 12×21 = 252 tokens; 512×910 px ≈ 19×33 = 627 tokens; 800×1422 px ≈ 29×51 = 1,479 tokens; a native 1080×1920 frame = 39×69 = 2,691 tokens (under the 4,784 cap on current models, so not downscaled).
- So 12 frames of a 30 s reel cost about 7.5k tokens at 512 px or about 18k at 800 px; 1 fps over a 60 s reel at 800 px would be about 89k tokens, and at native resolution about 161k. Sampling at 1 fps full-resolution is impractical; scene-change sampling at 512–800 px is the sensible operating point.
- Images stay in the conversation and are re-sent each turn, so a long chat analysing several reels accumulates image tokens and counts toward the more-than-20-images threshold; starting a fresh chat per reel (or per few reels) keeps this manageable.
- Byte-wise, 12 JPEG frames at 800 px/q70 are likely 60–150 KB each, which could exceed a 1 MB result in one call; requesting 5–8 frames per call, or 512 px frames, is safer. This is an estimate, not measured.
- Frames lose motion, cut rhythm and audio tone. Frame-based "watching" answers what is on screen and what is said; pacing has to be inferred from frame timestamps and the transcript.

### Gaps
- No official Anthropic figure was found for the maximum number of images, or bytes, a single MCP tool result may carry in Claude Desktop. The 1 MB figure is community-reported, and whether it is counted before or after base64 encoding is unknown.
- Whether the 20-images-per-message claude.ai limit applies to images arriving through tool results in Claude Desktop is not documented in the sources read.
- No measurement of real result sizes from any of the catalogued servers on a vertical reel was made.
