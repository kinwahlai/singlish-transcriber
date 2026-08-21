"""Phase 0 spike: does MERaLiON-3-3B-ASR load and transcribe on this GPU, and how well?

Usage: uv run python spike/transcribe_spike.py <path-to-audio-file>
"""

import sys
import time

import torch
from meralion_3_asr import Meralion3ASR


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-audio-file>")
        sys.exit(1)

    audio_path = sys.argv[1]

    print("loading MERaLiON-3-3B-ASR (transformers backend)...")
    load_start = time.time()
    model = Meralion3ASR.from_pretrained(
        "MERaLiON/MERaLiON-3-3B-ASR", backend="transformers"
    )
    print(f"loaded in {time.time() - load_start:.1f}s")

    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.memory_reserved() / 1e9
        print(f"GPU memory after load: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved")

    print(f"transcribing {audio_path}...")
    transcribe_start = time.time()
    text = model.transcribe(audio_path)
    elapsed = time.time() - transcribe_start
    print(f"transcribed in {elapsed:.1f}s")

    if torch.cuda.is_available():
        peak = torch.cuda.max_memory_allocated() / 1e9
        print(f"peak GPU memory allocated: {peak:.2f} GB")

    print("\n--- transcript ---")
    print(text)


if __name__ == "__main__":
    main()
