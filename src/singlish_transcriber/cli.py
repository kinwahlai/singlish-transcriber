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


def _ingest(audio_path: str, db_path: str) -> int:
    """Diarize + transcribe + store one file. Returns the new meeting id.

    Lets FileNotFoundError / AudioConversionError / MissingHFTokenError propagate so
    callers can report them consistently.
    """
    from singlish_transcriber import pipeline

    turns = pipeline.transcribe_with_speakers(audio_path)
    duration = audio.get_duration_seconds(audio_path)
    conn = storage.get_connection(db_path)
    try:
        return storage.ingest_meeting(conn, audio_path, duration, turns)
    finally:
        conn.close()


def cmd_ingest(args: argparse.Namespace) -> int:
    from singlish_transcriber import diarize as diarize_mod

    try:
        meeting_id = _ingest(args.audio_path, args.db)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (audio.AudioConversionError, diarize_mod.MissingHFTokenError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(meeting_id)
    return 0


def _serve_and_open(host: str, port: str | int, db_path: str, meeting_id: int) -> int:
    from singlish_transcriber import server

    try:
        server.ensure_server_running(host, port, db_path)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    url = f"http://{host}:{port}/meetings/{meeting_id}"
    print(f"Opening {url}")
    server.open_url(url)
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    from singlish_transcriber import diarize as diarize_mod

    print(f"Ingesting {args.audio_path} (roughly a minute per few minutes of audio)...")
    try:
        meeting_id = _ingest(args.audio_path, args.db)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (audio.AudioConversionError, diarize_mod.MissingHFTokenError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Stored as meeting {meeting_id}.")

    return _serve_and_open(args.host, args.port, args.db, meeting_id)


def cmd_open(args: argparse.Namespace) -> int:
    conn = storage.get_connection(args.db)
    try:
        storage.get_meeting_transcript(conn, args.meeting_id)  # raises KeyError if missing
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    return _serve_and_open(args.host, args.port, args.db, args.meeting_id)


def cmd_list(args: argparse.Namespace) -> int:
    conn = storage.get_connection(args.db)
    try:
        meetings = storage.list_meetings(conn)
    finally:
        conn.close()

    if not meetings:
        print("No meetings ingested yet. Run `ingest` or `label` on a recording first.")
        return 0

    print(f"{'id':<4} {'duration':>9}  {'created_at':<26} filename")
    for m in meetings:
        print(
            f"{m['id']:<4} {m['duration_seconds']:>8.0f}s  {m['created_at']:<26} {m['filename']}"
        )
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

    label_parser = subparsers.add_parser(
        "label",
        help="Ingest a recording, start the web server if needed, and open it in your "
        "browser for speaker labeling.",
    )
    label_parser.add_argument("audio_path", help="Path to an audio file (m4a/mp3/wav/...).")
    label_parser.add_argument(
        "--db", default=storage.DEFAULT_DB_PATH, help="Path to the SQLite database file."
    )
    label_parser.add_argument("--host", default="127.0.0.1", help="Web server host.")
    label_parser.add_argument("--port", type=int, default=8420, help="Web server port.")
    label_parser.set_defaults(func=cmd_label)

    open_parser = subparsers.add_parser(
        "open",
        help="Open an already-ingested meeting in your browser (no re-processing).",
    )
    open_parser.add_argument("meeting_id", type=int)
    open_parser.add_argument(
        "--db", default=storage.DEFAULT_DB_PATH, help="Path to the SQLite database file."
    )
    open_parser.add_argument("--host", default="127.0.0.1", help="Web server host.")
    open_parser.add_argument("--port", type=int, default=8420, help="Web server port.")
    open_parser.set_defaults(func=cmd_open)

    list_parser = subparsers.add_parser(
        "list", help="List stored meetings with their ids."
    )
    list_parser.add_argument(
        "--db", default=storage.DEFAULT_DB_PATH, help="Path to the SQLite database file."
    )
    list_parser.set_defaults(func=cmd_list)

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
