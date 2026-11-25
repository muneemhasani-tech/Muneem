# MRA Real Estate: Shorts editing plan (status 2026-11-11)

## Repos cloned (not yet built or run)
- `Adobe_Premiere_Pro_MCP` (hetpatel-11): about 283 tools, including `color_correct`, `create_caption_track`, `add_text_overlay`, `detect_silence` (needs ffmpeg), split/ripple delete. Needs a real Premiere Pro session. Its own KNOWN_ISSUES says only 43 tools were live-tested.
- `adb-mcp` (mikechambers): about 26 Premiere tools (import, sequence, markers, transitions, export, B&W/tint/blur). No captions or color-grade tools.
- Plan: use `Adobe_Premiere_Pro_MCP` as primary once Premiere is available.

## What is known about the MRA style (from thumbnails and metadata only)
- Long explainers (23-30s): sentence-style titles with a number or warning. They get the views (best: 1.4K).
- 3-5s clips: ALL-CAPS hook titles, text-over-footage.
- Look: dark navy "blueprint" palette, white and yellow bold type, yellow keyword highlight, hand-drawn sketch/arrow graphics, cut-out speaker with an outline.
- Talking head at a desk with a blue/purple room glow; a headline text box fixed at the top of the frame.
- NOT KNOWN YET: cut pace, caption font and animation, exact color grade, music, SFX, transitions, audio treatment. This needs footage.

## Blockers
1. YouTube blocks this cloud session ("confirm you're not a bot") for downloads, headless playback and embeds. No video or audio has been seen.
2. No Premiere Pro subscription yet; the MCP cannot run without it.
3. Running third-party install/build code (npm) was denied by the permission check; waiting for the user to allow it.

## Needed from the user
- 3-5 original Short files (mp4), plus raw footage for one test edit (Drive folder or upload).
- Permission rule for npm install/build, if they want the repo built here.

## Proposed pipeline once footage exists
1. Analyze: ffmpeg scene detection, silencedetect, Whisper transcript, frame grabs, color stats, so the style guide has measured values.
2. Rough cut: remove silences and filler, cut to the script.
3. Grade: match the measured MRA look (LUT or curves) with ffmpeg now, Lumetri via MCP later.
4. Captions: Bangla/English/Banglish, human-checked; highlighted keyword in yellow.
5. Hook text box + end card ("general information, not legal advice").
6. Export 9:16, 1080x1920. User approves before posting.
