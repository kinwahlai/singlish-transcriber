.DEFAULT_GOAL := help

.PHONY: help label open ingest list show diarize transcribe lint test sync

help:
	@echo "singlish-transcriber:"
	@echo ""
	@echo "  make label FILE=path/to/recording.m4a   Transcribe + label a NEW meeting (re-runs the full pipeline)"
	@echo "                                           (warns + asks first if that file was already ingested; add YES=1 to skip)"
	@echo "  make open ID=1                          Reopen an ALREADY-ingested meeting in your browser (no re-processing)"
	@echo "  make ingest FILE=path                   Same as label, but doesn't open the browser"
	@echo "  make list                               List stored meetings and their ids"
	@echo "  make show ID=1                          Print a stored meeting's transcript"
	@echo "  make diarize FILE=path                  Test diarization on a clip without saving it"
	@echo "  make transcribe FILE=path               Quick ASR-only sanity check, no speaker splitting"
	@echo ""
	@echo "  make lint                               Run ruff"
	@echo "  make test                               Run pytest"
	@echo "  make sync                               Install/update dependencies"

label:
ifndef FILE
	$(error Usage: make label FILE=path/to/recording.m4a)
endif
	uv run singlish-transcriber label $(FILE) $(if $(YES),--yes)

open:
ifndef ID
	$(error Usage: make open ID=1)
endif
	uv run singlish-transcriber open $(ID)

ingest:
ifndef FILE
	$(error Usage: make ingest FILE=path/to/recording.m4a)
endif
	uv run singlish-transcriber ingest $(FILE) $(if $(YES),--yes)

list:
	uv run singlish-transcriber list

show:
ifndef ID
	$(error Usage: make show ID=1)
endif
	uv run singlish-transcriber show $(ID)

diarize:
ifndef FILE
	$(error Usage: make diarize FILE=path/to/recording.m4a)
endif
	uv run singlish-transcriber diarize $(FILE)

transcribe:
ifndef FILE
	$(error Usage: make transcribe FILE=path/to/recording.m4a)
endif
	uv run singlish-transcriber transcribe $(FILE)

lint:
	uv run ruff check .

test:
	uv run pytest

sync:
	uv sync
