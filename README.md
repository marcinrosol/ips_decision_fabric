# IPS Decision Fabric

An agentic decision-support system for a pyrotechnics/energetics research
lab: a live chemical inventory (SQLite) and a searchable, cited corpus of
~50 International Pyrotechnics Seminar proceedings (1968-2022) get reasoned
over jointly by a local LLM, which drafts purchase orders and experiment
schedules for a human to review.

See `CLAUDE.md` for the full architecture writeup.

## Prerequisites

- Windows, with Python 3.11+ on `PATH`.
- An NVIDIA GPU is optional but strongly recommended -- setup picks a
  smaller local model automatically if one isn't found (see below), but
  quality and speed both drop with model size.
- The IPS proceedings PDF corpus (`data/corpus/*.pdf`) is **not included in
  this repository** (too large, and largely not ours to redistribute) --
  supply it separately before running the ingestion pipeline. `data/corpus/`
  is otherwise expected to also contain `IPS-TOC-1968-2013.pdf` (the master
  table of contents, used for article-level citations).

## Setup

```
python scripts/setup.py
```

One command, safe to re-run. It installs Python dependencies
(`requirements.txt`), installs Tesseract OCR and Ollama if either is
missing, detects available GPU VRAM, and pulls a locally-run model sized to
fit (`qwen2.5:72b` down to `qwen2.5:7b` depending on what's available --
see `scripts/setup.py` for the exact tiers). The chosen model is recorded in
`agents/model.txt` and used by both the MCP server and the agent loop.

## Running it

```
python data/inventory/seed.py     # (re)build the inventory DB from schema + seed data
python -m simulation.run          # advance the live sim clock, deplete stock, progress POs
python -m pipeline.run            # ingest data/corpus/*.pdf into the vector store (one-time, slow)
python -m pipeline.backfill_articles   # add article-level citations on top
python -m dashboard.app           # localhost:5000 -- inventory, chat with the agent, review queue
```

The dashboard is the main entry point day to day: it shows live inventory,
a chat panel for asking the agent formulation questions, and a review panel
for approving/rejecting whatever it drafts.

## Running with Docker

Containerizes the dashboard, the simulation engine, and the agent/MCP chat
layer. The PDF ingestion pipeline (`pipeline.run`/`backfill_articles`) stays
a native, one-time step -- run it on the host first so `data/vector_store/`
exists to mount in. Ollama itself also stays native (it's already set up
with a GPU-sized model per `scripts/setup.py`) -- the containers connect to
it remotely rather than duplicating a many-GB model download.

**Prerequisite: make Ollama reachable from the container.** Ollama binds to
`127.0.0.1` by default, which containers can't reach even via
`host.docker.internal`. Set `OLLAMA_HOST=0.0.0.0` as a **Windows System**
environment variable, then fully quit and restart Ollama (tray icon quit,
not just closing a window). Confirm with `curl http://localhost:11434/api/tags`
from the host afterward.

```
docker compose build
docker compose run --rm dashboard python data/inventory/seed.py   # one-off, (re)builds the DB
docker compose up -d
```

The dashboard is then at `http://localhost:5000`, same as running natively.
Both services share `data/inventory/` (bind-mounted, WAL mode handles the
concurrent writer/reader) and read `data/vector_store/` read-only. To point
at a different pulled model, change `OLLAMA_MODEL` in `docker-compose.yml`.
