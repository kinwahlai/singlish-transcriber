"""Audio preprocessing: normalize arbitrary input formats to 16kHz mono WAV via ffmpeg."""

import subprocess
import tempfile
from pathlib import Path


class AudioConversionError(Exception):
    pass


def to_wav16k_mono(input_path: str) -> str:
    """Convert any ffmpeg-readable audio file to a 16kHz mono WAV, returning the temp file path.

    Raises FileNotFoundError if input_path doesn't exist, AudioConversionError if ffmpeg fails.
    """
    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"audio file not found: {input_path}")

    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="singlish_transcriber_")
    import os

    os.close(fd)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(src),
            "-ar", "16000",
            "-ac", "1",
            out_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        Path(out_path).unlink(missing_ok=True)
        raise AudioConversionError(
            f"ffmpeg failed to convert {input_path!r} (exit {result.returncode}):\n"
            f"{result.stderr.strip()[-2000:]}"
        )
    return out_path
