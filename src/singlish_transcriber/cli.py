import argparse
import json
import sys
from pathlib import Path

from singlish_transcriber import asr, audio, storage


def cmd_transcribe(args: argparse.Namespace) -> int:
    wav_path = None
    try:
        wav_path = audio.to_wav16k_mono(args.audio_path)
        text = asr.transcribe(wav_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except audio.AudioConversionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if wav_path is not None:
            Path(wav_path).unlink(missing_ok=True)

    print(text)
    return 0


def cmd_diarize(args: argparse.Namespace) -> int:
    from singlish_transcriber import diarize as diarize_mod
    from singlish_transcriber import pipeline

    try:
        turns = pipeline.transcribe_with_speakers(args.audio_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (audio.AudioConversionError, diarize_mod.MissingHFTokenError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(turns, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from singlish_transcriber import diarize as diarize_mod
    from singlish_transcriber import pipeline

    try:
        turns = pipeline.transcribe_with_speakers(args.audio_path)
        duration = audio.get_duration_seconds(args.audio_path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (audio.AudioConversionError, diarize_mod.MissingHFTokenError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    conn = storage.get_connection(args.db)
    try:
        meeting_id = storage.ingest_meeting(conn, args.audio_path, duration, turns)
    finally:
        conn.close()

    print(meeting_id)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    conn = storage.get_connection(args.db)
    try:
        transcript = storage.get_meeting_transcript(conn, args.meeting_id)
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(json.dumps(transcript, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="singlish-transcriber")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser(
        "transcribe", help="Transcribe a single audio file to plain text."
    )
    transcribe_parser.add_argument("audio_path", help="Path to an audio file (m4a/mp3/wav/...).")
    transcribe_parser.set_defaults(func=cmd_transcribe)

    diarize_parser = subparsers.add_parser(
        "diarize",
        help="Transcribe with speaker diarization, printing a JSON list of turns.",
    )
    diarize_parser.add_argument("audio_path", help="Path to an audio file (m4a/mp3/wav/...).")
    diarize_parser.set_defaults(func=cmd_diarize)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Diarize + transcribe a recording and store it, printing the new meeting id.",
    )
    ingest_parser.add_argument("audio_path", help="Path to an audio file (m4a/mp3/wav/...).")
    ingest_parser.add_argument(
        "--db", default=storage.DEFAULT_DB_PATH, help="Path to the SQLite database file."
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    show_parser = subparsers.add_parser(
        "show", help="Print a stored meeting's transcript as JSON."
    )
    show_parser.add_argument("meeting_id", type=int)
    show_parser.add_argument(
        "--db", default=storage.DEFAULT_DB_PATH, help="Path to the SQLite database file."
    )
    show_parser.set_defaults(func=cmd_show)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
