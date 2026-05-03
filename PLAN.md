# Oregon Cannabis License Watch

**Owner:** Mark Pernotto (mark@pernotto.com)
**Created:** 2026-04-24
**Purpose:** A data-engineering project built on public Oregon cannabis data. Practical experience with multi-source ETL, schema design, data cataloging, and operational pipelines. Built for learning; public because there's no reason not to be.

---

## Approach: Ship Small First, Then Scale

Two phases. Phase 1 is a small, shippable tool. Phase 2 subsumes Phase 1 into a broader data warehouse. Phase 1 becomes source module #1 of the warehouse.

- **Phase 1** — Oregon Cannabis License Change-Detection. Target: ~2 weeks.
- **Phase 2** — Oregon Cannabis Open Data Warehouse. Target: ~4 weeks after Phase 1 ships.

---

## Tech Stack

The stack favors tools that are actually used in industry DE work. The line we hold is at "platform engineering / SRE" concerns — Kubernetes, Spark, Kafka — which this project doesn't need and which tip into operating infrastructure for a team rather than building pipelines.

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Primary language |
| Warehouse | Postgres 16 (Neon free tier) | dbt-friendly; free tier sufficient |
| Object storage | Cloudflare R2 (Phase 1); AWS S3 as alternate backend (Phase 2) | Raw landing zone — THE foundational DE pattern. R2 is cheap and simple; S3 in Phase 2 for "yes I've used S3" authenticity |
| Orchestration | GitHub Actions cron (Phase 1); Airflow (Phase 2) | Actions is fine for a 2-week MVP; Airflow is what DE job listings name. |
| Transform | dbt Core (Phase 2) | Industry-standard SQL transform tool |
| Containerization | Docker + docker-compose (from Day 1) | Reproducible local → CI → prod runs. Table stakes. |
| IaC | Terraform (Phase 2, small scope: R2/S3 bucket, Fly app) | Real exposure to Terraform without the full SRE burden |
| Frontend | Vite + React + TypeScript | Existing strength |
| API | FastAPI | Lightweight, typed, Python-native |
| Hosting | Neon (Postgres), Cloudflare R2 (objects), Fly.io (API), Vercel (frontend) | Cheap/free, sane free tiers |
| PDF parsing | `pdfplumber` | Better multi-column results than `tabula-py` for Oregon DOR PDFs |
| HTML scraping | `requests` + `beautifulsoup4`; `playwright` only if JS-required | Keep simple |
| Tableau extraction | Direct `.csv` URL form (verified — see `docs/TABLEAU_RESEARCH.md`) | OLCC's Tableau Server exposes a stable CSV export endpoint |
| Data quality | `pytest` + targeted assertions (Phase 1); Great Expectations or dbt tests (Phase 2) | Progressive rigor |
| Local analytics | DuckDB (Phase 2, optional) | Modern in-process analytics engine; worth touching |

**Not using:** Kubernetes, Spark, Kafka, Snowflake/BigQuery/Redshift (dbt-on-Postgres teaches the same SQL modeling).

---

## Data Source Inventory

All public records. Attribute the agency in README and in-app. Scrape on a human cadence, not a high-volume one. Use a `User-Agent` that identifies the project and a contact email.

### Oregon

| Source | URL | Format | Update | Phase |
|---|---|---|---|---|
| OLCC Cannabis Licensee Tableau | https://data.olcc.state.or.us/t/OLCCPublic/views/CannabisBusinessLicensesEndorsements/CannabisLicensesEndorsements | CSV export | Weekly-ish | **1 + 2** |
| OLCC Market Data Tableau | https://data.olcc.state.or.us/#/site/OLCCPublic/views/MarketDataTableau/MainScreen | CSV | Monthly | 2 |
| OLCC Cannabis Thefts | https://www.oregon.gov/olcc/marijuana/Pages/marijuana-thefts.aspx | Tableau | Irregular | 2 |
| OR DOR monthly marijuana tax distribution | https://www.oregon.gov/dor/programs/businesses/Documents/Marjuana_monthly_financial_reporting_distributions_public.pdf | PDF | Monthly | 2 |
| OLCC "Where the Money Goes" | https://www.oregon.gov/olcc/Pages/Where-The-Money-Goes.aspx | HTML + PDFs | Quarterly | 2 |
| OLCC Bulletins | https://www.oregon.gov/olcc/marijuana/pages/bulletins.aspx | PDF (HTML index) | Irregular | 2 (optional) |
| data.oregon.gov Cannabis Pesticide Guide | https://data.oregon.gov/d/b8ki-p9ef | Socrata SODA API | ~Annual | 2 |
| OHA OMMP Medical Marijuana Statistics | https://www.oregon.gov/oha/ph/DiseasesConditions/ChronicDisease/MedicalMarijuanaProgram/Pages/data.aspx | PDF quarterly | Quarterly | 2 |
| Portland Cannabis Program stats | https://www.portland.gov/ppd/cannabis/statistics | HTML/PDF | Monthly | 2 (optional) |

### Not available — do not pursue

- **METRC raw transaction data** — legally exempt per ORS 475C.517
- **Producer/processor/wholesaler physical addresses** — legally withheld
- **Licensee-specific inventory, security plans** — exempt

---

## Library / Organizational Craft (cross-phase)

These are first-class artifacts, not decoration. They make the project more useful and more maintainable.

- **`docs/DATA_CATALOG.md`** — one entry per dataset: title, publisher, source URL, license, update cadence, coverage period, schema, known quality issues, citation string.
- **Controlled vocabularies** under `vocabularies/` — `license_type`, `status`, `change_type` as SKOS-lite YAML (term, preferred label, definition, source authority, deprecated mappings). `transform.py` loads these rather than hard-coding enums.
- **Provenance on every row** — `source_url`, `source_retrieved_at`, `source_checksum` (sha256 of the source file), `extraction_version` carried through to derived tables.
- **Archival snapshot series** — `data/snapshots/` with monthly tarball rollups to `data/archive/YYYY-MM.tar.gz`; ~30 days kept loose.
- **Explicit licensing** — MIT on code, CC0 on derived data. Stated in `LICENSE` / `LICENSE-DATA`.
- **`PRIVACY.md`** + **`CONTRIBUTING.md` Principles** — what is and isn't published, plus hard rules: republish-don't-enrich, mirror corrections, no scoring/ranking, no person-search enrichment.

---

# PHASE 1 — Oregon Cannabis License Change-Detection

## Goal

A daily job that snapshots the OLCC active licensee dataset, diffs against the previous snapshot, and publishes a public feed of license state changes. Ship in ~2 weeks (budget 3).

## Definition of Done

- [x] ETL pipeline (extract → transform → load → diff) implemented and tested end-to-end
- [x] Postgres schema applied; live OLCC data verified working (2,660 rows)
- [x] `DATA_CATALOG.md` entry for the OLCC licensee dataset
- [x] Controlled-vocabulary files for `license_type`, `status`, `change_type`
- [x] `PRIVACY.md` + `CONTRIBUTING.md` (Principles) + `LICENSE` + `LICENSE-DATA`
- [x] pytest suite covers extract, transform, load idempotency, diff correctness, vocab validation (24 tests)
- [ ] Repo public on github.com/markpernotto/oregon-cannabis-license-watch
- [ ] Public JSON endpoint at `/changes/latest` and `/changes/<YYYY-MM>`
- [ ] Public RSS feed
- [ ] Minimal React page shows last 30 days of changes, filterable by license type and county
- [ ] GitHub Action runs nightly without manual intervention and has been green for 5 consecutive days
- [ ] Freshness SLO stated: published data is ≤ 26 hours stale from source

## Schema

Schema reflects verified OLCC source columns (see `docs/TABLEAU_RESEARCH.md`). The OLCC view exposes fewer fields than initially speculated: no `issued_date`, no standalone `city`, and `Status` is always `ACTIVE` because the view is pre-filtered. Columns below use the canonical naming after transform; the `raw_row` JSONB column preserves the original source row.

### `licensees_snapshots` (raw landing)

```
snapshot_date          DATE NOT NULL
license_number         TEXT NOT NULL          -- e.g. "020-1001842C5BE"; prefix encodes type
license_type           TEXT NOT NULL          -- normalized via vocabularies/license_type.yaml
status                 TEXT NOT NULL          -- source view emits "ACTIVE" only
legal_name             TEXT                   -- source column "Business Licenses"
trade_name             TEXT                   -- source column "Business Name"
endorsements           TEXT[]                 -- comma-separated in source; parsed to array
county                 TEXT
physical_address       TEXT                   -- retailers + labs only; "Exempt from Public Disclosure" otherwise
tier                   TEXT                   -- producers only: "Tier I" / "Tier II"
canopy_type            TEXT                   -- producers only
sos_registration       TEXT                   -- Oregon Secretary of State business-entity number
expiration_date        DATE
raw_row                JSONB                  -- full source row for forensics
source_url             TEXT NOT NULL
source_retrieved_at    TIMESTAMPTZ NOT NULL
source_checksum        TEXT NOT NULL          -- sha256 of the CSV bytes
extraction_version     TEXT NOT NULL
PRIMARY KEY (snapshot_date, license_number)
```

**Diff consequences of `Status == ACTIVE` only:** the source only shows currently-active licenses, so `STATUS_CHANGE` as a distinct event is not observable — a license leaving the list manifests as `REMOVED`. If it returns later, `NEW` fires again. Finer-grained termination reasons (Revoked vs Surrendered vs Expired) would need a different source.

### `license_changes` (derived)

```
change_id              BIGSERIAL PRIMARY KEY
observed_at            TIMESTAMPTZ NOT NULL
license_number         TEXT NOT NULL
change_type            TEXT NOT NULL          -- NEW, REMOVED, FIELD_CHANGE
field_name             TEXT                   -- non-null when change_type = FIELD_CHANGE
prev_value             JSONB
new_value              JSONB
diff_summary           TEXT
source_snapshot_date   DATE NOT NULL
UNIQUE (source_snapshot_date, license_number, change_type, field_name) NULLS NOT DISTINCT
```

The unique index backs `INSERT ... ON CONFLICT DO NOTHING`, so re-running diff on the same snapshot pair never duplicates rows.

### `licensees_current` (view)

`SELECT * FROM licensees_snapshots WHERE snapshot_date = (SELECT MAX(snapshot_date) ...)`. Always reflects the latest snapshot only — a license REMOVED today does not appear in this view, even though we still have its prior snapshot rows.

## Pipeline

```
OLCC Tableau (.csv URL — Tableau Server direct export, verified)
        │
        ▼ nightly cron (GitHub Actions)
  extract.py       → data/snapshots/YYYY-MM-DD.csv (committed)
        │           + bundled Sectigo intermediate (server omits it)
        ▼
  transform.py     → normalize, coerce, validate against controlled vocabularies
        │
        ▼
  load.py          → UPSERT into licensees_snapshots
        │
        ▼
  diff.py          → compare today vs. yesterday → license_changes (idempotent)
        │
        ▼
  publish.py       → regenerate rss.xml + changes.json
        │
        ▼
  FastAPI / Vercel → /api/changes, /api/licensees, /rss.xml
```

## Repository layout

```
oregon-cannabis-license-watch/
├── .github/workflows/
│   ├── nightly.yml
│   └── ci.yml
├── etl/
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── diff.py
│   ├── publish.py
│   ├── run.py                # CLI: extract → transform → load → diff
│   ├── vocab.py              # controlled-vocabulary loader
│   ├── schema.sql
│   └── certs/                # bundled TLS intermediate (OLCC server omits)
├── vocabularies/
│   ├── license_type.yaml
│   ├── status.yaml
│   └── change_type.yaml
├── api/                      # FastAPI app (Phase 1 end)
├── web/                      # Vite + React + TS UI (Phase 1 end)
├── data/
│   ├── snapshots/            # ~30 days loose
│   └── archive/              # YYYY-MM.tar.gz rollups
├── tests/
│   ├── test_extract.py
│   ├── test_transform.py
│   ├── test_load.py
│   ├── test_diff.py
│   └── fixtures/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_CATALOG.md
│   ├── DATA_SOURCES.md
│   ├── TABLEAU_RESEARCH.md
│   └── diagrams/
├── LICENSE                   # MIT (code)
├── LICENSE-DATA              # CC0 (derived data)
├── PRIVACY.md
├── CONTRIBUTING.md           # includes Principles
├── pyproject.toml
├── README.md
└── .env.example
```

## Risk register

| Risk | Mitigation |
|---|---|
| OLCC TLS chain is incomplete (verified) | Bundle the Sectigo intermediate at `etl/certs/`; merge with certifi at runtime. Refresh procedure documented. |
| OLCC Tableau endpoint is unreliable or changes URL form | Manual download is an acceptable fallback; the project does not bypass any access control. |
| Initial snapshot has nothing to diff against | First run emits zero changes, not errors (verified). |
| Dates/enums drift in source data | `raw_row JSONB` preserves source row; transforms log unknown enum values rather than failing. Real-world `*` sentinel values for dates handled. |
| Neon free tier pauses after inactivity | ~2s cold start, acceptable for nightly batch |
| Committed snapshot CSVs bloat repo | 30 days loose, monthly tarball rollups to `data/archive/` |
| Scope creep into Phase 2 during Phase 1 | Phase 1 is licensee data only. No tax PDFs, no market data, no lab results. |

---

# PHASE 2 — Oregon Cannabis Open Data Warehouse (outline only)

Detailed plan after Phase 1 ships.

## Scope

Each additional source becomes a module in `etl/sources/` following the same extract → transform → load contract as Phase 1. Each gets its own `DATA_CATALOG.md` entry and vocabulary files if it introduces new controlled terms.

## Source modules (priority order)

1. **OR DOR monthly tax distribution PDFs** — `pdfplumber`, `tax_distributions_monthly`
2. **OLCC Market Data Tableau** — monthly harvest/sales/transfers aggregates
3. **OLCC Theft Dashboard** — `thefts`
4. **OHA OMMP quarterly PDFs** — medical program patient/caregiver/grower counts
5. **data.oregon.gov Cannabis Pesticide Guide** — Socrata API
6. **Portland Cannabis Program** — city-level licensing

## Additional tooling

- **dbt Core** for transforms — raw → staging → marts (star schema)
- **Great Expectations** for data quality
- **Airflow** replaces GitHub Actions cron; one Airflow install (Astronomer free tier or local docker-compose) drives all source flows
- **Terraform** for hosted resources (R2/S3 bucket, Fly app)
- **AWS S3** added as an alternate object-storage backend alongside R2
- **DuckDB** for local ad-hoc analytics
- **FastAPI** grows to cover all domains with `/v1/` versioning
- **React dashboard** grows to one page per data domain

---

## What not to add

- AWS-specific IAM / VPC plumbing — outside scope
- ML / LLM features — dilutes the data-engineering focus
- METRC raw transaction data — legally exempt; don't chase
- Other states — Oregon focus is the story
- Authentication / user accounts — public data, public site
- Person-search or contact-info enrichment — see `CONTRIBUTING.md` Principles
