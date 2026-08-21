"""pyannote.audio speaker diarization wrapper."""

import os

import soundfile as sf
import torch
from pyannote.audio import Pipeline

_pipeline: Pipeline | None = None


class MissingHFTokenError(Exception):
    pass


def _get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        # Prefer an explicit env var (e.g. for headless/CI use); otherwise fall back to
        # whatever credentials `hf auth login` cached locally.
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or True
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", token=token
            )
        except Exception as e:
            raise MissingHFTokenError(
                "Failed to load pyannote/speaker-diarization-3.1: "
                f"{e}\nSet HF_TOKEN, or run `hf auth login`, with a token that has accepted "
                "the license for both pyannote/speaker-diarization-3.1 and "
                "pyannote/segmentation-3.0 on huggingface.co."
            ) from e
        if pipeline is None:
            raise MissingHFTokenError(
                "pyannote/speaker-diarization-3.1 failed to load — most likely the token "
                "is valid but the license hasn't been accepted for that model or for "
                "pyannote/segmentation-3.0 yet."
            )
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        _pipeline = pipeline
    return _pipeline


def diarize(wav_path: str) -> list[tuple[float, float, str]]:
    """Return (start_seconds, end_seconds, speaker_label) turns for a 16kHz mono WAV file."""
    pipeline = _get_pipeline()
    data, sr = sf.read(wav_path, dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T)  # (channels, frames)
    output = pipeline({"waveform": waveform, "sample_rate": sr})
    # exclusive_speaker_diarization has no overlapping turns, which is what per-turn ASR needs.
    return [
        (segment.start, segment.end, speaker)
        for segment, _, speaker in output.exclusive_speaker_diarization.itertracks(
            yield_label=True
        )
    ]
