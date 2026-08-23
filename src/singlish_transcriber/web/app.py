"""M4: FastAPI app to list meetings, view transcripts, and label speakers.

Ingestion is CLI-only (see cli.py's `ingest` command) - this app only reads and labels
meetings that already exist in the database.
"""

import mimetypes
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from singlish_transcriber import storage

app = FastAPI(title="singlish-transcriber")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _db_path() -> str:
    return os.environ.get("SINGLISH_TRANSCRIBER_DB", str(storage.DEFAULT_DB_PATH))


class RenameSpeakerRequest(BaseModel):
    display_name: str


@app.get("/", response_class=HTMLResponse)
def meetings_list(request: Request):
    conn = storage.get_connection(_db_path())
    try:
        meetings = storage.list_meetings(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "meetings.html", {"meetings": meetings}
    )


@app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(request: Request, meeting_id: int):
    conn = storage.get_connection(_db_path())
    try:
        meeting = storage.get_meeting_transcript(conn, meeting_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "meeting_detail.html", {"meeting": meeting}
    )


@app.get("/meetings/{meeting_id}/audio")
def meeting_audio(meeting_id: int):
    conn = storage.get_connection(_db_path())
    try:
        meeting = storage.get_meeting_transcript(conn, meeting_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    finally:
        conn.close()

    path = meeting["filename"]
    if not Path(path).is_file():
        raise HTTPException(
            status_code=404, detail=f"audio file no longer exists at {path!r}"
        )
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@app.patch("/api/meetings/{meeting_id}/speakers/{label}")
def rename_speaker(meeting_id: int, label: str, body: RenameSpeakerRequest):
    conn = storage.get_connection(_db_path())
    try:
        updated = storage.rename_speaker(conn, meeting_id, label, body.display_name)
    finally:
        conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="speaker not found")
    return {"ok": True}
