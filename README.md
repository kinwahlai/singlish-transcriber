# singlish-transcriber

A local tool to transcribe multi-speaker, multi-language (English/Mandarin/Malay/Singlish,
including mid-sentence code-switching) meeting recordings, diarize who spoke when, and label
speakers with real names in a browser. See `SPEC.md` for the full design and milestone plan.

## One-time setup

1. `uv sync` — installs everything, including MERaLiON-3-3B-ASR and pyannote.audio.
2. Diarization (`diarize`, `ingest`, `label`) needs a Hugging Face account and token:
   - Accept the license on **[pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)**,
     **[pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)**, and
     **[pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)**
     (all three are gated dependencies of the diarization pipeline).
   - Run `uv run hf auth login` and paste a read-only token from
     [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). (If the login
     prompt fails with a terminal/`getpass` error, set the `HF_TOKEN` environment variable
     instead — either works.)

Plain `transcribe` (no diarization) doesn't need any of this — MERaLiON-3-3B-ASR isn't gated.

## Quick start: transcribe and label a meeting

```
make label FILE=path/to/recording.m4a
```

(or `uv run singlish-transcriber label path/to/recording.m4a` if you'd rather not use `make`.)

This does everything in one go: diarizes + transcribes the recording, stores it as a **new**
meeting, starts the web server in the background if it isn't already running, and opens your
browser straight to that meeting's page so you can rename "Speaker 1" / "Speaker 2" to real
names. Takes roughly a minute of processing per few minutes of audio — for anything more than a
few minutes long, expect it to take a while, and it prints progress as it works rather than
hanging silently. Renaming a speaker in the browser applies to every turn for that speaker in
that meeting, and is saved immediately.

**Important:** `label`/`ingest` always re-run the full pipeline and create a brand-new meeting,
even for a file you've already processed before — they never silently skip ahead. If a file's
already been ingested, they'll warn you and ask before proceeding (add `--yes` / `make ... YES=1`
to skip the prompt). If you just want to reopen something you already ingested, use
`make open ID=<id>` instead (see below) rather than re-ingesting.

Run `label` again on another recording later and it reuses the same background server rather than
starting a new one.

## Command reference

Every command accepts `m4a`, `mp3`, `wav`, or anything else `ffmpeg` can read. Each has a
matching `make <name> FILE=... / ID=...` shortcut — run `make` with no arguments to see them all.

### `label <audio_path> [--db PATH] [--host HOST] [--port PORT]`
The everyday command for a **new** recording — see Quick Start above. Combines `ingest` +
starting the web server + opening your browser to the newly created meeting.

### `open <meeting_id> [--db PATH] [--host HOST] [--port PORT]`
Reopens an **already-ingested** meeting in your browser — starts the server if needed, but does
no re-processing. Use this instead of `label` once a recording has already been ingested; look up
its id with `list` first if you don't remember it.

### `ingest <audio_path> [--db PATH]`
Same as `label`, minus opening the browser — diarizes, transcribes, and stores a recording,
printing the new integer meeting id. Handy for batch-ingesting several recordings before
reviewing any of them (follow up with `open <id>` on each once you're ready).

### `list [--db PATH]`
Lists every stored meeting with its id, duration, and filename — this is how you find the id to
pass to `show` or `open`.

### `show <meeting_id> [--db PATH]`
Prints a previously stored meeting's transcript as JSON (speaker labels/names, timestamps, text).
Useful for scripting or a quick terminal check without opening the browser.

### `diarize <audio_path>`
Runs diarization + transcription and prints the result as JSON directly to stdout — no storage.
Useful for testing pipeline quality on a clip without committing it to the database.

### `transcribe <audio_path>`
Plain speech-to-text, no speaker separation, no storage — just MERaLiON's transcript as text.
The simplest command; good for a quick sanity check that a file's audio is even readable, or for
a single-speaker recording where diarization wouldn't add anything.

`--db` on any command defaults to `~/.local/share/singlish-transcriber/db.sqlite` if omitted.

## The web UI (started automatically by `label`)

Can also be started manually: `uv run uvicorn singlish_transcriber.web.app:app --port 8420`
(set `SINGLISH_TRANSCRIBER_DB=<path>` first if you're not using the default database location).

- `/` — list of every ingested meeting.
- `/meetings/<id>` — that meeting's transcript, with an audio player synced to it. Click a turn's
  text to jump the player to that moment; click a speaker label to rename it (Enter to save,
  Escape to cancel) — the new name applies to every turn for that speaker.

Ingestion itself only happens via the CLI (`ingest` or `label`) — the web UI is view/label only.
Server logs (if something looks wrong) go to `~/.local/share/singlish-transcriber/web.log`.

## Privacy

Recordings and transcripts are real client meeting content. Everything stays local — nothing in
`samples/`, ingested recordings, database files, or verification evidence is committed to git
(see `.gitignore`), and none of it should be pushed to a remote/shared repo without a deliberate
decision to do so.
