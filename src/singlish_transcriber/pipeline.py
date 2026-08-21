"""M2: preprocess -> diarize -> per-turn ASR -> merged, timestamped, speaker-labeled transcript."""

import sys
from pathlib import Path

import soundfile as sf

from singlish_transcriber import asr, audio
from singlish_transcriber import diarize as diarize_mod

MERGE_GAP_SECONDS = 0.3


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


def transcribe_with_speakers(input_path: str) -> list[dict]:
    """Run the full M2 pipeline on one audio file, returning a list of
    {start, end, speaker_id, text} turns ordered by start time.
    """
    wav_path = audio.to_wav16k_mono(input_path)
    try:
        turns = _merge_adjacent(diarize_mod.diarize(wav_path))
        samples, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)

        texts = []
        for start, end, _speaker in turns:
            i, j = int(start * sample_rate), int(end * sample_rate)
            if j <= i:
                texts.append("")
                continue
            try:
                texts.append(asr.transcribe_array(samples[i:j], sample_rate))
            except Exception as e:  # noqa: BLE001 - one bad segment must not kill the run
                print(
                    f"warning: ASR failed for segment {start:.2f}-{end:.2f}s: {e}",
                    file=sys.stderr,
                )
                texts.append("")
    finally:
        Path(wav_path).unlink(missing_ok=True)

    return [
        {"start": start, "end": end, "speaker_id": speaker, "text": text}
        for (start, end, speaker), text in zip(turns, texts)
    ]
