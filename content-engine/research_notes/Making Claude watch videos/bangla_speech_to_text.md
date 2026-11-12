# Free, local speech-to-text for Bangla and Banglish on a Windows 10 Intel i7 CPU (state as of 12 Nov 2026)

Reading notes for the report writer:
- Everything under "Cited Findings" was fetched or searched this session. Items marked "(search summary)" came from a search-result digest and were NOT opened on the primary page; treat them as lower confidence.
- Nothing was run. No command below was executed on Windows; commands are assembled from the documented CLI options and are labelled as untested.
- Bengali error rates from different sources are NOT comparable with each other (different test sets, WER vs CER, normalised vs orthographic scoring). Only before/after pairs inside one source are comparable.

## 1. How good is OpenAI Whisper (large-v3, large-v3-turbo, medium) on Bengali?

### Takeaway
Stock Whisper is weak on Bengali: every source found puts zero-shot large-v3 at roughly 55-90% WER (about 30-37% CER) on Bengali read speech, whereas Bengali fine-tunes of the same model reach about 10-32% WER. No Bengali-specific figure was found for large-v3-turbo or medium.

### Cited Findings
- Mozilla's fine-tune card gives a clean before/after on Common Voice 21 Bengali (9,363 eval clips): stock whisper-large-v3 = 55.46% normalised WER / 83.34% orthographic WER / 35.66% normalised CER; after fine-tuning = 9.65% normalised WER / 24.29% orthographic WER / 4.88% normalised CER — [mozilla-ai/whisper-large-v3-bn](https://huggingface.co/mozilla-ai/whisper-large-v3-bn)
- BuzzASR's card reports zero-shot whisper-large-v3 CER of 30.46% on FLEURS Bengali and 37.31% on Common Voice 25 Bengali (CER, not WER; normalised) — [BuzzASR/bengali](https://huggingface.co/BuzzASR/bengali)
- Fleurs-SLU's per-language table lists Bengali at 33.9 for Whisper-v3-Large vs 9.0 for SeamlessM4Tv2-Large; the caption says these are average CER (search summary) — [Fleurs-SLU, arXiv 2501.06117](https://arxiv.org/pdf/2501.06117)
- The Dolphin paper lists Whisper large-v3 Bengali WER of 71.0 in one table and 77.0 in another; the search digest could not tell with certainty which table is Common Voice 17 (search summary) — [Dolphin, arXiv 2503.20212](https://arxiv.org/pdf/2503.20212)
- ElevenLabs' marketing page lists Whisper Large v3 at 89.4% WER on Bengali and claims Scribe reaches 3.1% WER on FLEURS and 5.5% on Common Voice; vendor figures, no methodology given (search summary) — [ElevenLabs Bengali STT](https://elevenlabs.io/speech-to-text/bengali)
- In a 2022 OpenAI Whisper GitHub discussion, a user reported Bengali output coming out in Devanagari script, and a maintainer said Bengali stays above 100% WER in the paper's breakdown and suggested fine-tuning (applies to the 2022 models, not large-v3) (search summary) — [openai/whisper Discussion #203](https://github.com/openai/whisper/discussions/203)
- large-v3-turbo is not trained for translation: OpenAI's README says it returns the original language even when translation is requested; it was fine-tuned on transcription data only, with the decoder cut from 32 layers to 4 (search summary) — [openai/whisper README](https://github.com/openai/whisper); [openai/whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo)
- A Hugging Face thread reports large-v3 "suddenly" outputting English for all transcriptions; the fix was passing `task="transcribe"` explicitly (a Transformers default-config issue, later reverted) (search summary) — [openai/whisper-large-v3 discussion #71](https://huggingface.co/openai/whisper-large-v3/discussions/71)

### Inferences
- The gap between 55% normalised and 83% orthographic WER on the same clips (Mozilla card) suggests a large share of Whisper's Bengali "errors" are spelling, punctuation and word-boundary differences rather than wrong words. CER of 30-37% still means roughly one character in three is wrong, so stock Whisper output in Bengali script is a rough draft, not a caption-ready transcript.
- For the stated purpose (comparing spoken pacing with on-screen captions), exact spelling matters less than timing. A noisy transcript with good word timestamps may still be usable for pacing analysis even where it is not usable as caption text.
- Because turbo cannot translate, it removes one failure mode (English translation instead of Bengali transcription). With large-v3 or medium, always set language `bn` and task `transcribe` explicitly.
- All benchmarks above are read speech (FLEURS, Common Voice). Short-form voiceovers with music beds and English loanwords are a different condition; expect results to differ, direction unknown.

### Gaps
- No Bengali WER found for large-v3-turbo or medium specifically. Whether turbo is worse than large-v3 on Bengali is unverified.
- The official OpenAI per-language WER table for large-v3 (FLEURS/Common Voice 15 chart in the GitHub README) was not opened; no official Bengali number is quoted here.
- No source found documenting how often Whisper emits romanised Bangla, hallucinated text on silence/music, or repeated phrases specifically for Bengali. These are well-known general Whisper behaviours but I have no Bengali-specific citation.

## 2. Which implementations are best on CPU, and what are the exact commands?

### Takeaway
`whisper-ctranslate2` (a CLI over faster-whisper) is the most direct fit: it runs through `uvx`, supports int8 on CPU, word timestamps, `initial_prompt`, SRT/VTT/JSON output, and can load a converted Bengali fine-tune from a folder. WhisperX has no default Bengali alignment model, so it fails on `bn` unless an alignment model is supplied by hand.

### Cited Findings
- faster-whisper latest on PyPI is 1.2.1, uploaded 31 Oct 2025; requires Python 3.9+; depends on ctranslate2 >=4.0,<5, onnxruntime, av (PyAV), huggingface-hub, tokenizers; has a `conversion` extra that pulls in transformers[torch] — [PyPI faster-whisper JSON](https://pypi.org/pypi/faster-whisper/json)
- whisper-ctranslate2 latest on PyPI is 0.5.9 (0.5.8 was uploaded 5 Oct 2026); requires faster-whisper>=1.2.0; its docs state int8 gives the best CPU performance — [PyPI whisper-ctranslate2 JSON](https://pypi.org/pypi/whisper-ctranslate2/json)
- whisper-ctranslate2 CLI options (from source): `--model` (default `small`; choices include `medium`, `large-v3`, `large-v3-turbo`, `turbo`), `--model_directory` (path to a CTranslate2 Whisper model, e.g. a fine-tune), `--output_format` (`txt`, `vtt`, `srt`, `tsv`, `json`, `all`; default `all`), `--output_dir`, `--language`, `--task` (`transcribe`/`translate`), `--word_timestamps` (default False), `--initial_prompt`, `--hotwords`, `--threads`, `--compute_type` (incl. `int8`), `--device` (`auto`/`cpu`/`cuda`), `--vad_filter`, `--temperature`, `--condition_on_previous_text` (default True), `--beam_size` (default 5), `--highlight_words` and `--max_words_per_line` (both need `--word_timestamps True`) — [whisper-ctranslate2 commandline.py](https://raw.githubusercontent.com/Softcatala/whisper-ctranslate2/main/src/whisper_ctranslate2/commandline.py)
- WhisperX's default alignment tables cover en, fr, de, es, it (torchaudio) and 36 Hugging Face languages including hi, ur, te, ml — but not `bn`. For a language with no default, `load_align_model` raises `ValueError("No default align-model for language: ...")` and tells the user to pass a wav2vec2 model via `--align_model` — [whisperX alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- A 2026 Bengali long-form paper ran WhisperX with `tanmoyio/wav2vec2-large-xlsr-bengali` and `ai4bharat/indicwav2vec_v1_bengali` among the models tried, and found `tugstugi_bengaliai-asr_whisper-medium` gave the lowest WER of the ASR models it tested (search summary) — [arXiv 2603.03158](https://arxiv.org/pdf/2603.03158)
- whisper.cpp latest tagged release is v1.9.5 (6 Oct 2026), a maintenance release updating ggml to v0.26.0. Its release assets are source archives only (zip and tar.gz); the release page showed a separate build "b5454" with 14 assets, whose file names I could not read — [whisper.cpp releases](https://github.com/ggml-org/whisper.cpp/releases); [v1.9.5 assets](https://github.com/ggml-org/whisper.cpp/releases/expanded_assets/v1.9.5)
- CPU speed reference: the faster-whisper README benchmark, as quoted by secondary articles, has the `small` model with int8 transcribing 13 minutes of audio in about 1 min 42 s on an Intel Core i7-12700K with 8 threads (about 7.6x real time, 1,477 MB RAM), vs 6 min 58 s for openai/whisper (search summary; secondary sources) — [faster-whisper mirror README](https://github.com/rrrodzilla/faster-whisper)

### Inferences
- Suggested starting commands, UNTESTED, built from the options above (run in PowerShell or cmd; first run downloads the model from Hugging Face):
  - Stock turbo, Bengali script, word timestamps, all output files:
    `uvx whisper-ctranslate2 "clip.mp4" --model large-v3-turbo --language bn --task transcribe --device cpu --compute_type int8 --word_timestamps True --vad_filter True --condition_on_previous_text False --output_format all --output_dir out`
  - Same with stock large-v3 (slower, can translate, so keep `--task transcribe`): replace `--model large-v3-turbo` with `--model large-v3`.
  - Bengali fine-tune converted to CTranslate2: replace `--model ...` with `--model_directory "C:\models\bn-whisper-ct2"`.
  - Whether the tool accepts an .mp4 directly (via PyAV, which faster-whisper depends on) or needs FFmpeg extraction first was not verified; a safe pre-step is `ffmpeg -i clip.mp4 -ar 16000 -ac 1 clip.wav`.
- Speed estimate (my estimate, not a measurement): the only sourced figure is `small` at ~7.6x real time on a 12th-gen desktop i7. Turbo has the full large encoder with a 4-layer decoder, so it will be several times slower than `small`; large-v3 slower again. For a 60 s clip on a 4-8 core i7, plan for somewhere between tens of seconds and a few minutes depending on model and CPU generation, plus one-off model load and download time. Older or laptop i7s (4 cores, pre-10th gen) will be at the slow end. This should be measured on the actual machine with one clip.
- For 20-60 s clips, speed is not the deciding factor; any of these finishes in minutes. Accuracy on Bengali should drive the choice.
- WhisperX is a poor fit here: no Bengali aligner by default, a heavier PyTorch install, and the candidate aligners (`tanmoyio/wav2vec2-large-xlsr-bengali`, `ai4bharat/indicwav2vec_v1_bengali`) handle Bengali script only, so English words written in Latin script inside a Banglish transcript would likely not align. faster-whisper's own `word_timestamps` (derived from Whisper's attention, language-independent) avoids this.
- whisper.cpp on Windows currently needs either the per-commit build assets or compiling from source, since v1.9.5 ships no binaries on the tagged release. That makes it a weaker option for a non-developer than `uvx whisper-ctranslate2`.

### Gaps
- Model download sizes and RAM were not fetched this session. From memory (unverified): CTranslate2 large-v3 is about 3 GB, large-v3-turbo about 1.6 GB, medium about 1.5 GB at float16, with int8 RAM use roughly in the 1.5-4 GB range. Verify on the Systran / deepdml / mobiuslabsgmbh Hugging Face repos.
- No CPU-only benchmark found for large-v3-turbo or large-v3 int8 on an i7. The "realistic time for a 60 s clip" is an estimate only.
- GUI apps (Buzz, Vibe, Subtitle Edit) were not researched this session: current versions, Windows installers, Bengali handling and word-timestamp export are all unverified. From memory, all three are free and wrap whisper.cpp and/or faster-whisper, and Subtitle Edit can download whisper engines itself; none of that was checked.
- Whether `uvx whisper-ctranslate2` resolves cleanly on Windows 10 with the current Python/ctranslate2 wheels was not tested.
- Names of whisper.cpp Windows binary assets (historically `whisper-bin-x64.zip`) and GGML quantised model sizes not confirmed.

## 3. Bengali fine-tuned models on Hugging Face

### Takeaway
Bengali fine-tunes of Whisper beat stock large-v3 by a wide margin on Bengali benchmarks, and the Whisper-based ones (Mozilla large-v3-bn, BuzzASR/bengali, tugstugi medium) are permissively licensed and should convert to faster-whisper format. None was found pre-converted, and all are trained on Bengali-script data, so their behaviour on English words is unknown.

### Cited Findings
| Model | Base / type | Licence | Reported accuracy | Source |
|---|---|---|---|---|
| mozilla-ai/whisper-large-v3-bn | whisper-large-v3 fine-tune, ~2B params, trained on 21,409 Common Voice 21 Bengali clips | Apache-2.0 | CV21 bn: 9.65% norm. WER (stock 55.46%); 24.29% orthographic WER (stock 83.34%) | [model card](https://huggingface.co/mozilla-ai/whisper-large-v3-bn) |
| BuzzASR/bengali | whisper-large-v3 full fine-tune on FLEURS + Common Voice 25; paper arXiv 2609.09554 (Sep 2026) | MIT | FLEURS: 10.16% CER / 31.97% WER (stock CER 30.46%); CV25: 5.5% CER / 19.42% WER (stock CER 37.31%) | [model card](https://huggingface.co/BuzzASR/bengali) |
| bengaliAI/tugstugi_bengaliai-asr_whisper-medium | Whisper medium, 0.8B params (Kaggle Bengali.AI competition model) | Apache-2.0 | Card is empty, no WER. Third-party: 34.07% WER raw on the Bengali-Loop long-form set; 31.32% with LoRA tuning | [model card](https://huggingface.co/bengaliAI/tugstugi_bengaliai-asr_whisper-medium); [arXiv 2603.04809](https://arxiv.org/pdf/2603.04809); [arXiv 2605.08214](https://arxiv.org/pdf/2605.08214) |
| hishab/titu_stt_bn_fastconformer | NVIDIA NeMo FastConformer, trained on ~18,333 h (17,640 h news) | CC BY-NC 4.0 (non-commercial) | Card shows results only as images. Third-party: 50.67% WER on Bengali-Loop long-form | [model card](https://huggingface.co/hishab/titu_stt_bn_fastconformer); [arXiv 2603.04809](https://arxiv.org/pdf/2603.04809) |
| ai4bharat/indic-conformer-600m-multilingual | Conformer, 22 Indian languages incl. Bengali; gated on HF (accept terms); community ONNX and int8 exports exist (encoder 2.4 GB fp32 -> ~0.62 GB int8) | MIT (per GitHub and third-party listings) | No Bengali WER found | [HF model](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual); [GitHub](https://github.com/AI4Bharat/IndicConformerASR); [int8 ONNX export](https://huggingface.co/yashwork-byte/indic-conformer-600m-int8-onnx) |
| SeamlessM4T v2 Large | Meta multilingual speech model | not checked | FLEURS Bengali 9.0 vs 33.9 for Whisper-v3-Large (average CER per the table caption) | [Fleurs-SLU, arXiv 2501.06117](https://arxiv.org/pdf/2501.06117) |

- (All third-party WER rows above and the SeamlessM4T row are from search summaries, not from opened papers.)
- Best reported long-form Bengali results in 2026 papers come from fine-tuned Whisper pipelines: 27.00% WER (WhisperAlign) and 24.41% WER (Bangla-WhisperDiar) on the Bengali-Loop test set (search summary) — [arXiv 2603.04809](https://arxiv.org/pdf/2603.04809); [arXiv 2605.08214](https://arxiv.org/pdf/2605.08214)
- Other community checkpoints are small or weakly documented: `KhushiDS/whisper-large-v3-Bengali` reports 44.5% WER on its eval set; `psdn-ai/bangla-asr` is a Whisper-medium fine-tune tied to a Bangla-10K paper (search summary) — [KhushiDS card](https://huggingface.co/KhushiDS/whisper-large-v3-Bengali); [psdn-ai/bangla-asr](https://huggingface.co/psdn-ai/bangla-asr)
- None of the three Whisper-based model cards (Mozilla, BuzzASR, tugstugi) mentions a CTranslate2, faster-whisper or GGML version — [mozilla-ai card](https://huggingface.co/mozilla-ai/whisper-large-v3-bn); [BuzzASR card](https://huggingface.co/BuzzASR/bengali); [tugstugi card](https://huggingface.co/bengaliAI/tugstugi_bengaliai-asr_whisper-medium)
- faster-whisper ships a `conversion` extra (transformers[torch]) for converting Transformers Whisper checkpoints, and whisper-ctranslate2 loads a converted folder with `--model_directory` — [PyPI faster-whisper JSON](https://pypi.org/pypi/faster-whisper/json); [whisper-ctranslate2 commandline.py](https://raw.githubusercontent.com/Softcatala/whisper-ctranslate2/main/src/whisper_ctranslate2/commandline.py)

### Inferences
- The most promising local route is a Bengali Whisper fine-tune converted once to CTranslate2 int8 and run through `whisper-ctranslate2 --model_directory`. Candidate order: mozilla-ai/whisper-large-v3-bn (clearest evidence, Apache-2.0), BuzzASR/bengali (MIT, most recent, evaluated on FLEURS too), tugstugi medium (smaller and faster, proven in the Kaggle competition and in 2026 papers, but no card).
- Conversion command from memory of the faster-whisper README, UNTESTED: `uvx --from "faster-whisper[conversion]" ct2-transformers-converter --model mozilla-ai/whisper-large-v3-bn --output_dir C:\models\bn-whisper-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization int8`. This pulls in PyTorch (a multi-GB download) and needs several GB of RAM; it is the one developer-ish step in the workflow. If the repo lacks `tokenizer.json`, the copy step fails and needs a workaround.
- Fine-tunes trained on read-speech corpora (Common Voice, FLEURS) may lose stock Whisper's ability to write English words in Latin script and may degrade its timestamp behaviour; both need a hands-on test with a real Banglish clip before committing.
- Titu is a weak fit: non-commercial licence, NeMo install (awkward on Windows), news-domain training, and the worst third-party WER in the list. IndicConformer is viable through ONNX but has no Whisper-style CLI or SRT/word-timestamp output out of the box.
- The headline Mozilla figure (9.65%) is on Common Voice, the same corpus family it was trained on; real-world voiceover accuracy will be worse. BuzzASR's FLEURS WER of 32% on a set it also trained on is a more sobering indicator.

### Gaps
- Meta MMS (mms-1b-all) Bengali WER and licence: not researched this session (from memory the weights are CC BY-NC 4.0; unverified).
- AI4Bharat IndicWhisper / Vistaar Bengali WER: not found.
- BanglaASR (bangla-speech-processing/BanglaASR) and other named models in the brief: not checked.
- No model was found that is fine-tuned specifically for Bangla-English code-mixed speech.
- Whether any pre-converted CTranslate2 or GGML build of these Bengali fine-tunes exists on Hugging Face was not searched directly.
- Kaggle Bengali.AI Speech Recognition competition write-ups were not opened.

## 4. Handling Banglish (code-mixed Bangla-English)

### Takeaway
Research on Bangla-English code-switched ASR exists but is thin and dated (MUCS 2021 era, about 28% WER on its test set), and I found no evidence-backed recipe for Banglish with Whisper. Prompting, transliteration and LLM clean-up are plausible approaches that have to be tested, not established practice.

### Cited Findings
- MUCS 2021 was a challenge on multilingual and code-switching ASR for low-resource Indian languages, with a Bengali-English code-switching track and Kaldi and Transformer baselines (search summary) — [arXiv 2104.00235](https://arxiv.org/pdf/2104.00235)
- A follow-up system reported 28.27% WER on the Bengali-English blind test vs a 32.81% baseline (search summary) — [arXiv 2203.16578](https://arxiv.org/pdf/2203.16578)
- Hussein et al. placed 3rd in the MUCS 2021 code-switching track with a 27.1% relative WER gain on Bengali-English by pre-training on balanced monolingual data then fine-tuning on code-switched data (search summary) — [arXiv 2106.05885](https://arxiv.org/abs/2106.05885)
- The closest work using the word "Banglish" is CSVC-Net, a 3,840-sample spoken command classification dataset (92.08% accuracy); it is command classification, not transcription (search summary) — [CSVC-Net listing](https://astro.paperswithcode.com/paper/csvc-net-code-switched-voice-command)
- The tooling exposes the relevant levers: `--initial_prompt` (text prompt for the first window), `--hotwords` (hint phrases such as names), `--language`, and `--condition_on_previous_text` — [whisper-ctranslate2 commandline.py](https://raw.githubusercontent.com/Softcatala/whisper-ctranslate2/main/src/whisper_ctranslate2/commandline.py)

### Inferences
- Practical options to test, in order of effort:
  1. `--language bn` with an `--initial_prompt` written in the target style, i.e. a short Bengali sentence that keeps English terms in Latin script (for example property and brand terms the videos use). This nudges script choice and spelling; it does not guarantee it. `--hotwords` can carry recurring English terms and names.
  2. Transcribe in Bengali script (English words will often come out transliterated into Bengali letters), then have an LLM rewrite to the desired Banglish form using the known script or caption text as reference. Word timestamps come from the ASR pass, so the LLM step must not change word count or order if timings are to be reused.
  3. Run two passes (`--language bn` and `--language en`) and compare; the English pass tends to capture the English words and garble the Bangla, which can help spot loanwords.
- For the pacing use case, a simpler design is possible: since the on-screen captions and usually the script are already known, the ASR only needs to supply timing. Matching ASR words to known caption text by position and time is more robust than trying to get a perfect Banglish transcript.
- Romanised (Latin-script) Bangla output cannot be reliably forced from Whisper; it is trained mostly on Bengali-script Bengali. Transliteration after the fact (by an LLM or a transliteration library) is the dependable route.

### Gaps
- No source found on whether `initial_prompt` actually improves Bengali code-switched output or controls script choice; this is untested advice.
- No recent (2024-2026) Bangla-English code-switching ASR paper or dataset was found; one search only.
- No evidence on how Bengali fine-tunes (section 3) treat English words.

## 5. Free cloud fallbacks with Bengali support

### Takeaway
Groq's hosted Whisper is the simplest free fallback and its limits are far above what short clips need, but it is the same stock Whisper with the same Bengali weakness. ElevenLabs Scribe claims by far the best Bengali accuracy, though the figures are the vendor's own and its free allowance is reported inconsistently.

### Cited Findings
- Groq documents these limits for both whisper-large-v3 and whisper-large-v3-turbo: 20 requests/minute, 2,000 requests/day, 7,200 audio seconds/hour, 28,800 audio seconds/day. The page is ambiguous about whether the table is the Free or Developer plan base — [Groq rate limits](https://console.groq.com/docs/rate-limits)
- Third-party sources mostly repeat 20 RPM / 2,000 RPD / 7,200 audio-seconds per hour as the free tier, with one outlier citing 30 RPM / 1,000 RPD (search summary) — [dev.to comparison](https://dev.to/build996/free-whisper-api-groq-deepgram-assemblyai-compared-562m); [CostBench](https://costbench.com/software/llm-api-providers/groq/free-plan/)
- ElevenLabs advertises Bengali speech-to-text with Scribe: 99 languages, character-level timestamps, speaker diarisation, audio-event tagging, and claimed Bengali WER of 3.1% (FLEURS) and 5.5% (Common Voice) (vendor claim; search summary) — [ElevenLabs Bengali STT](https://elevenlabs.io/speech-to-text/bengali)
- ElevenLabs' free allowance is reported inconsistently: about 4.5 hours of Scribe v2 on the free API tier, 10 hours/month, and 12 minutes in-app, depending on the source (all third-party; search summary) — [Activepieces](https://www.activepieces.com/blog/elevenlabs-scribe-v3-api-limits-and-pricing-2026); [stork.ai](https://www.stork.ai/blog/elevenlabs-speech-to-text-scribe-2026); [vexascribe comparison](https://vexascribe.com/compare/best-transcription-api-for-developers)
- Deepgram is described as listing 36+ languages and AssemblyAI Universal-2 as 99 languages, without Bengali being named; free credit is reported as $200 (Deepgram) and $50 (AssemblyAI), with one source contradicting the Deepgram free credit (search summary) — [vexascribe comparison](https://vexascribe.com/compare/best-transcription-api-for-developers); [CostBench comparison](https://costbench.com/software/ai-transcription-apis/compare-all/)

### Inferences
- A 60 s clip uses under 1% of Groq's hourly audio allowance, so the free limits are not a practical constraint for this workload, whichever plan the table describes. Accuracy will match local stock large-v3 / turbo, so Groq buys speed, not quality.
- If the vendor claims are even roughly right, Scribe is the accuracy leader for Bengali and returns word/character timestamps, which fits the caption-timing use case. Worth a side-by-side test on two or three real clips before relying on it.
- Cloud options mean uploading client or brand audio to a third party; for published social videos that is usually low-risk, but it is a decision for the user.

### Gaps
- Google Gemini audio understanding: the docs page redirected (ai.google.dev -> aistudio.google.com) and was not read. Free-tier limits, current model names, Bengali quality and timestamp reliability in 2026 are all unverified. From memory, Gemini accepts audio and can produce timestamps on request, but its timestamps are generated text rather than aligned measurements, so they are less trustworthy for pacing analysis; unverified.
- ElevenLabs' actual current free allowance and whether the free plan permits commercial use: not confirmed on the official pricing page.
- Deepgram and AssemblyAI Bengali support: not confirmed on vendor docs.
- No independent benchmark found comparing Scribe, Gemini and Whisper on Bengali.

## 6. Word-level timestamps and output formats

### Takeaway
`whisper-ctranslate2` with `--word_timestamps True` and `--output_format all` writes TXT, SRT, VTT, TSV and JSON in one run, and the JSON carries per-word timing, which is what a caption-pacing comparison needs. This works for Bengali without WhisperX, whose alignment step does not support Bengali out of the box.

### Cited Findings
- whisper-ctranslate2 output formats are `txt`, `vtt`, `srt`, `tsv`, `json`, or `all` (default `all`); `--word_timestamps` is off by default; `--highlight_words` and `--max_words_per_line` shape SRT/VTT and both require `--word_timestamps True` — [whisper-ctranslate2 commandline.py](https://raw.githubusercontent.com/Softcatala/whisper-ctranslate2/main/src/whisper_ctranslate2/commandline.py)
- WhisperX raises an error for `bn` unless `--align_model` is given, because Bengali is absent from its default alignment models — [whisperX alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- Bengali wav2vec2 models that researchers have used with WhisperX include `tanmoyio/wav2vec2-large-xlsr-bengali` and `ai4bharat/indicwav2vec_v1_bengali` (search summary) — [arXiv 2603.03158](https://arxiv.org/pdf/2603.03158)
- A 2026 Bengali paper (WhisperAlign) used whisper-timestamped to chunk audio into segments before recognition, and noted that forced aligners such as the Montreal Forced Aligner need phoneme dictionaries not readily available for Bengali (abstract fetched; MFA note from search summary) — [arXiv 2603.04809](https://arxiv.org/abs/2603.04809)
- ElevenLabs Scribe returns character-level timestamps (vendor claim; search summary) — [ElevenLabs Bengali STT](https://elevenlabs.io/speech-to-text/bengali)

### Inferences
- Recommended output for analysis: the JSON file (segments with a `words` list of word, start, end, probability in the faster-whisper/OpenAI-Whisper layout; exact field names not verified this session) plus an SRT for human reading. `--max_words_per_line 1` with SRT gives a one-word-per-cue file that is easy to eyeball against captions.
- From word timings one can derive words per second, pause lengths, time to first word, and offset between a spoken word and its caption appearing (caption timings would come from the video frames or the editor's caption file, outside this topic).
- Whisper-derived word timestamps are typically accurate to roughly a tenth to a few tenths of a second and are weakest around music, long pauses and clip starts; that is my expectation from general Whisper behaviour, not a Bengali measurement. `--vad_filter True` generally reduces hallucinated text in silent or music-only stretches.
- If a Bengali fine-tune (section 3) gives better words but worse timings, a workable split is: fine-tune for text, stock Whisper for timing, then match the two.

### Gaps
- No measurement found of Whisper word-timestamp accuracy on Bengali.
- JSON schema field names for whisper-ctranslate2 output not verified.
- Whether word timestamps survive conversion of Bengali fine-tunes to CTranslate2 (alignment heads are set in the generation config and may be missing or wrong in fine-tunes) is unverified and is a known risk area.
