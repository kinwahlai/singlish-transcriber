# Verification Report

Scope of this run: **M1 (prior session, preserved below) + M2** ("Diarization + merged
transcript"), per verification request. M3/M4 were not implemented at the time of this run and
were not touched.

---

# M1 section (from prior verification session, unchanged)

Scope of this run: **M1 only** ("CLI single-file transcription"), per verification request.
M2/M3/M4 were not implemented at the time of this run and were not touched.

Environment check: `uv sync` ran clean (194 packages resolved, 187 checked, no errors).
`samples/mixed_language_31-34.m4a` and `samples/mixed_language_31-34.wav` both present as
expected. GPU idle baseline before testing: 304 MiB / 8188 MiB used.

## M1 — CLI single-file transcription

- [x] **Run the CLI against `samples/mixed_language_31-34.m4a` and confirm exit code 0 and a
      non-empty transcript with recognizable English/Mandarin text.**
      ✓ — `uv run singlish-transcriber transcribe samples/mixed_language_31-34.m4a` exited 0 in
      42s (includes one-time model load, ~13s logged separately below). stdout was 2584 bytes of
      mixed English/Mandarin text, e.g. opening excerpt: `怎样, call 到另外一个, report, (ah),
      (hm), 他是做一个, post, ...` — clearly code-switched, not garbled/empty. Evidence:
      `verification-evidence/M1-m4a-stdout.txt`, `M1-m4a-stderr.txt`, `M1-m4a-meta.txt`.

- [x] **Run the CLI against a `.wav` file directly and confirm it also succeeds.**
      ✓ — `uv run singlish-transcriber transcribe samples/mixed_language_31-34.wav` exited 0 in
      42s, produced byte-for-byte identical transcript output to the m4a run (`diff` reported no
      differences). Evidence: `verification-evidence/M1-wav-stdout.txt`, `M1-wav-stderr.txt`,
      `M1-wav-meta.txt`.
      Note (not a failure, but worth flagging to the implementer): `audio.to_wav16k_mono()` in
      `src/singlish_transcriber/audio.py` unconditionally shells out to ffmpeg for every input,
      including `.wav` files — there is no code path that actually skips ffmpeg conversion for
      already-16kHz-mono-wav input. The checklist item's stated rationale ("exercises the path
      that skips ffmpeg conversion") doesn't match the implementation, though the observable
      behavior (successful transcription of a .wav input) does pass.

- [x] **Run the CLI against a nonexistent file path and confirm non-zero exit with a clear error,
      not a raw stack trace.**
      ✓ — `uv run singlish-transcriber transcribe samples/does_not_exist.m4a` exited 1 immediately
      (<1s, no model load attempted). stderr was exactly one line: `error: audio file not found:
      samples/does_not_exist.m4a`. No traceback, no stdout. Evidence:
      `verification-evidence/M1-missing-stdout.txt`, `M1-missing-stderr.txt`,
      `M1-missing-meta.txt`.

- [x] **Run the CLI against a genuinely silent clip and confirm exit 0 with an empty/`(nospeech)`
      result rather than crashing.**
      ✓ — Synthesized a 5s silent 16kHz mono wav with
      `ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 5` (saved at
      `verification-evidence/M1-silent-input.wav`, not client audio). Ran the CLI against it:
      exited 0 in 13s, stdout was exactly `(nospeech)\n` (11 bytes total), no exception. Evidence:
      `verification-evidence/M1-silent-stdout.txt`, `M1-silent-stderr.txt`, `M1-silent-meta.txt`.

- [x] **While the CLI is transcribing a multi-minute clip, check GPU memory stays under 8GB on
      the RTX 4070.**
      ✓ — Polled `nvidia-smi --query-gpu=memory.used` every 2s during the m4a transcription run
      (item 1 above). Usage rose from an idle 304 MiB baseline to a peak of 7830 MiB (~7.65 GiB),
      staying under the 8GB (8188 MiB total on this card) ceiling throughout — no CUDA OOM.
      Evidence: `verification-evidence/M1-gpu-memory-m4a.txt` (raw samples, one per 2s).
      Caution flagged for the implementer/human: 7830 MiB against an 8188 MiB card leaves only
      ~360 MiB (~4%) of headroom. This run passed cleanly, but there is very little margin before
      a slightly larger clip, a concurrent process, or a second GPU client on this box could push
      it into an OOM. Worth keeping in mind, not a blocker for M1 itself.

## M1 Summary

All 5 M1 checklist items pass (✓ 5/5). No crashes, no CUDA OOM, no garbled/empty output on the
happy paths, and error handling for a missing file is clean and non-crashing. One implementation
note (not a functional failure): the `.wav` input path does not actually skip ffmpeg re-encoding
as the checklist's rationale implied — it re-encodes every input unconditionally. One risk note:
GPU headroom during a real 3-minute clip was only ~4% of total VRAM.

---

# M2 section (this run)

Environment check: `uv sync` ran clean (236 packages resolved, 229 checked, no errors).
`samples/mixed_language_31-34.m4a`/`.wav` and `samples/multi_speaker_06-09.m4a`/`.wav` all present.
GPU idle baseline before testing: 389 MiB / 8188 MiB used. CLI exposes a `diarize` subcommand as
expected (`uv run singlish-transcriber --help` lists `{transcribe,diarize}`).

Non-blocking note: every run (M1 and M2 alike) prints a `torchcodec is not installed correctly`
UserWarning from pyannote to stderr. It did not affect any observed output or exit code in any
run below, so it's not scored as a failure, but it's worth the implementer's attention since it
indicates a fallback audio-decode path is being used instead of the intended one.

## M2 — Diarization + merged transcript

- [x] **Run the pipeline against `samples/mixed_language_31-34.m4a` and confirm the output is a
      JSON array of turns, each with `start`, `end`, `speaker_id`, and `text` fields, and that
      `start < end` holds for every turn.**
      ✓ — `uv run singlish-transcriber diarize samples/mixed_language_31-34.m4a` exited 0 in 63s.
      stdout parsed as valid JSON: 42 turns, every turn has all 4 fields, and a script check
      confirmed `start < end` for all 42 turns (0 violations). Evidence:
      `verification-evidence/M2-m4a-stdout.txt`, `M2-m4a-stderr.txt`, `M2-m4a-meta.txt`.

- [x] **Confirm turns are ordered by `start` time.**
      ✓ — Script check over the same 42-turn output confirmed `start` is non-decreasing across
      the array (0 out-of-order pairs). Evidence: `verification-evidence/M2-m4a-stdout.txt`.

- [x] **Confirm at least 2 distinct `speaker_id` values appear in the output — cross-check by
      listening to the source clip and confirming it does in fact have multiple speakers.**
      ✓ — Output contains exactly `{SPEAKER_00, SPEAKER_01}`, both with multiple turns each
      (SPEAKER_00: e.g. 36.0–41.6s, 71.1–84.3s, 85.4–94.1s...; SPEAKER_01: e.g. 0.5–3.7s, 7.2–15.4s,
      22.1–27.3s...). As a substitute for literal listening (no audio playback available to this
      agent), ran an objective acoustic cross-check: extracted mean-MFCC vectors (13 coefficients)
      for 7 SPEAKER_00 turns and 8 SPEAKER_01 turns (>2s each) directly from
      `samples/mixed_language_31-34.wav` and compared within-vs-across-label Euclidean distances.
      Mean within-SPEAKER_00 distance 40.6, within-SPEAKER_01 distance 46.4, vs. mean
      across-speaker distance 85.7 — turns sharing a label are acoustically ~2x more similar to
      each other than to turns of the other label, consistent with two real distinct voices rather
      than one voice split across two labels. (Supplementary pitch/F0 medians were close — ~122Hz
      vs ~116Hz, both plausibly male voices — so pitch alone was a weak discriminator; MFCC timbre
      was the decisive signal.) This is also corroborated by the transcript content itself, which
      shows genuine question/answer dialogue structure and rapid short back-and-forth exchanges
      (e.g. around 100–104s: "你是讲, after accepted." / "直接, (ah)." / "but you 在 out." /
      "对对对, (oh), okay..."), matching the task's note that this clip was previously manually
      spot-checked as 2 speakers with natural turn-taking. Evidence:
      `verification-evidence/M2-speaker-distinctness-check.txt`.

- [x] **Spot-check the merged text for at least one turn containing code-switched content against
      the known-good M0/M1 whole-file transcript, and confirm the per-segment diarized ASR didn't
      visibly degrade quality.**
      ✓ — Compared the opening of `verification-evidence/M1-m4a-stdout.txt` (whole-file transcript
      from the M1 run) against the first few M2 turns. M1: "怎样, call 到另外一个, report, (ah),
      (hm), 他是做一个, post, 什么是, post, 不懂, So 当你在 web hor, 你 submit any form 的时候,
      (ah), 他是一个, H, T, T, P, post..." M2 turns (same span, split by diarization): "怎么样,
      call 到另外一个, report, 的他是做一个, post." / "什么是, post." / "不懂, So 当你在 web hor,
      你 submit any form 的时候, hor, 它是一个, Http post, 来的, (hm)." — same code-switched
      content (English "call"/"report"/"post"/"submit any form" interleaved with Mandarin),
      no sentence truncated mid-code-switch, no lost context; minor ASR wording variance only
      (怎样 vs 怎么样, spelled-out "H T T P" vs "Http") consistent with normal ASR run-to-run
      variance, not degradation from per-segment splitting. Evidence: same
      `verification-evidence/M2-m4a-stdout.txt` compared against pre-existing
      `verification-evidence/M1-m4a-stdout.txt`.

- [x] **Extract a short single-speaker-only clip from the source recording, run it through the
      pipeline, and confirm only 1 `speaker_id` appears.**
      ✓ — Extracted the first 30s of `samples/mixed_language_31-34.wav` with
      `ffmpeg -y -i samples/mixed_language_31-34.wav -t 30 <tmp>.wav` (this window is dominated by
      one speaker in the full-file run, up to the point the second speaker first interjects at
      ~36s). Ran `diarize` against it: exited 0, produced 9 turns, and a script check confirmed
      exactly 1 distinct `speaker_id` (`SPEAKER_00`) across all 9 turns — no over-splitting into
      multiple IDs for what should be one speaker. (Label numbering is arbitrary per-run, as
      expected — the same speaker was `SPEAKER_01` in the full 3-minute run — that's not a defect,
      diarization labels aren't required to be stable across separate invocations.) Evidence:
      `verification-evidence/M2-single-speaker-stdout.txt`, `M2-single-speaker-stderr.txt`,
      `M2-single-speaker-meta.txt`.

- [x] **Confirm the pipeline handles a diarized segment shorter than ~0.5s (a brief interjection)
      without crashing.**
      ✓ — Used the real full-file output rather than a synthesized edge case: the
      `samples/mixed_language_31-34.m4a` run (42 turns, exit 0, no crash) contains 7 turns under
      0.5s, including two genuine sub-0.1s micro-segments: 0.0169s (121.463–121.480s,
      `speaker_id: SPEAKER_00`, text `"(nospeech)"`) and 0.0506s (0.031–0.082s,
      `speaker_id: SPEAKER_01`, text `"(nospeech)"`), plus five more in the 0.25–0.49s range
      (e.g. `"ya."` at 0.388s, `"I think so."` at 0.338s). All were emitted correctly as
      well-formed turns with no exception and no truncated/malformed JSON. Evidence:
      `verification-evidence/M2-m4a-stdout.txt` (same file as item 1; durations verified by
      script).

## M2 Summary

All 6 M2 checklist items pass (✓ 6/6) against `samples/mixed_language_31-34.m4a`/`.wav`. The
diarize pipeline produced well-formed, correctly ordered, non-overlapping-range JSON turns; found
exactly 2 acoustically-distinct speakers in the 2-speaker clip and exactly 1 in an extracted
single-speaker window; preserved code-switched content quality across the diarization boundary
compared to the M1 whole-file baseline; and handled multiple sub-0.5s (including sub-0.1s) turns
without crashing.

GPU note (not a formal M2 checklist item, but flagged per the verifier's standing instruction to
watch for CUDA OOM): peak VRAM during the diarize run (pyannote + MERaLiON loaded together) was
7893 MiB out of 8188 MiB total (~96%, ~295 MiB / ~3.6% headroom) — no OOM occurred, but this is
even tighter than the ~4% headroom already flagged in the M1 report for MERaLiON alone, since M2
now holds both models in VRAM simultaneously. Combined with M1's existing headroom warning, this
is a real risk for a slightly longer/noisier clip or any concurrent GPU usage — worth the
implementer's attention before scaling up input duration or running M2 alongside anything else on
this GPU.

`samples/multi_speaker_06-09.wav`/`.m4a` was confirmed present but not run — all 6 checklist items
were already satisfiable from `mixed_language_31-34.m4a`/`.wav` plus the extracted single-speaker
window, and re-running the full pipeline against a second 3-minute clip was not required by
VERIFICATION.md and would have added GPU load without new verification value given the ~3.6%
headroom margin already observed.

M3, M4 were explicitly out of scope for this run and are unimplemented — not evaluated here.
