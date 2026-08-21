"""MERaLiON-3-3B-ASR wrapper. Lazily loads the model once per process."""

from meralion_3_asr import Meralion3ASR

_model: Meralion3ASR | None = None


def _get_model() -> Meralion3ASR:
    global _model
    if _model is None:
        _model = Meralion3ASR.from_pretrained(
            "MERaLiON/MERaLiON-3-3B-ASR", backend="transformers"
        )
    return _model


def transcribe(wav_path: str) -> str:
    """Transcribe a 16kHz mono WAV file. Returns the transcript text (may be empty for silence)."""
    return _get_model().transcribe(wav_path)


def transcribe_array(samples, sample_rate: int) -> str:
    """Transcribe an in-memory mono float32 waveform slice."""
    return _get_model().transcribe((samples, sample_rate))
