# Contributing

This project ingests Oregon public-records data and republishes it as a
catalog and change feed. Contributions are welcome, with the constraints
below.

## Principles (read first)

The full statement is in [PRIVACY.md](PRIVACY.md#principles). The short
version, since these are hard rules:

1. **Republish, don't enrich.** No joins to other datasets that reconstruct
   information the publishing agency chose not to release.
2. **Mirror corrections.** When the source corrects, we follow on the next
   snapshot.
3. **Honor takedown requests** for errors this project introduced.
4. **Aggregate-only for any health-related data.**
5. **No scoring, ranking, or editorializing.**
6. **No reidentification** of aggregated records.
7. **No harassment surfaces** — no person-search, no contact-info enrichment.

A pull request that violates any of these will be closed regardless of
technical merit.

## How to contribute

1. **Open an issue first** for anything bigger than a typo fix or a clearly
   isolated bug. New data sources, schema changes, and UI surfaces benefit
   from up-front discussion.
2. **Match the existing patterns.**
   - New data sources go under `etl/sources/` (Phase 2) and follow the
     extract → transform → load contract.
   - New controlled vocabularies go under `vocabularies/` as SKOS-lite YAML.
   - Each new dataset gets a [`docs/DATA_CATALOG.md`](docs/DATA_CATALOG.md)
     entry with publisher, source URL, license, cadence, fields, and known
     issues.
3. **Tests are required** for transform and diff logic. Network-touching
   tests are marked `@pytest.mark.network` and excluded from CI by default.
4. **Run lint and tests locally** before opening a PR:
   ```
   ruff check .
   pytest -m "not network"
   ```
5. **Provenance must travel.** Any code path that ingests new data records
   `source_url`, `source_retrieved_at`, `source_checksum`, and
   `extraction_version` on every row.

## Code style

- Python 3.12, type hints encouraged, ruff config is the source of truth.
- No comments that restate the code; comments explain *why* something is
  surprising.
- No silent failures. If extraction or validation hits an unexpected
  condition, raise loudly with context.

## What's out of scope

- Adding states beyond Oregon (this is Oregon-focused on purpose).
- Authentication / accounts (the data is public).
- Machine-learning features that score, rank, or predict behavior of named
  licensees.
- Anything in the Phase 2 "Not using" list in [PLAN.md](PLAN.md).

## Reporting a data error

- **Error in the source data:** route to the publishing agency (e.g. OLCC).
  This project republishes; we don't correct upstream.
- **Error introduced by this project's processing:** open an issue with the
  `data-correction` label including the snapshot date, the affected
  `license_number` (or equivalent identifier), and the discrepancy.
