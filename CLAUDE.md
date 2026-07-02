# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

IPS Decision Fabric is an agentic decision-support system for a pyrotechnics/energetics
research lab. It's designed around two data sources that get reasoned over jointly:

1. **Live inventory state** — a SQLite database (`data/inventory/inventory.db`) tracking
   chemical stock, scheduled experiments, purchase orders, and an audit log of agent
   decisions.
2. **Historical knowledge** — a corpus of ~50 International Pyrotechnics Seminar (IPS)
   proceedings PDFs spanning 1968–2022 (`data/corpus/`), intended to be embedded into a
   vector store and queried separately from the live DB.

The intended interaction model is conversational: a user chats with the IPS proceedings
corpus for formulation guidance (e.g. "what's a stable red star composition using
strontium carbonate?"), and the agent layer cross-references whatever it recommends
against live inventory state and the experiment schedule to turn that guidance into
concrete next steps — scheduling a new `Experiment_Schedule` entry, or issuing a
`Purchase_Order` for chemicals a recommended formulation needs but is low/out of stock on.
Each such recommendation, plus the human reviewer's outcome, gets logged to `Decision_Log`
(citations from the corpus go in `vector_store_citations`, the live numbers it reasoned
over go in `inventory_snapshot_summary`).

## Current state

- **`data/inventory/`** — the data layer (schema + seed data). Working.
- **`simulation/`** — a live simulation engine that advances an accelerated sim clock,
  depleting inventory as experiments run, progressing purchase orders through their
  lifecycle, and injecting stochastic events (supplier delays, recounts, expirations).
  Run with `python -m simulation.run` from the repo root. Working.
- **`pipeline/`** — PDF→vector-store ingestion. Working; the full corpus has been run
  through it. `data/corpus/*.pdf` → per-page text (native, or OCR via Tesseract for the
  ~20 pre-2000 scanned volumes) → chunked → embedded (`sentence-transformers`) → stored in
  a local Chroma collection at `data/vector_store/`. **28,597 chunks**, each citable as
  `"Proc. Nth Int'l Pyrotechnics Seminar (YYYY), pp. X-Y"`. A second pass
  (`master_toc.py`/`articles.py`/`backfill_articles.py`) adds article-level (title +
  author) citations by matching a master table of contents against ingested chunk text —
  covers 29 of 45 seminar volumes at reasonable confidence; 5 volumes were deliberately
  excluded for poor match quality and volumes after 2013 aren't covered by the master TOC
  at all, so those fall back to page-range-only citations (not a bug — a documented
  coverage limit). Re-run via `python -m pipeline.run` (skips already-ingested files) and
  `python -m pipeline.backfill_articles`.
- **`mcp_servers/server.py`** — an MCP server (stdio transport, `FastMCP`) exposing both
  data sources as tools: `search_corpus` (the vector store above), `get_chemical_status` /
  `list_low_stock_chemicals` / `get_experiment_schedule` (read-only inventory queries), and
  `draft_purchase_order` / `draft_experiment_schedule` / `log_decision` (writes — these
  only ever create `Draft`/`Pending` rows; nothing is auto-approved). Working.
- **`agents/`** — the decision agent: a manual tool-calling loop (`loop.py` +
  `mcp_bridge.py`) against a **local model via Ollama** (`qwen2.5:72b`, not the Anthropic
  API — a deliberate choice to avoid per-token billing on top of a Claude subscription;
  Ollama must be running locally with that model pulled). No standalone CLI — it's driven
  from the dashboard's chat panel. Working.
- **`dashboard/`** — a Flask web dashboard (`python -m dashboard.app`, localhost:5000)
  showing live inventory status (color-coded by stock level, with order-status icons),
  current sim time, a live event feed, a chat panel (`/api/chat`) for talking to the
  decision agent, and a "Pending Review" panel surfacing everything awaiting a human
  decision — `Decision_Log` rows, Draft POs, Pending experiments — with
  Approve/Reject/Override actions (`dashboard/actions.py`) that write back to the DB and
  feed the simulation engine's existing lifecycle logic (e.g. approving a Draft PO sets it
  to `Submitted`, which the engine then carries forward on its own). Working.
- `requirements.txt`: Flask, plus the ingestion/agent stack — `pymupdf`, `pytesseract`,
  `Pillow`, `sentence-transformers`, `chromadb`, `mcp`, `ollama`.
- Not currently a git repository — nothing here has version history yet.
- No automated tests exist anywhere in the repo; everything has been verified with manual
  smoke tests so far.

## The inventory data layer

`data/inventory/schema.sql` defines 5 tables in SQLite:

- **Chemical** — one row per chemical: identity (name/CAS/formula/category), physical
  properties (form, particle size, purity), hazard metadata (UN number, hazard class,
  storage class/location), stock levels (quantity on hand, reorder threshold), and
  sensitivity data (impact/friction) used for safety reasoning.
- **Experiment_Schedule** — planned/approved lab experiments, each with a risk level,
  approval workflow (`approval_status`/`approved_by`), and an `ips_reference_citation`
  linking back to the proceedings corpus.
- **Experiment_Chemical** — junction table: which chemicals (and quantities) an experiment
  requires.
- **Purchase_Order** — restocking orders per chemical, with DOT hazmat shipping class and
  an approval workflow.
- **Decision_Log** — audit trail of agent-generated decisions. Each row records the
  triggering event, any `vector_store_citations` pulled from the IPS corpus, an
  `inventory_snapshot_summary`, the recommended action, a confidence score, which
  `agent_model` produced it, and the human reviewer's outcome
  (`Approved`/`Overridden`/`Pending`). This is the integration point between the agent
  layer and both data sources: `mcp_servers/server.py`'s `log_decision` tool writes rows
  here (always `human_decision='Pending'`), and the dashboard's review panel
  (`dashboard/actions.py`) is how a human sets `human_decision`/`human_reviewer`/`outcome`.

Foreign keys cascade/restrict per the schema (e.g. deleting a chemical that's referenced by
a purchase order is restricted; deleting an experiment schedule cascades to its chemical
requirements).

### Rebuilding the database

```
python data/inventory/seed.py
```

This drops and recreates `data/inventory/inventory.db` from `schema.sql`, then loads
realistic fake lab data (chemicals, experiments, POs, and example decision-log entries)
defined directly in `seed.py`. Re-run this any time `schema.sql` changes or the seed data
needs refreshing — it's the only way the two stay in sync (there's no migration tooling).

## Working in this repo

- `data/corpus/` contains an `intsoc login.txt` file alongside the PDFs — treat it as a
  credential file, not a data file. Never read, print, or commit its contents.
- `pipeline/`, `mcp_servers/`, and `agents/` are now implemented — check their existing
  conventions (`pipeline/store.py` for Chroma access, `mcp_servers/server.py`'s tool
  functions, `agents/loop.py`'s manual tool-call loop, `dashboard/queries.py` vs.
  `dashboard/actions.py`'s read/write connection split) before introducing new patterns.
- Known gaps, in rough priority order: no git history for anything built so far (consider
  `git init` before further major changes); no automated tests; article-level citations
  don't cover the full corpus (see `pipeline/` above); the agent's tool-call arguments
  aren't always well-formed (e.g. it has sent `unit_cost_usd` instead of
  `draft_purchase_order`'s actual `unit_cost` parameter, silently dropping the value —
  worth tightening tool descriptions/param names in `mcp_servers/server.py` if it recurs).
