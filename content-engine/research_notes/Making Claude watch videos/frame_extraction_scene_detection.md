# Frame extraction, scene detection and contact sheets for making Claude "watch" short vertical reels (state: 12 Nov 2026)

**How to read these notes.** Commands marked **[TESTED]** were run by the researcher on 12 Nov 2026 against a synthetic 1080x1920, 30 fps, 11.5 s clip with three hard cuts, using FFmpeg 6.1.1 (Linux), PySceneDetect 0.7.3 (via `uvx`), librosa 1.0.1 and opencv-python-headless. They were NOT run on Windows; the filter syntax is identical, but shell quoting differs (Windows notes are given separately and are flagged where unverified). Anything marked **[UNTESTED]** was not executed. All commands are written on one line with double-quoted filter strings, which is the form that works in Windows `cmd.exe` and PowerShell.

---

## 1. What frame sampling rate should be used for short, fast-cut video? What do video-native models do?

### Takeaway
The de-facto industry default is 1 fps (Gemini's fixed default; Simon Willison's plugin default), and Google's own docs admit 1 fps loses detail on fast action and quick scene changes. For a 20-60 s fast-cut reel, the evidence supports a hybrid: every cut point (scene detection) plus a fixed 2 fps floor, rather than 1 fps alone.

### Cited Findings
- Gemini "static" video processing "Extracts frames at a fixed rate (1 FPS)"; 258 tokens per frame by default, 66 tokens per frame at low media resolution; audio is 32 tokens per second; total is about 300 tokens/s (default) or about 100 tokens/s (low resolution) — [Google Gemini video understanding docs](https://aistudio.google.com/docs/video-understanding) (ai.google.dev/gemini-api/docs/video-understanding now 301-redirects here)
- Google's docs state "fast action sequences might lose detail due to the 1 FPS sampling rate" and that the default "may miss details in videos with rapid motion or quick scene changes"; a custom rate is set with an `fps` argument in the `processing` configuration object (e.g. `fps: 0.5`), and clipping uses `start_offset` / `end_offset`; timestamps are referenced as `MM:SS` — [Google Gemini video understanding docs](https://aistudio.google.com/docs/video-understanding)
- Simon Willison's `llm-video-frames` plugin (May 2025) uses ffmpeg to turn a video into JPEG frames at `fps` per second, default 1, with a `timestamps=1` option that burns the filename and timestamp into the bottom-right of each frame; examples use `?fps=2` and `?timestamps=1&fps=5` — [Simon Willison, llm-video-frames](https://simonwillison.net/2025/May/5/llm-video-frames/)
- Willison's measured costs on GPT-4.1 mini: 3 frames = 7,072 input tokens (about 0.31 cents); 14 frames at fps=5 with timestamps = 32,968 input tokens (about 1.34 cents), about 5.9 MB of base64 JPEG — [Simon Willison, llm-video-frames](https://simonwillison.net/2025/May/5/llm-video-frames/)
- A 2026 engineering overview gives the rule "match the frame rate to the shortest event that matters" — at 1 fps anything shorter than a second can fall between samples — and recommends uniform or query-aware sampling for continuous fixed-camera footage where cut detection would miss events — [Fora Soft, Video VLMs: frame sampling (31 May 2026)](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/video-vlms-frame-sampling-token-streaming-2026) (vendor blog; secondary source)
- The same overview reports research on key-clip selection ("From Frames to Clips", Zhang et al., arXiv:2510.02262) claiming gains of roughly 8-10 points over uniform sampling on long-video benchmarks, and cites VideoBrain (arXiv:2602.04094) and Generative Frame Sampler (arXiv:2503.09146) as adaptive-sampling work — [Fora Soft overview](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/video-vlms-frame-sampling-token-streaming-2026) (not verified against the papers themselves; these are long-video results)
- The same overview says Google added an "agentic" video mode on 1 Sept 2026 in which the model reads the transcript first, then loads only needed segments at the needed frame rate, with Google-reported savings of up to 88% tokens — [Fora Soft overview](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/video-vlms-frame-sampling-token-streaming-2026) (Google's own claim, relayed second-hand; not verified in Google's docs)
- A practitioner tool for Claude (claude-real-video / `crv`) reports that a 58-second clip at fixed 1 fps gives 58 frames, whereas scene-change selection plus pixel-difference dedup kept 26 frames; its design is scene-change `select` with a density floor (`--fps-floor`, default 1.0 s), a sliding dedup window (default 4 frames, keep if at least 8% of pixels changed), and a default cap of 150 frames — [DEV Community article by the tool author](https://dev.to/huangchihhungleo/your-llm-isnt-watching-the-video-its-reading-subtitles-2jjl); [mcp.directory write-up](https://mcp.directory/blog/claude-real-video-understanding-2026) (author-reported, single example, self-promotional)
- The same author states Claude does not accept video files, ChatGPT answers from YouTube subtitles, and Gemini samples at 1 fps — [DEV Community](https://dev.to/huangchihhungleo/your-llm-isnt-watching-the-video-its-reading-subtitles-2jjl). Consistent with Anthropic's vision docs listing only JPEG, PNG, GIF and WebP as supported image inputs ("Animations are unsupported, and only the first frame is used") — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)

### Inferences
- Short-form reels commonly have shots of about 1-3 s plus word-by-word captions that change several times per second. 1 fps will skip whole shots and most caption states. A 2 fps floor on a 60 s reel is 120 frames; 20-30 s reels give 40-60 frames — manageable for Claude if tiled (section 4).
- Recommended recipe for this use case (researcher's synthesis, not from a single source): (a) run cut detection to get the exact cut list and one frame per shot; (b) add a uniform 2 fps pass for caption/pacing coverage; (c) for the first 3 seconds (the hook), sample denser (4-5 fps) at higher resolution, because that is where layout and caption style matter most.
- Scene-only sampling is insufficient on its own: talking-head reels can have a single long shot in which captions, zoom punches and overlays change without any cut being detected.

### Gaps
- No peer-reviewed study was found that tests sampling rates specifically on sub-60-second fast-cut social reels; the academic sampling literature located is about long videos (minutes to hours).
- The primary papers (arXiv:2510.02262, 2602.04094, 2503.09146) were not opened; numbers come from a secondary vendor article.
- Could not confirm from Google's primary docs the "agentic mode" claim or whether low media resolution is now the default.

---

## 2. Exact FFmpeg commands (fixed fps, scene-change frames with timestamps, contact sheets with burned-in timestamps, 16 kHz audio)

### Takeaway
All four building blocks are single FFmpeg commands; they were verified on FFmpeg 6.1.1. The main Windows pitfalls are the drive-letter colon in `fontfile`, `%` doubling inside `.bat` files, and using `-fps_mode vfr` (not a constant frame rate) after `select`.

### Cited Findings

**Install on Windows**
- `winget install Gyan.FFmpeg` is the Windows install command listed by a current tool's docs — [mcp.directory, claude-real-video](https://mcp.directory/blog/claude-real-video-understanding-2026)

**A. Fixed-fps extraction with downscale [TESTED]** (2 fps, 720x1280 output; `-2` keeps aspect and even width; `-q:v 3` is high-quality JPEG)
```
mkdir frames
ffmpeg -hide_banner -i reel.mp4 -vf "fps=2,scale=-2:1280" -q:v 3 frames/f_%04d.jpg
```
Test result: 11.5 s clip gave 23 frames. Frame N (1-based) is at about (N-1)/2 seconds.

**B. Scene-change frames, with timestamps printed to the console via showinfo [TESTED]**
```
mkdir scenes
ffmpeg -hide_banner -i reel.mp4 -vf "select='gt(scene,0.3)',showinfo,scale=-2:1280" -fps_mode vfr -q:v 3 scenes/s_%03d.jpg
```
Test result: showinfo lines contained `pts_time:3`, `pts_time:5`, `pts_time:9` (the three true cuts). showinfo writes to stderr; on Windows capture with `2> scenes_log.txt`.

**C. Scene-change timestamps and scores written to a text file (no images) [TESTED]**
```
ffmpeg -hide_banner -i reel.mp4 -vf "select='gt(scene,0.3)',metadata=print:file=scenes.txt" -an -f null -
```
Test output of `scenes.txt`:
```
frame:0    pts:46080   pts_time:3
lavfi.scene_score=0.735033
frame:1    pts:76800   pts_time:5
lavfi.scene_score=0.615878
```

**D. Scene-change frames including the first frame, with the source frame number in the filename [TESTED]** (`select` on scene never emits frame 0, so add `eq(n,0)+`; `-frame_pts 1` names files by PTS, which after `select` equalled the source frame index in the test: `p_000000.jpg`, `p_000090.jpg`, `p_000150.jpg`, `p_000270.jpg` at 30 fps = 0 s, 3 s, 5 s, 9 s)
```
ffmpeg -hide_banner -i reel.mp4 -vf "select='eq(n,0)+gt(scene,0.3)',scale=-2:1280" -fps_mode vfr -frame_pts 1 -q:v 3 scenes/p_%06d.jpg
```

**E. Alternative cut detector `scdet` (prints score and time for each detected cut) [TESTED]**
```
ffmpeg -hide_banner -i reel.mp4 -vf "scdet=threshold=10" -an -f null -
```
Test output lines: `lavfi.scd.score: 28.712, lavfi.scd.time: 3` (and 5, 9).

**F. Single contact sheet, 1 fps, 4x3 grid, burned-in timestamps [TESTED]** (Linux font path as tested; Windows form below)
```
ffmpeg -hide_banner -i reel.mp4 -vf "fps=1,scale=360:640,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\:hms}':x=8:y=8:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6,tile=4x3:margin=8:padding=8:color=white" -frames:v 1 -update 1 -q:v 2 sheet.jpg
```
Test result: 1480x1952 JPEG; each tile showed a legible label `00:00:00.000` ... `00:00:11.000` in reading order (verified by viewing the image).

**G. Multiple contact sheets (as many as needed), 2 fps, 4x2 per sheet [TESTED]** (23 frames gave 3 sheets; the last, partly filled sheet is still written)
```
ffmpeg -hide_banner -i reel.mp4 -vf "fps=2,scale=360:640,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\:hms}':x=8:y=8:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6,tile=4x2:margin=8:padding=8" -fps_mode vfr -q:v 2 sheet_%02d.jpg
```

**H. "Cut sheet": one tile per detected shot, timestamped [TESTED]**
```
ffmpeg -hide_banner -i reel.mp4 -vf "select='eq(n,0)+gt(scene,0.3)',scale=360:640,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\:hms}':x=8:y=8:fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=4x3" -frames:v 1 -update 1 cuts.jpg
```

**I. Caption-band strip: crop the region where captions sit, keep it at high resolution, stack vertically [TESTED]** (crops a band 35% of frame height starting at 55% down — adjust to the reel's caption position; 2 fps; 2 columns x 8 rows of 720 px-wide strips; test output 1440x3584)
```
ffmpeg -hide_banner -i reel.mp4 -vf "fps=2,crop=iw:ih*0.35:0:ih*0.55,scale=720:-2,tile=2x8" -frames:v 1 -update 1 capstrip.jpg
```
(Add the same `drawtext` clause before `tile` to timestamp each strip. Use `-fps_mode vfr` and `capstrip_%02d.jpg` instead of `-frames:v 1 -update 1` for multiple sheets.)

**J. Audio to 16 kHz mono 16-bit WAV for Whisper-style transcription [TESTED]** (ffprobe confirmed `pcm_s16le,16000,1`)
```
ffmpeg -hide_banner -i reel.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
```

**Windows font-path quoting (from FFmpeg user reports; NOT tested by the researcher)**
- The colon is an option separator in filter syntax, so the drive colon must be escaped; a Windows 10 user reports that escaping the colon, using forward slashes and wrapping the path in single quotes works: `fontfile='C\:/WINDOWS/fonts/lucon.ttf'` — [FFmpeg-user mailing list / VideoHelp threads via search](https://forum.videohelp.com/showthread.php?p=2586524); [FFmpeg-user list](https://ffmpeg.org/pipermail/ffmpeg-user/2018-February/038991.html)
- A backslash form also reported to work: `fontfile='C\:\\Windows\\Fonts\\arial.ttf'` (escape `:` as `\:` and `\` as `\\`); in batch/scripted contexts users report needing extra levels of escaping, and sources disagree on how many — [Stack Overflow mirror: drawtext could not load font](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/8103808/ffmpeg-drawtext-could-not-load-fontface-from-file); [FFmpeg-user list](https://ffmpeg.org/pipermail/ffmpeg-user/2020-December/051193.html)
- Resulting Windows form of command F **[UNTESTED on Windows]**:
```
ffmpeg -hide_banner -i reel.mp4 -vf "fps=1,scale=360:640,drawtext=fontfile='C\:/Windows/Fonts/arialbd.ttf':text='%{pts\:hms}':x=8:y=8:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6,tile=4x3:margin=8:padding=8:color=white" -frames:v 1 -update 1 -q:v 2 sheet.jpg
```

### Inferences
- Simplest way to sidestep the Windows font-path problem entirely: copy a font into the working folder (`copy C:\Windows\Fonts\arialbd.ttf .`) and use `fontfile=arialbd.ttf` — a relative path has no colon or backslash to escape. (Researcher's suggestion based on the escaping rules above; not tested on Windows.)
- Inside a `.bat`/`.cmd` file every literal `%` must be doubled: `%%{pts\:hms}` and `f_%%04d.jpg`. Typed interactively in `cmd.exe` or in PowerShell a single `%` is correct. (Standard cmd.exe behaviour; not from a fetched source and not tested here.)
- Always wrap the whole `-vf` value in double quotes and the `select` expression in single quotes so its comma is not parsed as a filter separator; without the inner quotes write `gt(scene\,0.3)`.
- `-fps_mode vfr` is the current spelling (tested on 6.1.1); older tutorials use `-vsync vfr`, which is deprecated. Without it, FFmpeg duplicates frames to fill the gaps left by `select`.
- Threshold guidance: 0.3 caught all hard cuts between very different synthetic shots (scores 0.62-0.74). Real reels with jump cuts on the same talking head produce much lower scores, so expect to lower to about 0.1-0.2 and dedupe, or use PySceneDetect (section 3) which is purpose-built. `scdet` uses a 0-100 scale (default threshold 10 per the tested command's behaviour).
- The `hms` timestamp is 12 characters wide (`00:00:07.500`). For reels under 60 s it is fine at fontsize 28 on a 360 px tile (verified visually); keep the label in a corner that captions do not occupy (top-left usually; captions are typically centre/lower-third).
- Because the label is drawn before `tile`, the font size is relative to the tile, not the sheet; scale `fontsize` to about 7-8% of tile width.

### Gaps
- The official FFmpeg filter documentation page (ffmpeg.org/ffmpeg-filters.html) could not be read past the audio-filter sections (page is about 590k characters); option semantics above are verified by execution on FFmpeg 6.1.1 rather than quoted from the docs. The installed Windows build will likely be FFmpeg 7.x/8.x — no behaviour change is expected for these filters but that was not verified.
- No command was run on Windows 10; the font-path form is from user reports.
- `freezedetect` (for held/static frames) was attempted but produced no confirmed output in testing; not recommended here without further testing.

---

## 3. PySceneDetect: version, install, commands, average shot length, and which detector suits fast-cut reels

### Takeaway
PySceneDetect 0.7.3 (released 8 Nov 2026) is current; `uvx scenedetect` runs it with no install. `detect-adaptive` is the best default for short-form content (highest F1 on the short-form AutoShot benchmark), and the tool prints average shot length directly; lower `--min-scene-len` below its 0.6 s default for fast-cut reels.

### Cited Findings
- Latest version is 0.7.3, released Nov 8, 2026; requires Python >= 3.10; install with `pip install scenedetect` (upgrade: `pip install --upgrade scenedetect`); a `scenedetect-headless` package exists for servers (install only one of the two) — [PyPI: scenedetect](https://pypi.org/project/scenedetect/)
- Python API quick start: `from scenedetect import detect, AdaptiveDetector` then `scene_list = detect('my_video.mp4', AdaptiveDetector())` — [PyPI: scenedetect](https://pypi.org/project/scenedetect/)
- Global options (must come before commands): `-i/--input`, `-o/--output`, `-s/--stats` (per-frame metrics CSV), `-m/--min-scene-len` (default 0.6s), `-d/--downscale`, `-fs/--frame-skip`, `-b/--backend` (default opencv) — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- `detect-adaptive`: "Find fast cuts using diffs in HSL colorspace (rolling average)"; two-pass; the rolling average "can help mitigate false detections in situations such as camera movement"; defaults `-t/--threshold 3.0`, `-c/--min-content-val 15.0`, `-f/--frame-window 2` — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- `detect-content`: "Find fast cuts using differences in HSL (filtered)"; per-frame score 0-255; default threshold 27.0. Other detectors: `detect-hash` (0.35), `detect-hist` (0.2), `detect-threshold` (12.0, for fades to/from black) — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- `list-scenes` writes `$VIDEO_NAME-Scenes.csv`; `-s/--skip-cuts` omits the first-row cut list (RFC 4180-compliant CSV); `-n/--no-output-file` only prints. `save-images` defaults: `-n/--num-images 3`, JPEG quality 95, filename `$VIDEO_NAME-Scene-$SCENE_NUMBER-$IMAGE_NUMBER`, resize with `-s/--scale`, `-H/--height`, `-W/--width`; `save-html` builds an HTML report from the preceding `save-images` — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- Benchmarks at default settings on AutoShot (short-form web/user-generated clips, hard cuts): AdaptiveDetector F1 73.86 (recall 70.59, precision 77.46); ContentDetector F1 69.26; HashDetector 64.84; HistogramDetector 57.82. On BBC Planet Earth: Adaptive 91.59 vs Content 86.69. On ClipShots hard cuts they tie (55.75 vs 55.84). For fades, HistogramDetector is best (F1 75.33) and Adaptive worst of the main four (23.96) — [PySceneDetect benchmarks](https://www.scenedetect.com/benchmarks/)
- Tuned-best parameters by mean hard-cut F1 across the three datasets: Adaptive `adaptive_threshold=3.5, window_width=3, min_scene_len=0.6s` (F1 76.3); Content `threshold=31` (F1 73.4). The page notes its default-setting tables predate v0.7.2 and will be regenerated — [PySceneDetect benchmarks](https://www.scenedetect.com/benchmarks/)

**Commands [TESTED with `uvx scenedetect`, v0.7.3]**

Run without installing (needs `uv`), or replace `uvx scenedetect` with `scenedetect` after `pip install scenedetect`:
```
uvx scenedetect version
```
Detect cuts, write stats CSV + scene CSV, save one 720 px-wide image per scene, all into folder `sd`:
```
uvx scenedetect -i reel.mp4 -o sd -s reel.stats.csv detect-adaptive list-scenes save-images -n 1 -W 720
```
Fast-cut variant (allow shots as short as 0.3 s; middle-of-shot plus first/last frames = 3 images per scene):
```
uvx scenedetect -i reel.mp4 -o sd -m 0.3s detect-adaptive list-scenes save-images -n 3 -W 720
```
Print scene list only, content detector:
```
uvx scenedetect -i reel.mp4 -m 0.3s detect-content -t 27 list-scenes -n
```
- Test console output included the line `Detected 4 scenes, average shot length 2.9 seconds.` and a `Comma-separated timecode list: 00:00:03.000,00:00:05.000,00:00:09.000` — i.e. average shot length is printed by the tool itself (researcher's test run, PySceneDetect 0.7.3)
- Test `reel-Scenes.csv` content: first row `Timecode List:,00:00:03.000,00:00:05.000,00:00:09.000`, then header `Scene Number,Start Frame,Start Timecode,Start Time (seconds),End Frame,End Timecode,End Time (seconds),Length (frames),Length (timecode),Length (seconds)` (researcher's test run)
- Test stats CSV columns: `Frame Number,Timecode,adaptive_ratio (w=2),content_val,delta_edges,delta_hue,delta_lum,delta_sat` (researcher's test run)
- Speed on CPU: 345 frames of 1080x1920 processed in 1.2 s (about 281 fps) in a Linux sandbox (researcher's test run; indicates a 60 s reel takes seconds on an i7 without GPU, though exact Windows speed was not measured)

**Average shot length and pacing stats from the CSV [TESTED]** — save as `asl.py`, run `python asl.py sd\reel-Scenes.csv`:
```python
import csv, sys, statistics as st
rows = list(csv.reader(open(sys.argv[1], encoding="utf-8")))
hdr = next(i for i, r in enumerate(rows) if r and r[0] == "Scene Number")
L = [float(r[rows[hdr].index("Length (seconds)")]) for r in rows[hdr + 1:] if r]
tot = sum(L)
print(f"shots={len(L)} cuts={len(L)-1} duration={tot:.2f}s ASL={tot/len(L):.2f}s median={st.median(L):.2f}s min={min(L):.2f}s max={max(L):.2f}s cuts_per_min={(len(L)-1)/tot*60:.1f}")
```
Test output: `shots=4 cuts=3 duration=11.50s ASL=2.88s median=2.75s min=2.00s max=4.00s cuts_per_min=15.7`

### Inferences
- For fast-cut reels use `detect-adaptive` with `-m 0.3s` (or lower): the 0.6 s default minimum scene length will merge rapid B-roll montage shots (anything under 18 frames at 30 fps).
- Both hard-cut detectors will under-detect jump cuts on the same talking head (small content change) and will not detect zoom punches or caption changes; use the stats CSV (`content_val` peaks) to tune, and pair with the fixed-fps pass.
- AutoShot F1 of about 74% at defaults means roughly a quarter of cuts are missed or spurious on short-form content; treat cut counts as approximate and have Claude sanity-check against the 2 fps contact sheet.
- If reels use dissolves/fades between B-roll, run a second pass with `detect-hist` (best on fades in the benchmark).

### Gaps
- The docs page did not list the filename macros beyond `$VIDEO_NAME`, `$SCENE_NUMBER`, `$IMAGE_NUMBER`, `$FRAME_NUMBER`; whether a timecode macro exists for `save-images` was not confirmed.
- No benchmark specific to vertical social reels with burned-in animated captions (animated captions may trigger false cuts; unmeasured).
- Neural shot-boundary detectors (e.g. TransNetV2, AutoShot) were not researched for CPU-only Windows feasibility.

---

## 4. Contact sheet vs individual frames for Claude; tile resolution for captions; Claude's image downscaling and its effect on grid size; published grid experiments

### Takeaway
On Claude, token cost is proportional to pixels (28x28 px patches), so a contact sheet does not save tokens versus the same frames sent separately at the same tile size — its benefits are fewer image slots, explicit temporal ordering and in-image timestamps. On current models (Claude 4.7 and later) a sheet can be up to 2,576 px on the long edge and 4,784 visual tokens (about 3.75 MP), which fits roughly 8 vertical tiles at about 504x896 or 15-18 tiles at about 340-365 px wide; older/standard-tier models cap at 1,568 px and 1,568 tokens (about 1.2 MP), i.e. only about 8 tiles at 288x512.

### Cited Findings
- "Claude processes images in patches instead of pixels. Each patch is a 28×28-pixel block of the image, referred to as a visual token. An image, therefore, costs ⌈width / 28⌉ × ⌈height / 28⌉ visual tokens." — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Resolution tiers: High-resolution = "Claude 4.7 and later models", max long edge 2,576 px, max 4,784 visual tokens; Standard = all other models, max long edge 1,568 px, max 1,568 visual tokens. Larger images are downscaled to the largest size that fits, preserving aspect ratio. High-resolution is automatic (no beta header) — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Doc examples: 1920x1080 is downsized to 1456x819 (1,560 tokens) on standard but not resized on high-res (2,691 tokens); 3840x2160 becomes 2576x1449 (4,784 tokens) on high-res — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- "High-resolution images can use up to roughly three times more visual tokens than the same image on a standard-tier model"; Anthropic advises downsampling before sending if the extra fidelity is not needed — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Limits: up to 20 images per message on claude.ai; 100 per API request for 200k-context models, 600 for other models; max 8000x8000 px per image; if a request has more than 20 images a stricter per-image dimension limit applies (keep each dimension at or below 3,000 px to be safe); 10 MB per image (base64) on the Claude API and claude.ai — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Text guidance: "If the image contains important text, make sure it's legible and not too small"; resizing "might ... make text less legible. Consider pre-resizing your images, cropping them, or both"; "heavy JPEG compression can make text difficult to read" — [Anthropic vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- IG-VLM ("An Image Grid Can Be Worth a Video", arXiv:2403.18406): uniformly samples 6 frames into a 3x2 grid and feeds one image to a VLM (GPT-4V, LLaVA v1.6 7B/13B/34B, CogAgent); claims to surpass prior methods on 9 of 10 zero-shot video-QA benchmarks — [arXiv abstract](https://arxiv.org/abs/2403.18406); [paper HTML](https://arxiv.org/html/2403.18406v1)
- IG-VLM ablations: near-square grids beat single-row and single-column layouts in all six tested combinations; row-major (left-to-right, then down) ordering beat column-major on average, and both beat random; of N = 4, 6, 9, 12, 16, 20 frames, N = 6 was best on ActivityNet-QA and NExT-QA; GPT-4V on a 20% ActivityNet-QA validation subset rose from 26.3 (single frame) to 54.7 (grid) — [paper HTML](https://arxiv.org/html/2403.18406v1)
- IG-VLM limitations noted by the authors: resizing/cropping by the VLM's preprocessing reduces per-frame spatial detail; "Detail Orientation" scores lagged the best prior models — [paper HTML](https://arxiv.org/html/2403.18406v1)
- A 2026 AACL paper is reported (via search summary) to find that a single 2x8 image grid built with simple shot-transition detection can approximate full-video annotation for short clips — [ACL Anthology 2026.aacl-long.29](https://aclanthology.org/2026.aacl-long.29.pdf) (not opened; claim from search snippet only)
- Practitioner tooling for Claude uses the same approach: sample frames, tile into timestamped contact sheets, have Claude read the sheets; one guide notes "contact sheets trade resolution for coverage, so fine detail needs a zoomed re-sample"; claude-real-video's `--grid` packs keyframes into 3x3 sheets ("9x fewer images") — [skills.sh: oaustegard parsing-video skill (via search)](https://www.skills.sh/oaustegard/claude-skills/parsing-video); [DEV Community](https://dev.to/huangchihhungleo/your-llm-isnt-watching-the-video-its-reading-subtitles-2jjl)
- A 2023 OpenAI community thread describes feeding a frame grid plus a Whisper transcript to GPT-4 Vision — [OpenAI community: Reading videos with GPT4V](https://community.openai.com/t/reading-videos-with-gpt4v/523568) (via search summary)

### Inferences
(All arithmetic below is the researcher's, derived from Anthropic's published patch formula and tier limits; it is not published by Anthropic.)
- Pixel budget per image: high-res tier 4,784 x 784 px² = about 3.75 MP; standard tier 1,568 x 784 = about 1.23 MP. For N vertical 9:16 tiles filling the budget, max tile width is about sqrt(budget x 9 / (16 x N)):

| Tiles per sheet | High-res tier (Claude 4.7+): max tile | Standard tier: max tile |
|---|---|---|
| 6 (3x2) | about 590x1050 | about 340x600 |
| 8 (4x2) | about 510x910 | about 290x520 |
| 12 (4x3) | about 420x745 | about 240x425 |
| 15 (5x3) | about 375x665 | about 215x380 |
| 18 (6x3) | about 340x605 | about 195x350 |
| 24 (6x4) | about 295x525 | about 170x300 |

- Concrete sheets that fit the high-res tier without being resized (checked with the patch formula): 4x2 of 504x896 = 2016x1792 = 4,608 tokens; 5x3 of 364x648 = 1820x1944 = 4,550 tokens; 6x3 of 336x598 = 2016x1794 = 4,680 tokens; 4x3 of 392x696 = 1568x2088 = 4,200 tokens. The tested 4x3 sheet of 360x640 tiles with margins (1480x1952) = 3,710 tokens, fits high-res; on a standard-tier model it would be downscaled by about 0.65 to roughly 234x416 per tile. Margins/padding consume budget; drop them (`tile=5x3`) when at the limit.
- Individual frame cost for comparison: 1080x1920 = 2,691 tokens (high-res; downsized to about 819x1456 / about 1,560 tokens on standard); 720x1280 = 1,196; 540x960 = 700; 360x640 = 299.
- Token cost is therefore roughly constant per pixel whichever packaging is used: 120 frames (60 s at 2 fps) at 360x640 is about 36k tokens as single images or about 36k as eight 5x3 sheets. Sheets win on (a) claude.ai's 20-images-per-message cap, (b) fewer file reads in agentic tools, (c) the model seeing sequence and pacing at a glance, (d) timestamps travelling with the pixels. Individual frames win when detail matters, because a sheet over the cap is silently downscaled.
- Caption legibility: no published minimum text height for Claude was found. Reasoning from the 28 px patch size and Anthropic's "not too small" guidance: reel captions are large (often 5-8% of frame width per character line height, i.e. roughly 55-90 px tall at 1080 wide — researcher's estimate, unsourced), so at a 360 px-wide tile they are about 18-30 px tall — typically readable for bold Latin text, marginal for Bangla, whose conjuncts and vowel signs (matra) need more pixels. Practical rule to validate by experiment: use at least about 500 px-wide tiles (4x2 on high-res tier) when Bangla caption text must be read; use about 340-365 px tiles (5x3 / 6x3) for layout, pacing and B-roll overview only; and add a separate high-resolution caption-band strip (command I in section 2) or a handful of full 720x1280 frames for caption style/typography.
- IG-VLM's "6 frames is best" result reflects 2024-era models with low input resolution (LLaVA 1.6, GPT-4V); it should not be read as a limit for Claude's 3.75 MP tier, but its layout findings (near-square grid, row-major order) are a reasonable default — the tested FFmpeg `tile` filter fills row-major.
- Suggested bundle for a 60 s reel on a high-res Claude model (about 45-55k image tokens): 8 overview sheets at 5x3 / 364x648 from the 2 fps pass (about 36k), 1 cut sheet (one tile per shot, about 4.5k), 2-3 caption strips, plus 3-4 full-res 720x1280 hook frames (about 1.2k each), the scene CSV, pacing stats and the transcript as text.

### Gaps
- No published, controlled experiment was found comparing contact sheets versus individual frames on Claude specifically, nor any measurement of the minimum tile size at which Claude reads Bangla burned-in captions. This needs a local A/B test (same reel, tiles at 300/360/500 px, compare transcribed captions against ground truth).
- The exact resize/pad rule lives in Anthropic's separate "vision-coordinates" page, which was not fetched; figures above use the limits and examples in the main vision page.
- Whether claude.ai / Claude Code apply additional client-side downscaling before the API tier limits was not verified.
- The 2026 AACL 2x8-grid paper was not read; details unverified.

---

## 5. Tools for measuring pacing and edit style objectively (cuts, ASL, zoom/motion, loudness, beats, caption OCR for Bangla)

### Takeaway
Cut count and average shot length come straight from PySceneDetect; loudness/silence from FFmpeg `ebur128` / `silencedetect`; beats and onsets from librosa; zoom and motion from a short OpenCV optical-flow script — all CPU-only and free. Bangla caption OCR is the weak link: Tesseract (`ben`), EasyOCR (`bn`) and PaddleOCR PP-OCRv5 all support Bengali, but published accuracy figures are for scanned documents (about 80% word accuracy), not stylised video captions, so a vision LLM reading high-resolution caption crops is likely the more reliable reader.

### Cited Findings
- PySceneDetect prints cut list and average shot length and writes per-scene lengths to CSV (see section 3) — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- On 216 real-world Bengali document images, Tesseract reached 88.54% character-level and 79.99% word-level accuracy; EasyOCR reached 90.98% character-level and 78.06% word-level; figures are from the document categories where OCR does best — [BRAC University thesis (via search summary)](https://dspace.bracu.ac.bd/bitstreams/ba79fe28-fbb3-41bb-8f7b-53990b1f892d/download) (not opened directly)
- Tesseract's language table lists Bengali with code `ben` (script model code `beng`), supported in all listed data sets (tessdata, tessdata_best, tessdata_fast) — [Tesseract docs: data files](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html)
- EasyOCR lists Bengali with code `bn`; "Languages sharing the same written script ... can be used together. English can be combined with any language." — [EasyOCR language list](https://www.jaided.ai/easyocr/)
- EasyOCR latest release is 1.7.2 (24 Sept 2024); install `pip install easyocr` (on Windows install torch/torchvision first from pytorch.org); `gpu=False` for CPU-only — [EasyOCR GitHub](https://github.com/JaidedAI/EasyOCR)
- PaddleOCR's PP-OCRv5 multilingual recognition expanded coverage to include Bengali; language is selected with the `lang` parameter (e.g. `PaddleOCR(lang="fr")`); PaddleOCR 3.x changed its interface relative to 2.x — [PaddleOCR PP-OCRv5 multilingual docs](https://www.paddleocr.ai/v3.5.0/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html) (via search summary; the Bengali code itself was not shown)
- A PaddleOCR-vs-Tesseract comparison site withdrew earlier accuracy claims for lack of linked inputs and recommends testing each engine on your own images — [codesota: paddleocr vs tesseract](https://www.codesota.com/ocr/paddleocr-vs-tesseract) (via search summary)

**Loudness (EBU R128) summary [TESTED]** — prints integrated loudness (LUFS), loudness range and true peak at the end of stderr:
```
ffmpeg -hide_banner -nostats -i reel.mp4 -af "ebur128=peak=true" -vn -f null -
```
**Per-100 ms momentary loudness curve to a text file [TESTED]** (lines of `pts_time:` followed by `lavfi.r128.M=<LUFS>`; shows energy peaks, drops and music swells over time):
```
ffmpeg -hide_banner -i reel.mp4 -af "ebur128=metadata=1,ametadata=print:key=lavfi.r128.M:file=loud.txt" -vn -f null -
```
**Pauses / silence gaps [TESTED: runs; the test tone had no silence so no events printed]** (prints `silence_start`, `silence_end`, `silence_duration` to stderr; useful for speech pacing and dead air):
```
ffmpeg -hide_banner -i reel.mp4 -af "silencedetect=noise=-30dB:d=0.3" -vn -f null -
```
**Beat / onset times with librosa [TESTED, librosa 1.0.1; a 120 BPM click track was measured at 117.5 BPM with beats every about 0.5 s]** — `pip install librosa`, save as `beats.py`, run `python beats.py audio.wav`:
```python
import sys, librosa, numpy as np
y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
print("tempo_bpm", float(np.atleast_1d(tempo)[0]))
print("beat_times", [round(float(t), 2) for t in librosa.frames_to_time(beats, sr=sr)])
print("onset_times", [round(float(t), 2) for t in onsets])
```
**Motion and zoom per 0.2 s via dense optical flow [TESTED: runs on CPU and prints values; not validated against labelled zooms]** — `pip install opencv-python numpy`, save as `motion.py`, run `python motion.py reel.mp4 > motion.csv`:
```python
import sys, cv2, numpy as np
cap = cv2.VideoCapture(sys.argv[1]); fps = cap.get(cv2.CAP_PROP_FPS); step = max(1, round(fps / 5))  # ~5 samples/s
prev = None; i = 0
print("t,mean_flow_px,zoom_div")
while True:
    ok, f = cap.read()
    if not ok: break
    if i % step == 0:
        g = cv2.cvtColor(cv2.resize(f, (180, 320)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.linalg.norm(fl, axis=2).mean()
            div = (np.gradient(fl[..., 0], axis=1) + np.gradient(fl[..., 1], axis=0)).mean()  # >0 zoom-in, <0 zoom-out
            print(f"{i / fps:.2f},{mag:.3f},{div:.4f}")
        prev = g
    i += 1
```
**Tesseract and EasyOCR on a caption crop [UNTESTED]** (Tesseract needs `ben.traineddata` in its tessdata folder; `--psm 6` = single uniform block, `--psm 7` = single line):
```
tesseract caption_crop.png stdout -l ben+eng --psm 6
```
```python
import easyocr
reader = easyocr.Reader(['bn', 'en'], gpu=False)
for box, text, conf in reader.readtext('caption_crop.png'): print(round(conf, 2), text)
```

### Inferences
- Cut-on-beat analysis: compare the PySceneDetect cut timecodes with librosa `beat_times`/`onset_times`; the share of cuts within about ±0.1 s of a beat is an objective "edited to the music" score. (Researcher's suggestion; with speech-heavy reels beat tracking is unreliable, so onsets are the safer signal.)
- In the optical-flow script, sustained positive `zoom_div` over several samples suggests a zoom-in/push, negative a zoom-out; a one-sample spike in `mean_flow_px` coincides with a cut (ignore rows near cut times). Thresholds must be calibrated on real reels; the divergence heuristic is the researcher's and unvalidated.
- Caption cadence can be measured without OCR: run PySceneDetect or `select='gt(scene,0.05)'` on the cropped caption band only (prepend `crop=iw:ih*0.35:0:ih*0.55,`) so that each change in the band approximates a caption change; changes per second approximates words-per-caption cadence. (Researcher's suggestion; untested on real captions.)
- Stylised reel captions (heavy stroke, drop shadow, highlight colours, emoji, mixed Bangla + Banglish in Latin script, animated scale) violate the clean-document conditions behind the roughly 80% word-accuracy figures, so classical OCR will do worse; expect it to be useful for locating text regions and detecting change timing rather than for accurate transcription. For reading the text, send Claude a high-resolution caption-band strip and cross-check with the audio transcript.
- Banglish (Bangla in Latin letters) is read by the English models; `ben+eng` / `['bn','en']` covers both scripts.

### Gaps
- No source was found that measures Tesseract, EasyOCR or PaddleOCR accuracy on stylised Bangla video captions; the only figures are for document images. This must be benchmarked locally.
- PaddleOCR's exact Bengali `lang` code and CPU-only Windows install steps were not confirmed (likely `bn`, unverified).
- Tesseract Windows installer details (e.g. the UB Mannheim build and where to drop `ben.traineddata`) and the tessdata_best vs tessdata_fast trade-off were not confirmed from a fetched source.
- librosa's official `beat_track` documentation page returned 404 at the URL tried; the snippet was verified by running it on librosa 1.0.1 rather than against docs.
- No free tool was found that directly classifies edit techniques (zoom punch, whip pan, speed ramp); optical-flow heuristics are the fallback.

---

## 6. Ready-made open-source "video to LLM-ready bundle" tools that run on Windows

### Takeaway
Several free tools already do most of this: Simon Willison's `llm-video-frames` (fps frames with timestamp overlay), `claude-real-video`/`crv` (scene-change frames, dedup, 3x3 grids, Whisper transcript, manifest), `vcsi` (classic contact sheets) and PySceneDetect's `save-images`/`save-html`. None is tuned for 9:16 reels with Bangla captions, so a small custom FFmpeg + PySceneDetect script remains the most controllable option.

### Cited Findings
- `llm-video-frames` 0.1 (Simon Willison, May 2025): a fragment-loader plugin for the `llm` CLI; needs ffmpeg on PATH; usage `llm -f video-frames:video.mp4 'describe the key scenes in this video' -m gpt-4.1-mini`, `llm -f 'video-frames:video.mp4?fps=2' 'summarize this video'`, `llm -f 'video-frames:cleo.mp4?timestamps=1&fps=5' 'key moments, include timestamps'`; sends individual JPEG frames, not grids — [Simon Willison](https://simonwillison.net/2025/May/5/llm-video-frames/)
- `claude-real-video` (`crv`), MIT, Python: `pip install claude-real-video`, transcription extra `pip install "claude-real-video[whisper]"`; usage `crv "https://www.youtube.com/watch?v=..." --grid`; outputs `crv-out/frames/`, `transcript.txt`, `MANIFEST.txt` (frame timestamps aligned with transcript) and `grids/`; options include `--fps-floor` (default 1.0 s), `--adaptive`, `--text-anchors`, `--dedup-window` (4), `--dedup-threshold` (8), `--max-frames` (150), `--whisper-model` (default base, about 139 MB download), `--report`; processing is local via ffmpeg and faster-whisper; ships a Claude Code skill; Windows ffmpeg install listed as `winget install Gyan.FFmpeg` — [mcp.directory write-up](https://mcp.directory/blog/claude-real-video-understanding-2026); [DEV Community (author)](https://dev.to/huangchihhungleo/your-llm-isnt-watching-the-video-its-reading-subtitles-2jjl); repo: github.com/HUANGCHIHHUNGLeo/claude-real-video
- The crv author acknowledges that stills lose motion, and a Hacker News commenter objected that Claude "will just burn tokens" with this approach — [mcp.directory write-up](https://mcp.directory/blog/claude-real-video-understanding-2026); [DEV Community](https://dev.to/huangchihhungleo/your-llm-isnt-watching-the-video-its-reading-subtitles-2jjl)
- `vcsi` (video contact sheet creator, Python CLI): `pip install vcsi` or `uv tool install vcsi`; needs ffmpeg/ffprobe on PATH; works on Windows with ffmpeg on PATH; options `-g/--grid` (e.g. 4x4), `-w/--width` (default 1500), `-t/--show-timestamp`, `-s/--num-samples`, `-m/--manual` (comma-separated timestamps), `--interval`, `--start-delay-percent` (default 7), `--end-delay-percent`, `--metadata-position top|bottom|hidden`, `-S/--actual-size`; README example `vcsi video.mp4 -t -w 830 -g 4x4 ... -o output.png` — [vcsi GitHub](https://github.com/amietn/vcsi)
- PySceneDetect itself produces a per-scene image set and an HTML report (`save-images`, `save-html`) — [PySceneDetect CLI docs](https://www.scenedetect.com/docs/latest/cli.html)
- Other tools surfaced but not examined: a "parsing-video" Claude skill (oaustegard) that tiles evenly sampled frames into timestamped contact sheets; `vid2llm`; `video2flow`; Microsoft GenAIScript's video support; "Frame Array" — [skills.sh parsing-video](https://www.skills.sh/oaustegard/claude-skills/parsing-video); [vid2llm GitHub](https://github.com/leozitogs/vid2llm); [GenAIScript blog](https://microsoft.github.io/genaiscript/blog/video); [DEV: video2flow](https://dev.to/massiron/extract-video-frames-for-llm-vision-pipelines-with-video2flow-4a00) (listed from search results only)

### Inferences
- For a reel workflow, a suggested `vcsi` invocation is `vcsi reel.mp4 -t -g 5x3 -w 1820 --start-delay-percent 0 --end-delay-percent 0 --metadata-position hidden -o reel_sheet.jpg` (composed from documented options; UNTESTED). The default 7% start delay must be zeroed, otherwise the hook (first seconds) is skipped — a critical default to override for short-form analysis.
- `crv`'s defaults (1 s floor, 3x3 grid, dedup) are tuned to save tokens on longer YouTube videos; for 20-60 s reels where pacing is the object of study, dedup removes exactly the repetition information (how long a shot is held) that is wanted, so keep a uniform-fps sheet alongside.
- A custom pipeline of five commands — PySceneDetect (cuts + CSV + per-shot images), FFmpeg 2 fps sheets, caption strip, 16 kHz WAV, loudness/beat scripts — covers everything these tools do with full control over 9:16 tile sizes and Claude's resolution tiers.

### Gaps
- None of the ready-made tools were installed or run by the researcher; Windows compatibility for `crv` is implied by its docs (winget command) but not explicitly claimed or verified.
- `vcsi`'s current version/release date and maintenance status could not be confirmed (its GitHub releases section is empty).
- `video2x` named in the brief is a video upscaler rather than a contact-sheet tool; it was not researched. No dedicated "reel analysis" bundle tool for vertical short-form video was found.
- Popularity/maintenance (stars, last commit) of the smaller tools was not verified beyond author claims (crv: "500+ GitHub stars" per its author).
