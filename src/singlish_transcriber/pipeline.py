"""M2: preprocess -> diarize -> per-turn ASR -> merged, timestamped, speaker-labeled transcript."""

import sys
from pathlib import Path

import soundfile as sf

from singlish_transcriber import asr, audio
from singlish_transcriber import diarize as diarize_mod

MERGE_GAP_SECONDS = 0.3

# pyannote's segmentation model occasionally classifies real speech as silence with high
# confidence over multi-second stretches (confirmed by direct inspection: a dedicated VAD pass
# with the same model shows the same gaps, so this isn't a tunable threshold issue - the model's
# per-frame decision is just wrong there). MIN_GAP_SECONDS controls how large an undiarized gap
# has to be before we treat it as a candidate for missed speech and ASR it directly as a backstop.
MIN_GAP_SECONDS = 0.75
UNKNOWN_SPEAKER = "SPEAKER_UNKNOWN"


def _merge_adjacent(
    turns: list[tuple[float, float, str]],
) -> list[tuple[float, float, str]]:
    """Merge consecutive turns from the same speaker separated by a short gap.

    Raw diarization output is often fragmented into many short same-speaker turns;
    merging them produces more usable ASR input without losing genuine speaker changes.
    """
    if not turns:
        return []
    merged = [list(turns[0])]
    for start, end, speaker in turns[1:]:
        last = merged[-1]
        if speaker == last[2] and start - last[1] <= MERGE_GAP_SECONDS:
            last[1] = end
        else:
            merged.append([start, end, speaker])
    return [(t[0], t[1], t[2]) for t in merged]


def _find_gaps(
    turns: list[tuple[float, float, str]], total_duration: float
) -> list[tuple[float, float, str | None, str | None]]:
    """Find stretches of the recording with no diarized turn at all, long enough to plausibly
    contain speech the diarizer missed. Each gap carries the speaker diarized immediately before
    and after it (None at the very start/end of the recording), so a recovered gap bordered by
    the same speaker on both sides can be attributed to them instead of an unknown speaker.
    """
    gaps = []
    cursor = 0.0
    prev_speaker = None
    for start, end, speaker in turns:
        if start - cursor >= MIN_GAP_SECONDS:
            gaps.append((cursor, start, prev_speaker, speaker))
        cursor = max(cursor, end)
        prev_speaker = speaker
    if total_duration - cursor >= MIN_GAP_SECONDS:
        gaps.append((cursor, total_duration, prev_speaker, None))
    return gaps


def _transcribe_gaps(gaps, samples, sample_rate: int) -> list[dict]:
    """ASR every undiarized gap as a backstop against missed speech, keeping only the ones that
    actually contain speech (MERaLiON returns "(nospeech)" or empty text for true silence/noise).
    A gap bordered by the same speaker on both sides is attributed to that speaker; otherwise
    (a genuine speaker change, or the very start/end of the recording) it's attributed to an
    unknown speaker, since diarization never saw this audio.
    """
    results = []
    for start, end, speaker_before, speaker_after in gaps:
        i, j = int(start * sample_rate), int(end * sample_rate)
        try:
            text = asr.transcribe_array(samples[i:j], sample_rate).strip()
        except Exception as e:  # noqa: BLE001 - one bad segment must not kill the run
            print(
                f"warning: backstop ASR failed for gap {start:.2f}-{end:.2f}s: {e}",
                file=sys.stderr,
            )
            continue
        if text and text != "(nospeech)":
            speaker_id = (
                speaker_before
                if speaker_before is not None and speaker_before == speaker_after
                else UNKNOWN_SPEAKER
            )
            results.append({"start": start, "end": end, "speaker_id": speaker_id, "text": text})
    return results


def transcribe_with_speakers(input_path: str) -> list[dict]:
    """Run the full M2 pipeline on one audio file, returning a list of
    {start, end, speaker_id, text} turns ordered by start time.
    """
    wav_path = audio.to_wav16k_mono(input_path)
    try:
        print("Diarizing (can take a few minutes for a long recording)...", file=sys.stderr)
        turns = _merge_adjacent(diarize_mod.diarize(wav_path))
        samples, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)

        print(f"Found {len(turns)} speaker turns. Transcribing...", file=sys.stderr)
        texts = []
        progress_step = max(1, len(turns) // 20)  # ~20 updates regardless of turn count
        for idx, (start, end, _speaker) in enumerate(turns):
            i, j = int(start * sample_rate), int(end * sample_rate)
            if j <= i:
                texts.append("")
            else:
                try:
                    texts.append(asr.transcribe_array(samples[i:j], sample_rate))
                except Exception as e:  # noqa: BLE001 - one bad segment must not kill the run
                    print(
                        f"warning: ASR failed for segment {start:.2f}-{end:.2f}s: {e}",
                        file=sys.stderr,
                    )
                    texts.append("")
            if (idx + 1) % progress_step == 0 or idx + 1 == len(turns):
                print(f"  transcribed {idx + 1}/{len(turns)} turns", file=sys.stderr)

        diarized_results = [
            {"start": start, "end": end, "speaker_id": speaker, "text": text}
            for (start, end, speaker), text in zip(turns, texts)
        ]

        total_duration = len(samples) / sample_rate
        gaps = _find_gaps(turns, total_duration)
        if gaps:
            print(
                f"Checking {len(gaps)} undiarized gap(s) for speech the diarizer missed...",
                file=sys.stderr,
            )
            backstop_results = _transcribe_gaps(gaps, samples, sample_rate)
            if backstop_results:
                print(
                    f"  recovered speech in {len(backstop_results)} gap(s)", file=sys.stderr
                )
        else:
            backstop_results = []
    finally:
        Path(wav_path).unlink(missing_ok=True)

    return sorted(diarized_results + backstop_results, key=lambda t: t["start"])
