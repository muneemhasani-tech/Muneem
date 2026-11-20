# Claude native video-input support (state as of 12 Nov 2026)

Research date: 2026-11-12. Primary sources are Anthropic's own docs (platform.claude.com, support.claude.com) fetched live on that date. Secondary sources are dated individually. Nothing here was tested hands-on in a Claude Desktop session; where a hands-on test is the only way to settle a point, it is listed under Gaps.

## 1. Does any current Claude model or product accept video files (mp4/mov) directly?

### Takeaway
No. As of November 2026, no Anthropic doc lists video as an input type for the Claude apps, the Messages API, or the Files API; the documented visual input is still images (JPEG/PNG/GIF/WebP) and PDFs. Anthropic's docs do not contain an explicit "video is not supported" sentence. The evidence is absence from every supported-types list plus the statement that animated images are reduced to their first frame.

### Cited Findings
- The vision guide lists only four image formats: "Claude supports JPEG, PNG, GIF, and WebP images (`image/jpeg`, `image/png`, `image/gif`, `image/webp`). Animations are unsupported, and only the first frame is used." No video MIME type appears anywhere on the page. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- The vision guide's supported-model list runs through the newest models (Claude Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5), so the image-only limits apply to the current generation, not just older models. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- The Files API maps file types to content blocks as: PDF -> `document`; plain text -> `document`; images (jpeg/png/gif/webp) -> `image`; "Datasets, others" -> `container_upload` (code execution sandbox only). There is no video or audio content block. — [Anthropic Files API docs](https://platform.claude.com/docs/en/build-with-claude/files)
- The Files API accepts any file up to 500 MB (1 TB per organization) and upload/download/list operations are free, so an mp4 can be *stored*, but the only place it can be referenced is a `container_upload` block for the code execution tool, not as model input. — [Anthropic Files API docs](https://platform.claude.com/docs/en/build-with-claude/files)
- The claude.ai help article on uploads (last updated July 23, 2026) lists documents (PDF, DOCX, CSV, TXT, HTML, ODT, RTF, EPUB, JSON, XLSX) and images (JPEG, PNG, GIF, WebP). It does not mention MP4, MOV, MP3, or any audio/video type. — [Claude Help Center: What kinds of documents can I upload](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- Secondary confirmation (updated Sept 26, 2026; vendor blog, no first-hand testing): "Claude accepts images and PDFs but not video files." — [AnimSpec blog](https://animspec.com/blog/can-claude-watch-videos)
- Secondary confirmation (published Nov 3, 2026, updated Nov 9, 2026; docs-based, no hands-on test): Anthropic's vision docs list no video format, only images. — [CreatorFlow blog](https://creatorflow.so/blog/claude-video-editing/)
- Claude Code: secondary source says the Read tool opens images, PDFs, and Jupyter notebooks but cannot look inside an MP4; Claude Code can instead run ffmpeg via the shell on the local machine and then read the extracted frames. — [AnimSpec blog](https://animspec.com/blog/can-claude-watch-videos)
- Community wrappers exist that do exactly this for Claude Code (download, extract frames, transcribe, hand to Claude); they are third-party, not Anthropic features. — [bradautomates/claude-video on GitHub](https://github.com/bradautomates/claude-video)

### Inferences
- "Watching" a reel with Claude necessarily means converting it to still frames plus a text transcript before it reaches the model. There is no frame-sampling or length limit to document because there is no native video path.
- The one place Anthropic's docs mention MP4/MOV at all is for files Claude *produces* in the code execution sandbox (C2PA signing of generated image/video/audio outputs), which concerns output, not input. — see [Code execution tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)

### Gaps
- No Anthropic page states in so many words "video input is not supported"; the conclusion rests on omission from all supported-type lists.
- Feature-request threads about native video input (mirrored on claudeissues.com) could not be opened: that host is not reachable from this research session's network allowlist. A search-result summary said one request for mp4/mov/webm upload was opened March 8, 2026 and closed March 11, 2026; this is unverified.
- Claude Code's official tools reference was not fetched directly; the Read-tool statement above comes from a secondary source.

## 2. Does Claude accept audio input natively anywhere? Can it transcribe an uploaded audio file?

### Takeaway
No audio-file input is documented for the API or for app uploads; audio only enters Claude through live voice features (voice mode in the apps, dictation in Claude Code), where speech is transcribed to text. An uploaded mp3/wav/mp4 audio track is not transcribed by Claude natively, so the reel's voiceover needs a separate speech-to-text step.

### Cited Findings
- Neither the vision guide nor the Files API content-block table includes any audio type. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision); [Anthropic Files API docs](https://platform.claude.com/docs/en/build-with-claude/files)
- The claude.ai supported-uploads article (updated July 23, 2026) lists no audio formats. — [Claude Help Center](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- Voice mode exists in the Claude apps for live conversation; "Textual transcripts of your audio conversations are saved in your chat history just like text conversations." In Claude Cowork and Claude Code, dictation is available but voice mode is not. (Quoted via search-result excerpt of the help article, not a full fetch.) — [Claude Help Center: Use voice mode](https://support.claude.com/en/articles/11101966-use-voice-mode)
- Claude Code voice dictation streams recorded audio to Anthropic's servers for transcription (not local). (Via search-result excerpt.) — [Claude Code docs: voice dictation](https://code.claude.com/docs/en/voice-dictation)
- Third-party vendor pages (transcription vendors, so interested parties) consistently say Claude cannot transcribe uploaded audio/video files. — [Sonix](https://sonix.ai/ai/can-claude-transcribe-audio/); [Speak AI](https://speakai.co/integrations/claude/)
- Common workaround cited in secondary sources: extract audio with ffmpeg and transcribe with a Whisper model, or pull existing captions with yt-dlp. — [AnimSpec blog](https://animspec.com/blog/can-claude-watch-videos)

### Inferences
- Voice mode is a microphone feature, not a file-transcription feature; it cannot be pointed at an mp4.
- For 20-60 s reels, a free local Whisper run (or the platform's auto-captions) is the practical transcript source; the transcript then goes to Claude as plain text at negligible token cost.

### Gaps
- One user report (search-result summary of a May 2026 feature request) claimed claude.ai web "already analyzes audio files". It could not be opened or verified and conflicts with Anthropic's supported-types list. If true, it most likely describes the code-execution sandbox processing the file with Python, not native audio understanding; this is unconfirmed.
- Whether the claude.ai sandbox has any speech-to-text library pre-installed is undocumented.

## 3. Image input limits, token cost, and how many frames of a 60 s video fit in one message

### Takeaway
claude.ai / Claude Desktop: 20 images per message, 10 MB each, max 8000x8000 px. API: up to 600 images per request (100 on 200k-context models), 10 MB each base64, 128 MB request cap. Cost is `ceil(w/28) x ceil(h/28)` visual tokens per image, so a 1080x1920 reel frame costs about 2,691 tokens on current (4.7+) models, or about 700 tokens if downscaled to 540x960.

### Cited Findings
- Image count limits: "20 for each message on claude.ai"; "100 for each request on the API, for models with a 200k-token context window"; "600 for each request on the API, for all other models." — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- "The maximum dimensions for each image are 8000x8000 px." Max size per image: 10 MB (base64) on the Claude API, 5 MB on Amazon Bedrock, 10 MB on claude.ai. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- If an API request has more than 20 images, a stricter per-image dimension limit applies to every image; Anthropic's advice is to keep neither dimension above 3,000 px or stay at 20 or fewer image blocks. Images resent from earlier turns count toward the 20. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Request size cap is 128 MB on the first-party API and "can be reached first"; Anthropic suggests the Files API (`file_id` references) for many images. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Token formula: "Each patch is a 28x28-pixel block ... An image, therefore, costs `ceil(width / 28) x ceil(height / 28)` visual tokens." — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Resolution tiers: High-resolution (Claude 4.7 and later models): max long edge 2,576 px, max 4,784 visual tokens. Standard (all other models): max long edge 1,568 px, max 1,568 visual tokens. Larger images are downscaled preserving aspect ratio; high-res is automatic. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Reference costs from Anthropic's table: 1000x1000 = 1,296 tokens (both tiers); 1920x1080 = 2,691 tokens on high-res tier (not resized) vs 1,560 on standard tier (downsized to 1456x819); 200x200 = 64 tokens. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Pricing examples in the doc: at Claude Haiku 4.5's $1/M input tokens a 1000x1000 image is about $1.30 per thousand images; at Claude Opus 5.5's $4/M it is about $5.18 per thousand. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- "High-resolution images can use up to roughly three times more visual tokens ... downsample images before sending to control token costs." — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- claude.ai chat upload limits: 500 MB per file and up to 20 files per chat; project knowledge files 30 MB each; images up to 8000x8000 px, with a recommendation to use 1000x1000 px or larger. (Article updated July 23, 2026.) — [Claude Help Center](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- PDFs: Claude analyzes both text and visual elements in PDFs of 100 pages or fewer in claude.ai. — [Claude Help Center](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- Secondary: a 60-second clip at 4 fps (240 frames) exceeds what one claude.ai message allows. — [AnimSpec blog](https://animspec.com/blog/can-claude-watch-videos)

### Inferences (my arithmetic from the cited formula; not stated by Anthropic)
- Vertical reel frame costs: 1080x1920 -> 39 x 69 = 2,691 tokens (high-res tier, no resize). 720x1280 -> 26 x 46 = 1,196. 540x960 -> 20 x 35 = 700. 360x640 -> 13 x 23 = 299.
- claude.ai / Claude Desktop, one message, 20 separate frames: a 60 s reel gets one frame every 3 s; a 20 s reel gets 1 fps. At 540x960 that is about 14,000 tokens; at full 1080x1920 about 54,000 tokens.
- Contact sheets beat the 20-image cap: tiling several frames into one image (for example a 3x3 grid of 9:16 frames at roughly 1449x2576) lets 20 images carry 180 frames, at up to 4,784 tokens per sheet (about 96k tokens for all 20). Each tile is then only about 483x859 px, so small on-screen text gets harder to read. This is a common practice inference, not an Anthropic recommendation.
- API, one request: 60 frames (1 fps for 60 s) at 540x960 is about 42,000 input tokens, roughly $0.17 on Opus 5.5 at the $4/M figure quoted in the vision doc; 120 frames (2 fps) about 84,000 tokens / $0.34. The 600-image cap is not the binding constraint for a 60 s reel; token cost is.
- Because the first 3 seconds (the hook) matter most for reels, a denser sample there (for example 2-4 fps for 0-3 s, then 1 frame per 2-3 s) fits within 20 images.
- The "20 files per chat" help-center figure and the "20 images per message" vision-doc figure are different limits; whether more than 20 images can be sent across several messages in one Claude Desktop chat was not confirmed (see Gaps).

### Gaps
- Whether claude.ai downsamples uploaded images further before the model sees them (beyond the API's tier rules) is not documented.
- Per-plan message/usage caps for the Free plan are not covered here; image-heavy messages consume usage faster but Anthropic publishes no per-image figure for the apps.
- Could not confirm from a primary source whether the 20-files-per-chat limit blocks sending 20 images in each of several consecutive messages.

## 4. What happens when a user drags an mp4 into Claude Desktop / claude.ai today?

### Takeaway
Not determinable from Anthropic's documentation, and I found no dated, first-hand 2026 test that quotes the actual behavior. MP4 is absent from the supported list, so the model will not "see" the video either way; whether the upload is rejected outright or accepted as an opaque file for the code-execution sandbox needs a 30-second hands-on test.

### Cited Findings
- MP4/MOV are not on the claude.ai supported upload list (updated July 23, 2026). The article does not say what happens with unsupported types. — [Claude Help Center](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- The same article says some types depend on the sandbox: "You must enable code execution and file creation in your account to upload XLSX files." — [Claude Help Center](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai)
- The file-creation help article says the sandbox handles CSV, TSV and "other files" for analysis, without enumerating them. — [Claude Help Center: Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)
- One undated-method secondary claim (surfaced only as a search-result summary, original page not opened) says uploading an MP4 to the chat returns an unsupported-file-type error. — [ScreenApp blog](https://screenapp.io/blog/can-claude-watch-videos) (unverified; vendor blog)
- A search-result title suggests a different observed behavior in some environment: "Claude defaults to thumbnails for large videos instead of using multi-part uploads". The page was unreachable, so product, date, and context are unknown. — [claudeissues.com mirror](https://claudeissues.com/issue/68597-claude-defaults-to-thumbnails-for-large-videos-instead-of-using-multi-part-uploa) (unverified)

### Inferences
- With "Code execution and file creation" enabled, non-listed file types are plausibly accepted as sandbox files (the XLSX precedent and the "other files" wording point that way), in which case the mp4 would land in the sandbox without any of it entering the model's context. With the feature off, rejection is the likely outcome. Both are inferences.

### Gaps
- Exact current behavior and error text for an mp4 dropped into Claude Desktop on Windows: no primary source and no verified first-hand 2026 report. Needs a direct test.

## 5. Does the Claude Desktop code-execution / file-creation sandbox have ffmpeg, so Claude can extract frames itself with no local setup? Upload size limits?

### Takeaway
Unconfirmed. Anthropic documents no ffmpeg (or OpenCV/moviepy) in either sandbox. The API code-execution container definitely cannot add it (no internet, fixed library list). The claude.ai/Desktop sandbox on Free/Pro/Max has network access to PyPI, npm, GitHub and Ubuntu apt mirrors, so installing a video library at runtime is plausible but not documented or verified. Upload size is documented inconsistently: 30 MB in the file-creation article vs 500 MB in the uploads article.

### Cited Findings
- Availability: code execution and file creation works on web, Claude Desktop, and mobile for all plans including Free; on by default for Free/Pro/Max/Ultra, with network access on. Toggle lives in Settings > Capabilities ("Code execution and file creation", or "Create and edit files" in the updated layout), plus "Allow network egress". — [Claude Help Center: Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)
- Approved network domains when egress is on include pypi.org, files.pythonhosted.org, registry.npmjs.org, github.com, archive.ubuntu.com, security.ubuntu.com, crates.io, yarnpkg.com. — [Claude Help Center: Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)
- The same article states a maximum file size of 30 MB for uploads and downloads in this feature, gives no CPU/RAM/disk figures, says resources and task duration are "intentionally limited", and notes file creation uses more of the plan's usage limit than normal chat. It never mentions video, audio, MP4 or ffmpeg. — [Claude Help Center: Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)
- Conflict: the uploads article (updated July 23, 2026) says "File size: 500MB per file" for chat uploads and 30 MB for project files. — [Claude Help Center: uploads](https://support.claude.com/en/articles/8241126-what-kinds-of-documents-can-i-upload-to-claude-ai); contradicted by the 30 MB figure in [Create and edit files](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)
- API code execution tool (a different sandbox from the apps): Python 3.11, Linux x86_64, 5 GiB RAM, 5 GiB disk, 1 CPU; "Internet access: Completely disabled"; "Claude can't download or install additional packages at runtime: only the pre-installed libraries are available." — [Anthropic code execution tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- API sandbox pre-installed list: pandas, numpy, scipy, scikit-learn, statsmodels, matplotlib, seaborn, pyarrow, openpyxl, xlsxwriter, xlrd, pillow, python-pptx, python-docx, pypdf, pdfplumber, pypdfium2, pdf2image, pdfkit, tabula-py, reportlab, img2pdf, sympy, mpmath, tqdm, python-dateutil, pytz, joblib; CLI tools "such as unzip, unrar, 7zip, bc, rg (ripgrep), fd, and sqlite". ffmpeg, OpenCV, moviepy, imageio are not listed. — [Anthropic code execution tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- API sandbox documented input types via `container_upload`: CSV, Excel, JSON, XML, images, text files. Video is not listed. — [Anthropic code execution tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- API code execution pricing: 1,550 free container-hours per organization per month, then $0.05 per hour per container; free when used alongside the current web search / web fetch tools. — [Anthropic code execution tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
- Secondary (published Nov 3, 2026; docs review only, explicitly no hands-on test): for the Claude app sandbox ffmpeg is "not listed" and network access may let it install packages from approved sources; for the API it is "Not on the pre-installed list, and the container has no internet." Recommends Claude Code with ffmpeg installed locally for real reel footage. — [CreatorFlow blog](https://creatorflow.so/blog/claude-video-editing/)
- A third-party plugin README notes that ffmpeg installed on the user's own machine is not present inside a cloud sandbox. (Search-result excerpt.) — [digitalsamba/claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit/blob/main/CLAUDE.md)

### Inferences
- "The pre-installed list is illustrative" matters: both docs use "such as" / "commonly used", so ffmpeg could be present yet unlisted. Absence from the list is not proof of absence in the app sandbox.
- If ffmpeg is missing in the app sandbox, Free/Pro/Max network egress to PyPI makes `pip install imageio-ffmpeg` (bundles a static ffmpeg binary) or `opencv-python-headless` a plausible route, since both are served from pypi.org / files.pythonhosted.org, which are on the approved list. This is an untested inference.
- Even if frame extraction works in the sandbox, extracted frames sit on the sandbox disk. For the model to actually look at them, Claude must open them as images in-conversation, and each viewed frame costs image tokens exactly as in section 3. Whether and how many sandbox images Claude can view per turn in the apps is not documented.
- A 20-60 s 1080x1920 reel is typically well under 30 MB, so even the stricter documented limit should not block the upload on size alone; type acceptance is the open question.
- Lowest-risk zero-cost path for a Windows 10 user if the sandbox route fails: extract frames locally with ffmpeg (free) and drag up to 20 JPEGs per message into Claude Desktop, plus paste a transcript. Claude Code or Cowork with local ffmpeg automates this but, per the secondary source above, most Claude Code surfaces need a paid plan or Console account.

### Gaps
- No primary source and no verified hands-on report on whether `ffmpeg` exists in the claude.ai / Claude Desktop sandbox in Nov 2026. Fastest resolution: ask Claude Desktop to run `which ffmpeg; python -c "import cv2"` with code execution enabled.
- Whether an mp4 is accepted into the app sandbox at all (see section 4).
- Which of 30 MB or 500 MB is the operative chat-upload limit; Anthropic's two help articles disagree.
- App sandbox CPU/RAM/disk and time limits are unpublished.

## 6. Is there an official Anthropic cookbook / guide on video understanding via frame extraction?

### Takeaway
None found. GitHub code search of the official `anthropics/claude-cookbooks` repository returned zero hits for ffmpeg, `cv2.VideoCapture`, and mp4, and Anthropic's vision guide contains no video section. Frame-extraction-plus-transcript guidance comes only from third parties.

### Cited Findings
- Code search on 2026-11-12 in `anthropics/claude-cookbooks` for `ffmpeg`, `cv2.VideoCapture`, `mp4`, and `youtube transcript` returned 0 results each. — [anthropics/claude-cookbooks on GitHub](https://github.com/anthropics/claude-cookbooks)
- The vision guide covers images only and offers no video or frame-sampling guidance; the closest statement is that animations use only the first frame. — [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- Third-party open-source tools implement the pattern for Claude Code, for example a `/watch` command that downloads, extracts frames, transcribes, and hands the result to Claude, with uniform, scene-aware, and keyframe sampling modes. Not affiliated with Anthropic. — [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
- Secondary write-ups describe the standard recipe as ffmpeg frame extraction + Whisper transcription + timestamps labelled on frames. — [AnimSpec blog](https://animspec.com/blog/can-claude-watch-videos)

### Inferences
- With no official recipe, sampling rate, frame size, and frame labelling are the user's design choices, bounded only by the image limits in section 3.

### Gaps
- GitHub code search only indexes the default branch and can miss notebook content; a manual browse of the cookbook's `multimodal/` folder was not done, so a small video example cannot be fully ruled out.
- I did not review the third-party tools' code or safety; they are listed as existence proof only.
