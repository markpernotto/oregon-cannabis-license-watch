# Oregon Cannabis Data

A public-data pipeline that snapshots Oregon cannabis licensing data nightly,
diffs it against prior snapshots, and publishes a change feed.

Phase 1 (in progress) covers the OLCC Cannabis Licensee Public Report.
Phase 2 will extend to tax distributions, market data, theft reports,
medical-program statistics, pesticide rules, and Portland city data.

## Status

Day 1. Scaffolding in place; extract is implemented against the OLCC Tableau
Server direct-CSV endpoint (verified 2026-04-24). Transform, load, diff,
publish, API, and UI are stubs.

## Quick start

```bash
# 1. Clone, then from the repo root:
cp .env.example .env

# 2. Start a local Postgres and load the schema
docker compose up -d db
# Schema is applied automatically by the db container init.

# 3. Install Python deps (locally, outside docker)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# 4. Run the extractor (writes data/snapshots/YYYY-MM-DD.csv)
python -m etl.extract
```

## Layout

See [PLAN.md](PLAN.md) for the full plan and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the pipeline diagram.

- `etl/` — extract / transform / load / diff / publish modules
- `vocabularies/` — controlled vocabularies (SKOS-lite YAML) for license
  types, statuses, and change types
- `api/` — FastAPI app (Phase 1 end)
- `web/` — React UI (Phase 1 end)
- `data/` — snapshot CSVs (latest ~30 loose, older in `archive/`)
- `docs/` — catalog, data-source inventory, architecture, research notes
- `tests/` — pytest suite

## Data

- **Source:** Oregon Liquor and Cannabis Commission, Cannabis Licensee
  Public Report — a public record under Oregon law.
- **Catalog entry:** [docs/DATA_CATALOG.md](docs/DATA_CATALOG.md)
- **Source extraction research:** [docs/TABLEAU_RESEARCH.md](docs/TABLEAU_RESEARCH.md)

## Licenses

- **Code:** MIT — [LICENSE](LICENSE)
- **Data artifacts:** CC0 1.0 — [LICENSE-DATA](LICENSE-DATA)

## Privacy

See [PRIVACY.md](PRIVACY.md). No personal information is collected from
visitors; the republished data is public-record business licensing.
