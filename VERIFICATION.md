# singlish-transcriber — Verification Rubric

This file is the contract between the implementer and the `verifier` subagent (see
`.claude/agents/verifier.md`). Every item below must be checked by actually running the project —
not by reading the code and reasoning that it should work. Reading code tells you what was
*intended*; running it tells you what *happens*.

**Policy for whoever is implementing (see also CLAUDE.md):**
1. Implement a milestone.
2. Run the cheap checks yourself: `uv run ruff check .`, `uv sync`, `uv run pytest`.
3. Invoke the `verifier` subagent with the milestone number and this file.
4. If it reports any ✗, fix the specific failure and re-invoke the verifier. Repeat up to 3 times.
5. If still failing after 3 attempts, stop and report to the human with the verifier's actual
   report attached — do not keep looping silently, and do not report success anyway.

**Policy for the verifier subagent:**
- You did not write this code. Approach it the way a skeptical QA reviewer would, not the way its
  author would. Your job is to find out what's actually true, not to confirm what's claimed.
- For every item, actually perform the action and report the observed result. "Should work based
  on the code" is not a pass.
- Capture evidence at each ✓/✗ decision point and save it to `verification-evidence/`. Name files
  `M<milestone>-<criterion-slug>.<ext>` (screenshot for a UI, captured stdout/response for
  everything else).
- Produce `VERIFICATION_REPORT.md` at the end: one line per criterion, ✓ or ✗, with the evidence
  filename and a one-sentence note on what you actually observed.
- If a criterion can't be checked for a reason unrelated to the feature (e.g. install itself
  fails), report that plainly as a blocker — don't mark surrounding items ✓ by assumption.

---

## M0 — Environment & ASR feasibility spike

Already validated manually during the spec interview (see SPEC.md §5). No formal rubric needed —
this was exploratory, not a deliverable milestone. Evidence lives in `spike/transcribe_spike.py`
and the session transcript: MERaLiON loaded (~6.6GB VRAM), transcribed a real 3-minute
English/Mandarin/Singlish excerpt correctly, peaked at ~8.15GB VRAM regardless of clip length.

## M1 — CLI single-file transcription

- [ ] Run the CLI against `samples/mixed_language_31-34.m4a` (or equivalent) and confirm exit
      code 0 and a non-empty transcript printed to stdout containing recognizable English and
      Mandarin text (not garbled/empty output).
- [ ] Run the CLI against a `.wav` file directly and confirm it also succeeds — exercises the
      path that skips ffmpeg conversion, not just the m4a-conversion path.
- [ ] Run the CLI against a nonexistent file path and confirm it exits non-zero with a clear,
      specific error message — not a raw stack trace dump or silent empty output.
- [ ] Run the CLI against a genuinely silent audio clip (e.g. re-derive one from the original
      silent `Recording.m4a` discovered during the spike, or synthesize one with
      `ffmpeg -f lavfi -i anullsrc`) and confirm it exits 0 with an empty/`(nospeech)` result
      rather than crashing.
- [ ] While the CLI is transcribing a multi-minute clip, check `nvidia-smi` (or the tool's own
      logged peak) and confirm GPU memory stays under 8GB on the RTX 4070.

## M2 — Diarization + merged transcript

- [ ] Run the pipeline against `samples/mixed_language_31-34.m4a` and confirm the output is a
      JSON array of turns, each with `start`, `end`, `speaker_id`, and `text` fields, and that
      `start < end` holds for every turn.
- [ ] Confirm turns are ordered by `start` time.
- [ ] Confirm at least 2 distinct `speaker_id` values appear in the output — cross-check by
      listening to the source clip and confirming it does in fact have multiple speakers talking
      in that window.
- [ ] Spot-check the merged text for at least one turn containing code-switched content against
      the known-good M0/M1 whole-file transcript, and confirm the per-segment diarized ASR didn't
      visibly degrade quality (e.g. cutting a sentence mid-code-switch and losing context).
- [ ] Extract a short single-speaker-only clip from the source recording, run it through the
      pipeline, and confirm only 1 `speaker_id` appears (no spurious over-splitting of one
      speaker into multiple IDs).
- [ ] Confirm the pipeline handles a diarized segment shorter than ~0.5s (a brief interjection)
      without crashing.
- [ ] (added post-implementation — real recordings showed pyannote's segmentation model can
      confidently misclassify multi-second stretches of real speech as silence, dropping whole
      sentences with no diarized turn at all) Confirm undiarized gaps of >=`MIN_GAP_SECONDS` are
      ASR'd as a backstop and, if they contain real speech, appear in the output as a turn;
      confirm gaps that are genuine silence/noise are NOT added (no spurious turns from
      background noise); confirm a recovered gap bordered by the *same* diarized speaker on both
      sides is attributed to that speaker (not `SPEAKER_UNKNOWN`) — this is what keeps the
      single-speaker-clip item above passing even when the backstop recovers a short
      interjection — and confirm a gap bordered by two *different* speakers (or at the very
      start/end of the recording) falls back to `speaker_id == "SPEAKER_UNKNOWN"`.

## M3 — Persistence

- [ ] Run the ingest command against a sample recording, then query the SQLite file directly
      (`sqlite3 <db> "select * from meetings"`, etc.) and confirm a `meetings` row, at least one
      `speakers` row, and multiple `turns` rows were created with sensible values.
- [ ] Run the retrieval command for that meeting's id and confirm it reconstructs the same
      transcript (start/end/speaker/text per turn) that was ingested.
- [ ] Restart the process entirely (kill and re-run, not just re-call a function in the same
      process) and confirm the previously ingested meeting is still retrievable — this is the
      actual persistence check, not just in-memory state surviving.
- [ ] Ingest the same file a second time and confirm the tool behaves sensibly (either a distinct
      new meeting row, or an explicit, intentional dedupe/overwrite) rather than crashing or
      silently corrupting existing rows.

## M4 — Speaker-labeling web UI

- [ ] Start the FastAPI app and confirm the meetings list page loads and shows at least one
      previously ingested meeting.
- [ ] Open that meeting and confirm the page shows an audio player and the transcript text,
      turn by turn.
- [ ] Click a speaker's placeholder label (e.g. "Speaker 1"), rename it, save, and confirm every
      turn belonging to that speaker in the transcript now shows the new name — not just the one
      turn that was clicked.
- [ ] Reload the page (a real browser reload, not a client-side re-render) and confirm the
      renamed speaker label is still shown — i.e. it round-tripped through SQLite, not just
      in-memory/JS state.
- [ ] Click on a transcript turn and confirm the audio player seeks to approximately that turn's
      `start_seconds` (playback-sync check).
- [ ] (added post-implementation, per user feedback) Confirm the meeting detail page shows a
      vertical speakers panel listing every distinct speaker in the meeting, with a count of how
      many are named vs. still on their placeholder label; renaming a speaker (from either the
      inline transcript label or the panel itself) updates the panel immediately without a page
      reload.
- [ ] (added post-implementation, per user feedback) Confirm an "Export transcript" button on the
      meeting detail page downloads a text file of the full transcript (timestamp, current
      speaker name, text per turn) immediately, with no server round-trip/loading wait.
- [ ] (added post-implementation, per user feedback) Confirm clicking a transcript turn both
      seeks the audio player to that turn's start AND starts playback (not just seeking, as the
      original playback-sync item above only required). Confirm the reverse direction too:
      during playback, the transcript line currently being spoken is visually highlighted, and
      the page auto-scrolls to keep it in view as playback moves past the visible turns — check
      with a turn far enough down the page that it starts off-screen.
- [ ] (added post-implementation, per user feedback — the first version of auto-follow fought
      the user's own scrolling, making it impossible to scroll away, e.g. to reach the player
      controls) Confirm the audio player/toolbar stay reachable at all times regardless of
      transcript scroll position (sticky). Confirm that manually scrolling the page during
      playback suspends auto-follow (no further forced scrolling as playback advances) and shows
      a "Resume following" control; confirm clicking it re-enables auto-follow and scrolls back
      to the currently-playing turn. Confirm auto-follow's own scrolling does NOT itself trip
      this suspend behavior (i.e. it doesn't mistake its own scroll for a manual one) — check
      with a turn far enough away that the auto-scroll takes a while to complete.
