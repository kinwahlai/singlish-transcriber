# singlish-transcriber — local multi-speaker, multi-language meeting transcription

**Status:** spec for v1; M0 (feasibility spike) complete
**License:** N/A — private personal/client-work tool, not distributed
**Deployment model:** 100% local, no backend service, no cloud dependency, no multi-user access.
Runs on the developer's MacBook Air (Apple Silicon, 24GB unified memory, MPS/CPU backend) or a
Linux/WSL2 box with an NVIDIA GPU (validated on an RTX 4070 laptop GPU, 8GB VRAM, CUDA 12.8).

## 1. What this is

A local tool to transcribe voice recordings of client meetings held in Singapore, where multiple
people speak and switch between English, Mandarin, Malay, and Singlish (including mid-sentence
code-switching) within the same conversation. v1 produces a speaker-separated, timestamped
transcript from a finished recording. A later phase lets the user relabel the anonymous speaker
IDs with real names.

## 2. Explicit scope (v1)

**In scope:**
- Batch processing of a single finished audio recording (m4a/mp3/wav) after the meeting ends.
- Automatic speech recognition that handles mixed-language, code-switched Singlish speech.
- Speaker diarization (who spoke when), producing placeholder speaker IDs (e.g. "Speaker 1").
- A merged, timestamped transcript (speaker, start, end, text) persisted to local storage.
- A local web UI to play back the meeting audio synced to the transcript and rename speaker IDs
  to real names, with the rename applied across the whole meeting.

**Stretch / post-v1** (build the core first, revisit if there's appetite):
- Translating the transcript into a single target language (today's scope is transcription in
  whatever language was actually spoken, not translation).
- Exporting a transcript (PDF/DOCX/plain text) for sharing outside the tool.
- Cross-meeting search or LLM-generated meeting summaries, enabled by having transcripts in
  SQLite but not built now.
- Remembering a speaker's real name across different meetings (v1 relabels per-meeting only).

**Explicitly out of scope** (call out as future work, don't build now):
- Real-time/live transcription during the meeting — the user explicitly wants post-recording
  processing only; live transcription needs streaming ASR and live diarization, a materially
  different architecture from the batch pipeline already spiked.
- Multi-user access, authentication, or a hosted/shared deployment — this is a single-user local
  tool for the developer's own use; no reason to take on auth or deployment complexity for v1.

## 3. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language/runtime | Python 3.12, managed with `uv` | Already set up and validated during the M0 spike. |
| ASR | `MERaLiON/MERaLiON-3-3B-ASR` via the `meralion-3-asr` package, `backend="transformers"` | AI Singapore/I2R-A*STAR model purpose-built for Singlish and SEA-language code-switching; validated on real meeting audio in M0 (~6.6GB VRAM load, ~6x real-time). |
| Diarization | `pyannote.audio` (`speaker-diarization-3.1`) | Mature, well-supported speaker diarization; requires accepting the model's license on Hugging Face and an `HF_TOKEN` (gated model). |
| Audio preprocessing | `ffmpeg` (system dependency) | Converts arbitrary input formats (m4a, mp3) to the mono 16kHz WAV that the ASR/diarization stack needs; already installed via apt. |
| Storage | SQLite (Python stdlib `sqlite3`) | Chosen over flat JSON files to support future cross-meeting queries; no external DB server needed. |
| Phase-2 UI | FastAPI + plain HTML/JS | Lightweight, full control over audio-playback-synced-to-transcript UX; avoids the constraints of a Python-only UI framework for this specific interaction. |
| Lint | `ruff` | Fast, standard, added via `uv add --dev`. |
| Test | `pytest` | Standard, added via `uv add --dev`. |

## 4. Data model

Refined during M3 implementation; initial shape:

```sql
meetings (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  file_hash TEXT,        -- SHA-256 of the audio content, used to detect re-ingesting the
                          -- same recording under a different path/filename (added post-M3)
  recorded_at TEXT,
  duration_seconds REAL,
  created_at TEXT NOT NULL
)

speakers (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL REFERENCES meetings(id),
  label TEXT NOT NULL,          -- e.g. "Speaker 1", assigned by diarization
  display_name TEXT             -- NULL until the user relabels it in the phase-2 UI
)

turns (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL REFERENCES meetings(id),
  speaker_id INTEGER NOT NULL REFERENCES speakers(id),
  start_seconds REAL NOT NULL,
  end_seconds REAL NOT NULL,
  text TEXT NOT NULL
)
```

## 5. Core features / milestones

Build in this order — each milestone is a working, demoable increment:

**M0 — Environment & ASR feasibility spike** *(complete)*
Confirmed `MERaLiON-3-3B-ASR` loads and runs via the `meralion-3-asr` transformers backend on the
RTX 4070 (8GB VRAM), using ~6.6GB at load and peaking at ~8.15GB during transcription regardless
of clip length (internal 30s chunking keeps memory flat). Confirmed on a real 3-minute excerpt of
mixed English/Mandarin/Singlish meeting audio that technical code-switched speech (HTTP POST,
CRM, EC2, PDF, etc. embedded in Mandarin sentences) transcribes correctly. Also confirmed a real
gotcha: OneDrive Files-On-Demand placeholders can silently read back as all-zero audio over a WSL
`/mnt/c/...` path — worth checking actual sample amplitudes, not just file size, before trusting
an input recording.

**M1 — CLI single-file transcription**
Turn the spike script into a real, reusable CLI/module: given any audio file path (m4a/mp3/wav),
auto-convert via ffmpeg as needed and produce a plain-text transcript via MERaLiON. No diarization
and no storage yet — this milestone is about making the ASR step itself robust (bad input files,
missing files, silent audio) rather than a one-off script.

**M2 — Diarization + merged transcript**
Add `pyannote.audio` diarization to produce speaker turns (start, end, speaker_id), run MERaLiON
per turn, and merge into a structured, timestamped transcript (JSON: array of
`{start, end, speaker_id, text}`). Checkpoint milestone (see §8).

**M3 — Persistence**
Add the SQLite schema above, a command to ingest a recording end-to-end (diarize + transcribe +
store), and a command to retrieve a stored meeting's transcript.

**M4 — Speaker-labeling web UI**
FastAPI app: list stored meetings, open one to see its transcript with audio playback synced to
turns, click a speaker's placeholder label to rename it (applies to every turn for that speaker in
that meeting), persisted back to SQLite. Ingestion is still CLI-only at this point (`ingest` from
M3) — the web UI only views and labels meetings that already exist. Checkpoint milestone (see §8).

**M5 — Browser upload & ingest**
Add upload to the web UI itself, so ingestion no longer requires the terminal: pick/drop an audio
file in the browser, it runs the M3 ingest pipeline (diarize + transcribe + store), and the new
meeting appears in the list. Deliberately deferred past M4 rather than folded into it, since it
adds real scope on top of view/label: a long-running request (diarization + ASR takes on the order
of a minute per few minutes of audio) needs either a background job with progress polling or a
held-open request with a loading state, plus in-browser error handling for bad files. Rubric to be
written (with the user) before this milestone is implemented, per the working policy in CLAUDE.md.

## 6. Non-functional requirements

- **Privacy:** recordings and transcripts contain real client meeting content. Keep local only —
  no pushing `samples/`, recordings, or transcripts to any remote/shared git repo without
  explicit, deliberate decision to do so.
- **Performance:** must process a full-length meeting recording (validated up to ~37 minutes so
  far, expected to scale to 1-2 hours) without exceeding the RTX 4070's 8GB VRAM — MERaLiON's
  internal chunking already validated to keep peak memory flat regardless of clip length.

## 7. Suggested repo structure

```
singlish-transcriber/
  spike/                       # phase-0 exploration script, kept for reference
  samples/                     # short real-audio clips for local testing (never pushed remotely)
  src/
    singlish_transcriber/
      asr.py                   # MERaLiON wrapper (M1)
      diarize.py                # pyannote wrapper (M2)
      pipeline.py               # ffmpeg preprocess + diarize + transcribe + merge (M2)
      storage.py                # SQLite schema + CRUD (M3)
      cli.py                    # command-line entrypoint (M1+)
      web/                      # FastAPI app (M4)
  tests/
  SPEC.md
  VERIFICATION.md
  CLAUDE.md
  pyproject.toml
```

## 8. Handoff note for Claude Code

Suggested first prompt for a new session: "Implement M1 per SPEC.md / VERIFICATION.md."

**Checkpoint milestones** (stop for human review even if the verifier passes everything):
- **M2 — Diarization + merged transcript**: foundational and highest-risk for silent quality
  problems — bad diarization boundaries or ASR-merge logic here poison every milestone after it,
  and transcript quality is inherently subjective in a way an automated verifier can't fully
  judge. Worth listening to a real merged transcript against the source audio before moving on.
- **M4 — Speaker-labeling web UI**: user-facing and interactive; UX quality (does the
  playback-sync actually feel usable) isn't something an automated verifier can fully judge either.
